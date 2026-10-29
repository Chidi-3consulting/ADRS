"""Regression tests for the release audit (see the audit table delivered with this change)."""
import hashlib
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

import pytest

from app import middleware
from app.auth import hash_password, serializer
from app.core.clock import business_date, business_today
from app.engine import calculate_retention_end_date, run_retention_checks
from app.models import (
    ApiKey, AuditLog, CategoryRetentionRule, ConnectedSystem, DataCategory, DataRecord,
    IntegrationLog, PasswordReset, User,
)

PW = "Correct-Horse-9-Battery"
TODAY = business_today()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _user(db, role="admin", email=None, **kw):
    u = User(organization_id=1, name=f"{role} user", email=email or f"{role}@t.local",
             password_hash=hash_password(PW), role=role, is_active=True, must_change_password=False,
             email_verified_at=datetime(2026, 1, 1), **kw)
    db.add(u)
    db.commit()
    return u


def _login(client, email):
    r = client.post("/login", data={"email": email, "password": PW}, follow_redirects=False)
    assert r.status_code == 303, r.text
    return r


def _cat(db, **kw):
    v = dict(organization_id=1, name="Cat", compliance_framework="GDPR", retention_period_days=30,
             disposal_method="delete", disposal_trigger="date_based", data_classification="standard",
             approval_type="auto_disposal", requires_dual_approval=False, legal_basis="legitimate_interest")
    v.update(kw)
    c = DataCategory(**v)
    db.add(c)
    db.commit()
    return c


def _rec(db, cat, ref, collected=None, **kw):
    r = DataRecord(organization_id=1, category_id=cat.id, record_reference=ref,
                   collection_date=collected or TODAY, status="active", **kw)
    r.category = cat
    calculate_retention_end_date(db, r)
    db.add(r)
    db.commit()
    return r


_n = [0]


def _key(db, perms, rate=600):
    _n[0] += 1
    s = ConnectedSystem(organization_id=1, name=f"Sys{_n[0]}", system_type="custom")
    db.add(s)
    db.commit()
    raw = f"sd_audit_{_n[0]}_" + "k" * 20
    db.add(ApiKey(organization_id=1, system_id=s.id, key_name="k", key_hash=hashlib.sha256(raw.encode()).hexdigest(),
                  key_prefix=raw[:8], permissions=perms, rate_limit_per_min=rate, is_active=True))
    db.commit()
    return {"Authorization": f"Bearer {raw}"}, raw


# ── C1: session enforcement really runs ──


def test_public_path_matching_is_not_a_prefix_of_everything():
    assert middleware._is_public_path("/")
    assert middleware._is_public_path("/login")
    assert middleware._is_public_path("/static/css/app.css")
    assert middleware._is_public_path("/api/v1/ingest")
    assert not middleware._is_public_path("/dashboard")
    assert not middleware._is_public_path("/records/view/1")
    assert not middleware._is_public_path("/admin/retention")


def test_idle_session_is_signed_out(client, db):
    _user(db)
    _login(client, "admin@t.local")
    data = serializer.loads(client.cookies.get("SafeData_session"))
    data["last_activity"] = time.time() - 3 * 3600
    client.cookies.set("SafeData_session", serializer.dumps(data))
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 303 and "/login" in r.headers["location"]


def test_demoted_or_deactivated_user_loses_access_at_once(client, db):
    u = _user(db)
    _login(client, "admin@t.local")
    assert client.get("/users", follow_redirects=False).status_code == 200
    u.role = "data_owner"
    db.commit()
    assert client.get("/users", follow_redirects=False).status_code == 403
    u.is_active = False
    db.commit()
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 303 and "/login" in r.headers["location"]


def test_password_change_ends_other_sessions(client, db):
    u = _user(db)
    _login(client, "admin@t.local")
    u.password_hash = hash_password("Another-Passw0rd-42!")
    db.commit()
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 303 and "/login" in r.headers["location"]


# ── H: fallback secret key ──


def test_known_dev_secret_is_refused_on_a_real_host():
    env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
    env.update(APP_ENV="local", APP_URL="https://safedata.example.com")
    r = subprocess.run([sys.executable, "-c", "import app.config"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 1 and "SECRET_KEY" in r.stderr


# ── CSRF is enforced outside the test environment, and every form carries the token ──


def test_every_post_form_has_a_csrf_field():
    import glob
    import re
    missing = []
    for f in glob.glob(os.path.join(ROOT, "app", "templates", "*.html")):
        text = open(f, encoding="utf-8").read()
        for m in re.finditer(r"<form\b[^>]*>(.*?)</form>", text, re.S | re.I):
            tag = re.match(r"<form\b[^>]*>", m.group(0), re.I).group(0)
            if re.search(r'method\s*=\s*["\']?post', tag, re.I) and "csrf" not in m.group(1):
                missing.append(os.path.basename(f))
    assert not missing, missing


def test_post_without_csrf_token_is_rejected_when_enforced(client, db, monkeypatch):
    _user(db)
    _login(client, "admin@t.local")
    monkeypatch.setattr(middleware, "APP_ENV", "production")
    r = client.post("/notifications/read-all", follow_redirects=False)
    assert r.status_code == 403
    token = serializer.loads(client.cookies.get("SafeData_session"))["csrf_token"]
    r = client.post("/notifications/read-all", data={"csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303


# ── API ──


def test_metrics_and_audit_verify_endpoints_work(client, db):
    h, _ = _key(db, ["read"])
    assert client.get("/api/v1/dashboard/metrics", headers=h).status_code == 200
    assert client.get("/api/v1/disposal/analytics", headers=h).status_code == 200
    r = client.get("/api/v1/audit/verify", headers=h)
    assert r.status_code == 200 and r.json()["chain_intact"] is True


def test_ingest_validation(client, db):
    cat = _cat(db)
    inactive = _cat(db, name="Off", is_active=False)
    h, _ = _key(db, ["ingest"])
    ok = {"record_reference": "A-1", "category_id": cat.id, "collection_date": TODAY.isoformat()}
    assert client.post("/api/v1/ingest", headers=h, json=ok).status_code == 200
    assert client.post("/api/v1/ingest", headers=h, json=ok).json()["status"] == "duplicate"
    assert client.post("/api/v1/ingest", headers=h, json={**ok, "record_reference": "B", "collection_date": "29/10/2026"}).status_code == 400
    future = (TODAY + timedelta(days=30)).isoformat()
    assert client.post("/api/v1/ingest", headers=h, json={**ok, "record_reference": "C", "collection_date": future}).status_code == 400
    assert client.post("/api/v1/ingest", headers=h, json={**ok, "record_reference": "D", "category_id": 99999}).status_code == 400
    assert client.post("/api/v1/ingest", headers=h, json={**ok, "record_reference": "E", "category_id": inactive.id}).status_code == 400
    assert client.post("/api/v1/ingest", headers=h, json={**ok, "record_reference": "x" * 300}).status_code == 422
    assert client.post("/api/v1/ingest", headers=h, json={**ok, "record_reference": "F", "notes": "n" * 5000}).status_code == 422
    assert db.query(DataRecord).count() == 1


def test_batch_reports_every_rejected_row_instead_of_dropping_it(client, db):
    cat = _cat(db)
    h, _ = _key(db, ["ingest"])
    good = {"record_reference": "G-1", "category_id": cat.id, "collection_date": TODAY.isoformat()}
    rows = [good, {**good, "record_reference": "G-2", "collection_date": "nope"},
            {**good, "record_reference": "G-3", "category_id": 424242}, good, {"category_id": cat.id}]
    r = client.post("/api/v1/ingest/batch", headers=h, json={"records": rows})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "partial"
    assert body["processed"] == 1 and body["duplicates_skipped"] == 1
    assert [x["index"] for x in body["rejected"]] == [1, 2, 4]


def test_consent_signal_rejects_bad_dates_and_converts_offsets(client, db):
    cat = _cat(db, legal_basis="consent", disposal_trigger="consent_withdrawal", retention_period_days=7)
    _rec(db, cat, "W-1")
    h, _ = _key(db, ["consent"])
    assert client.post("/api/v1/consent/signal", headers=h, json={"record_reference": "W-1", "withdrawn_at": "last tuesday"}).status_code == 422
    future = (datetime.utcnow() + timedelta(days=10)).isoformat()
    assert client.post("/api/v1/consent/signal", headers=h, json={"record_reference": "W-1", "withdrawn_at": future}).status_code == 422
    # 23:30 at +01:00 on 10 Jan is 22:30 UTC the same day, which is 10 Jan in Lagos
    r = client.post("/api/v1/consent/signal", headers=h,
                    json={"record_reference": "W-1", "withdrawn_at": "2026-01-10T23:30:00+01:00"})
    assert r.status_code == 200
    assert r.json()["records"][0]["retention_end_date"] == "2026-01-17"


def test_terminate_accepts_x_api_key_404_for_unknown_and_is_idempotent(client, db):
    cat = _cat(db, disposal_trigger="account_closure", retention_period_days=10)
    _rec(db, cat, "T-1")
    _, raw = _key(db, ["terminate"])
    hx = {"X-API-Key": raw}
    assert client.post("/api/v1/records/terminate", headers=hx, json={"external_ref": "NOPE"}).status_code == 404
    assert client.post("/api/v1/records/terminate", headers=hx, json={"external_ref": "T-1", "termination_date": "bad"}).status_code == 422
    r = client.post("/api/v1/records/terminate", headers=hx, json={"external_ref": "T-1", "termination_date": TODAY.isoformat()})
    assert r.status_code == 200 and r.json()["matched_count"] == 1
    r = client.post("/api/v1/records/terminate", headers=hx, json={"external_ref": "T-1", "termination_date": TODAY.isoformat()})
    assert r.json()["matched_count"] == 0 and r.json()["already_terminated"] == 1


def test_dispose_needs_an_explicit_permission_even_for_unrestricted_keys(client, db):
    cat = _cat(db)
    _rec(db, cat, "D-1")
    h, _ = _key(db, [])  # legacy key with no permission list
    assert client.post("/api/v1/records/disposed", headers=h, json={"external_ref": "D-1"}).status_code == 403
    assert client.get("/api/v1/categories", headers=h).status_code == 200


def test_rate_limit_counts_read_calls_too(client, db):
    h, _ = _key(db, ["read"], rate=3)
    codes = [client.get("/api/v1/categories", headers=h).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and 429 in codes[3:]


def test_bad_keys_are_throttled_per_client(client, db):
    codes = [client.get("/api/v1/categories", headers={"Authorization": "Bearer nope"}).status_code for _ in range(25)]
    assert codes[0] == 401 and codes[-1] == 429
    assert db.query(IntegrationLog).filter(IntegrationLog.method == "AUTH").count() <= 21


# ── auth flows ──


def test_two_factor_codes_are_throttled(client, db):
    from app.auth import encrypt_totp_secret
    from app.helpers import totp_generate_secret
    u = _user(db, twofa_enabled=True, twofa_secret=encrypt_totp_secret(totp_generate_secret()))
    client.post("/login", data={"email": u.email, "password": PW}, follow_redirects=False)
    last = ""
    for _ in range(8):
        last = client.post("/login/2fa", data={"code": "000000"}).text
    assert "Too many failed attempts" in last


def test_reset_and_invite_links_use_the_configured_address_not_the_host_header(client, db, monkeypatch):
    from app.routes import public as pub
    sent = []
    monkeypatch.setattr(pub, "send_system_email", lambda db_, to, subject, html: sent.append(html) or True)
    _user(db, email="victim@t.local")
    client.post("/forgot_password", data={"email": "victim@t.local"}, headers={"host": "evil.example"})
    assert sent and "evil.example" not in sent[0] and "/reset_password?" in sent[0]


def test_forgot_password_is_limited_per_address(client, db, monkeypatch):
    from app.routes import public as pub
    sent = []
    monkeypatch.setattr(pub, "send_system_email", lambda *a: sent.append(1) or True)
    _user(db, email="flood@t.local")
    for _ in range(6):
        client.post("/forgot_password", data={"email": "flood@t.local"})
    assert len(sent) == 3


def test_invitation_enforces_the_password_policy(client, db):
    from app.models import OrganizationInvitation
    raw = "tok" * 10
    db.add(OrganizationInvitation(organization_id=1, email="new@t.local", name="New Person", role="dpo",
                                  token_hash=hashlib.sha256(raw.encode()).hexdigest(), invited_by=None,
                                  expires_at=datetime.utcnow() + timedelta(days=1)))
    db.commit()
    r = client.post("/invite/accept", data={"token": raw, "password": "short", "password_confirm": "short"}, follow_redirects=False)
    assert "weak_password" in r.headers["location"]
    assert db.query(User).filter(User.email == "new@t.local").count() == 0


def test_admin_user_creation_checks_role_and_password_and_is_audited(client, db):
    _user(db)
    _login(client, "admin@t.local")
    bad = client.post("/users/create", data={"name": "X Y", "email": "x@t.local", "password": "weak", "role": "admin"}, follow_redirects=False)
    assert "weak_password" in bad.headers["location"]
    bad = client.post("/users/create", data={"name": "X Y", "email": "x@t.local", "password": PW, "role": "root"}, follow_redirects=False)
    assert "invalid_input" in bad.headers["location"]
    client.post("/users/create", data={"name": "X Y", "email": "X@t.local", "password": PW, "role": "dpo"})
    assert db.query(User).filter(User.email == "x@t.local").one().must_change_password is True
    assert db.query(AuditLog).filter(AuditLog.action == "user_created").count() == 1


def test_profile_needs_the_current_password_to_change_password(client, db):
    _user(db)
    _login(client, "admin@t.local")
    r = client.post("/profile", data={"name": "A B", "email": "admin@t.local", "password": "New-Passw0rd-77!"}, follow_redirects=False)
    assert "current%20password" in r.headers["location"]
    r = client.post("/profile", data={"name": "A B", "email": "admin@t.local", "password": "New-Passw0rd-77!",
                                      "current_password": PW}, follow_redirects=False)
    assert "saved=1" in r.headers["location"]
    assert client.get("/dashboard", follow_redirects=False).status_code == 200  # this session stays valid


def test_step_up_is_mandatory_for_permanent_actions(client, db):
    _user(db)
    cat = _cat(db)
    rec = _rec(db, cat, "S-1", collected=TODAY - timedelta(days=90))
    _login(client, "admin@t.local")
    r = client.post(f"/records/dispose/{rec.id}", data={}, follow_redirects=False)
    assert "stepup_failed" in r.headers["location"]
    db.expire_all()
    assert db.get(DataRecord, rec.id).status != "disposed"
    r = client.post(f"/records/dispose/{rec.id}", data={"auth_credential": PW}, follow_redirects=False)
    db.expire_all()
    assert db.get(DataRecord, rec.id).status == "disposed"
    r = client.post("/records/bulk_dispose", data={"record_ids": "1", "return_url": "https://evil.example/x"}, follow_redirects=False)
    assert r.headers["location"].startswith("/records")


def test_settings_reject_garbled_numbers_and_the_run_survives_old_bad_values(client, db):
    from app.models import OrganizationSetting
    _user(db)
    _login(client, "admin@t.local")
    r = client.post("/settings/save", data={"tab": "general", "sub_tab": "retention", "escalation_days": "abc",
                                            "consent_disposal_days": "-5"}, follow_redirects=False)
    assert "saved" not in r.headers["location"]
    assert db.query(OrganizationSetting).count() == 0
    db.add(OrganizationSetting(organization_id=1, setting_key="escalation_days", setting_value="abc"))
    db.commit()
    assert run_retention_checks(db, 1, dry_run=True)["dry_run"] is True


# ── categories ──


def test_data_owner_cannot_change_categories(client, db):
    _user(db, role="data_owner", email="owner@t.local")
    cat = _cat(db)
    _login(client, "owner@t.local")
    assert client.get("/categories/create").status_code == 403
    assert client.get(f"/categories/edit/{cat.id}").status_code == 403
    form = dict(name="X", retention_reason="r", legal_basis="contract", disposal_trigger="date_based",
                retention_period_days="0", disposal_method="delete", review_frequency="monthly")
    assert client.post(f"/categories/edit/{cat.id}", data=form).status_code == 403
    assert client.post("/categories/create", data=form).status_code == 403


def test_category_edit_validates_and_records_before_and_after(client, db):
    _user(db, role="dpo", email="dpo@t.local")
    cat = _cat(db, retention_period_days=30)
    _login(client, "dpo@t.local")
    form = dict(name="X", retention_reason="r", legal_basis="made_up", disposal_trigger="date_based",
                retention_period_days="10", disposal_method="delete", review_frequency="monthly")
    assert client.post(f"/categories/edit/{cat.id}", data=form).status_code == 422
    form.update(legal_basis="contract", retention_period_days="-1")
    assert client.post(f"/categories/edit/{cat.id}", data=form).status_code == 422
    form.update(retention_period_days="90")
    assert client.post(f"/categories/edit/{cat.id}", data=form, follow_redirects=False).status_code == 303
    entry = db.query(AuditLog).filter(AuditLog.action == "category_updated").one()
    assert entry.details["before"]["retention_period_days"] == 30 and entry.details["after"]["retention_period_days"] == 90


# ── exports, webhooks, emails ──


def test_csv_cells_that_look_like_formulas_are_neutralised():
    from app.core.csvsafe import safe_cell
    assert safe_cell("=HYPERLINK(\"http://x\")") == "'=HYPERLINK(\"http://x\")"
    assert safe_cell("+1") == "'+1" and safe_cell("@a") == "'@a" and safe_cell("-2") == "'-2"
    assert safe_cell("INV-1") == "INV-1" and safe_cell(5) == 5


def test_webhook_urls_cannot_reach_internal_addresses():
    from app.core.urlguard import url_problem
    for bad in ("http://localhost/x", "http://127.0.0.1/", "http://169.254.169.254/latest", "http://10.0.0.5/",
                "ftp://example.com/", "https://user:pw@example.com/", "http://service.internal/"):
        assert url_problem(bad), bad
    assert url_problem("https://script.google.com/macros/s/abc/exec") is None
    assert url_problem("") is None


def test_system_form_rejects_internal_base_url(client, db):
    _user(db)
    _login(client, "admin@t.local")
    r = client.post("/integrations/systems/create", data={"name": "S", "base_url": "http://169.254.169.254/"})
    assert r.status_code == 422


def test_webhook_signature_covers_the_exact_bytes_sent(db, monkeypatch):
    import hmac
    import httpx
    from app import enterprise
    from app.models import DisposalDispatch
    s = ConnectedSystem(organization_id=1, name="S", system_type="custom", signing_secret="sekret", base_url="https://93.184.216.34/hook")
    db.add(s)
    db.commit()
    cat = _cat(db)
    rec = _rec(db, cat, "H-1")
    db.add(DisposalDispatch(organization_id=1, record_id=rec.id, system_id=s.id, dispatch_type="delete", external_ref="H-1",
                            endpoint_url="https://93.184.216.34/hook", status="pending",
                            payload='{"action": "delete", "record_reference": "H-1"}'))
    db.commit()
    seen = {}

    def fake_post(url, content=None, headers=None, **kw):
        seen.update(content=content, headers=headers, follow=kw.get("follow_redirects"))
        return httpx.Response(200, text="ok")
    monkeypatch.setattr(enterprise.httpx, "post", fake_post)
    enterprise.process_disposal_dispatches(db)
    expected = hmac.new(b"sekret", seen["content"], hashlib.sha256).hexdigest()
    assert seen["headers"]["X-SafeData-Signature"] == expected and seen["follow"] is False


def test_event_email_escapes_user_supplied_text(monkeypatch):
    import app.helpers as h
    from app import engine
    mails = []
    monkeypatch.setattr(h, "send_system_email", lambda db, to, subject, html: mails.append(html) or True)
    import threading
    monkeypatch.setattr(threading, "Thread", lambda target, daemon: type("T", (), {"start": lambda self: target()})())
    engine._send_event_email("a@b.c", "<script>x</script>", "s", "<img src=x onerror=1>", "review_due")
    assert "<script>" not in mails[0] and "<img" not in mails[0]


# ── retention engine ──


def test_a_rule_that_needs_two_people_beats_an_automatic_category(db):
    cat = _cat(db, approval_type="auto_disposal")
    rule = CategoryRetentionRule(organization_id=1, category_id=cat.id, rule_name="strict", legal_basis="contract",
                                 retention_period_days=30, retention_period_label="30 days", requires_dual_approval=True)
    db.add(rule)
    db.commit()
    rec = _rec(db, cat, "P-1", collected=TODAY - timedelta(days=60), retention_rule_id=rule.id)
    res = run_retention_checks(db, 1)
    db.expire_all()
    assert res["auto_disposed"] == 0 and res["skipped_dual"] == 1
    assert db.get(DataRecord, rec.id).status != "disposed"


def test_legal_hold_is_never_deleted_by_a_real_run(db):
    cat = _cat(db)
    held = _rec(db, cat, "L-1", collected=TODAY - timedelta(days=90), legal_hold=True)
    free = _rec(db, cat, "L-2", collected=TODAY - timedelta(days=90))
    run_retention_checks(db, 1)
    db.expire_all()
    assert db.get(DataRecord, held.id).status != "disposed"
    assert db.get(DataRecord, free.id).status == "disposed"


def test_dry_run_changes_nothing(db):
    cat = _cat(db)
    rec = _rec(db, cat, "N-1", collected=TODAY - timedelta(days=90))
    before = db.query(AuditLog).count()
    run_retention_checks(db, 1, dry_run=True)
    db.expire_all()
    assert db.get(DataRecord, rec.id).status == "active" and db.query(AuditLog).count() == before


def test_business_date_is_lagos_not_utc():
    assert business_date(datetime(2026, 3, 1, 23, 30)) == datetime(2026, 3, 2).date()
    assert business_date(datetime(2026, 3, 1, 12, 0)) == datetime(2026, 3, 1).date()
    assert business_date(None) is None


def test_consent_withdrawn_late_in_the_utc_evening_counts_as_the_next_lagos_day(db):
    cat = _cat(db, legal_basis="consent", disposal_trigger="consent_withdrawal", retention_period_days=7)
    rec = _rec(db, cat, "Z-1", consent_withdrawn_at=datetime(2026, 3, 1, 23, 30))
    calculate_retention_end_date(db, rec)
    assert rec.retention_end_date == datetime(2026, 3, 9).date()


# ── audit ledger ──


def test_audit_entries_store_the_instant_that_was_hashed_and_the_chain_verifies(db):
    from app.engine import verify_audit_chain
    from app.helpers import log_audit
    for i in range(6):
        log_audit(db, 1, "x", "t", i, None, {"i": i}, "1.1.1.1")
    rows = db.query(AuditLog).order_by(AuditLog.id).all()
    assert all(r.created_at.microsecond == 0 for r in rows)
    assert verify_audit_chain(db)["ok"] is True


def test_verification_covers_the_newest_entries_when_the_ledger_is_long(db):
    from app.engine import verify_audit_chain
    from app.helpers import log_audit
    for i in range(8):
        log_audit(db, 1, "x", "t", i, None, {"i": i}, None)
    last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    last.action = "tampered"
    db.commit()
    assert verify_audit_chain(db, limit=3)["ok"] is False  # the oldest-5000 rule would have missed this


# ── setup wizard ──


def test_setup_counts_as_done_when_any_user_exists_even_without_the_flag(client, db):
    from app.auth import setup_is_complete
    from app.models import SystemSetting
    db.query(SystemSetting).delete()
    db.commit()
    assert setup_is_complete(db) is False
    _user(db)
    assert setup_is_complete(db) is True
    r = client.post("/setup", data={"org_name": "Evil", "name": "E", "email": "e@evil.test", "password": PW,
                                    "password_confirm": PW}, follow_redirects=False)
    assert r.status_code == 303 and "/login" in r.headers["location"]
    assert db.query(User).filter(User.email == "e@evil.test").count() == 0
