"""Admin retention run/simulate and consent management.

A simulation must leave every record, notification and flag exactly as it was.
"""

from datetime import date, datetime, timedelta

import pytest

from app.auth import hash_password
from app.engine import (
    records_past_retention,
    run_retention_checks,
    simulate_consent_removal,
)
from app.models import DataCategory, DataRecord, Notification, User

PW = "Xyq9$mNpL2!kA"
TODAY = date.today()


def _user(db, role, email):
    u = User(
        organization_id=1,
        name=f"{role} user",
        email=email,
        password_hash=hash_password(PW),
        role=role,
        is_active=True,
        must_change_password=False,
    )
    db.add(u)
    db.commit()
    return u


def _login(client, email):
    assert client.post("/login", data={"email": email, "password": PW}, follow_redirects=False).status_code == 303


def _category(db, **kw):
    vals = dict(
        organization_id=1,
        name="Cat",
        compliance_framework="GDPR",
        retention_period_days=30,
        disposal_method="delete",
        disposal_trigger="date_based",
        data_classification="standard",
        approval_type="auto_disposal",
        requires_dual_approval=False,
        legal_basis="legitimate_interest",
    )
    vals.update(kw)
    c = DataCategory(**vals)
    db.add(c)
    db.commit()
    return c


def _record(db, cat, ref, end, status="active", **kw):
    r = DataRecord(
        organization_id=1,
        category_id=cat.id,
        record_reference=ref,
        collection_date=TODAY - timedelta(days=400),
        retention_end_date=end,
        status=status,
        **kw,
    )
    db.add(r)
    db.commit()
    return r


def _snapshot(db):
    db.expire_all()
    return (
        sorted(
            (r.id, r.status, r.review_flagged_at, r.escalation_sent_at, r.disposed_at)
            for r in db.query(DataRecord).all()
        ),
        db.query(Notification).count(),
    )


# ── what counts as "collection" ──


def test_collection_queue_is_only_records_whose_retention_period_was_reached(db):
    cat = _category(db)
    due_today = _record(db, cat, "due-today", TODAY)
    overdue = _record(db, cat, "overdue", TODAY - timedelta(days=9), status="due_review")
    _record(db, cat, "tomorrow", TODAY + timedelta(days=1))
    _record(db, cat, "no-end-date", None)
    _record(db, cat, "disposed", TODAY - timedelta(days=9), status="disposed")
    _record(db, cat, "held", TODAY - timedelta(days=9), legal_hold=True)
    ids = {r.id for r in records_past_retention(db, 1).all()}
    assert ids == {due_today.id, overdue.id}


def test_held_records_can_be_included_on_request(db):
    cat = _category(db)
    held = _record(db, cat, "held", TODAY - timedelta(days=9), legal_hold=True)
    assert held.id in {r.id for r in records_past_retention(db, 1, include_held=True).all()}


# ── simulation is read-only ──


def test_dry_run_changes_nothing_but_reports_what_it_would_do(db):
    cat = _category(db)
    _record(db, cat, "will-flag", TODAY + timedelta(days=5))
    _record(db, cat, "will-dispose", TODAY - timedelta(days=3), status="due_review")
    before = _snapshot(db)
    result = run_retention_checks(db, 1, dry_run=True)
    assert _snapshot(db) == before
    actions = {p["reference"]: p["action"] for p in result["plan"]}
    assert actions == {"will-flag": "flag_for_review", "will-dispose": "auto_dispose"}


def test_dry_run_predicts_what_the_real_run_then_does(db):
    cat = _category(db)
    _record(db, cat, "flag-then-dispose", TODAY - timedelta(days=3))  # still "active"
    plan = {p["reference"]: p["action"] for p in run_retention_checks(db, 1, dry_run=True)["plan"]}
    assert plan["flag-then-dispose"] == "auto_dispose"
    real = run_retention_checks(db, 1)
    assert real["auto_disposed"] == 1
    db.expire_all()
    assert db.query(DataRecord).filter(DataRecord.record_reference == "flag-then-dispose").one().status == "disposed"


def test_dry_run_respects_legal_hold_and_inside_retention(db):
    cat = _category(db)
    _record(db, cat, "held", TODAY - timedelta(days=3), status="due_review", legal_hold=True)
    _record(db, cat, "far-future", TODAY + timedelta(days=300))
    assert run_retention_checks(db, 1, dry_run=True)["plan"] == []


# ── consent removal simulation ──


def test_consent_removal_simulation_reports_disposal_date_without_changing_anything(db):
    cat = _category(db, legal_basis="consent", disposal_trigger="consent_withdrawal")
    rec = _record(db, cat, "consented", None)
    before = _snapshot(db)
    sim = simulate_consent_removal(db, 1)
    assert _snapshot(db) == before
    (item,) = sim["items"]
    assert item["record_id"] == rec.id and item["outcome"] == "would_dispose"
    assert item["dispose_on"] == TODAY + timedelta(days=sim["grace_days"])


def test_consent_removal_simulation_flags_blockers(db):
    held_cat = _category(db, name="A", legal_basis="consent", disposal_trigger="consent_withdrawal")
    other = _category(db, name="B", legal_basis="consent", disposal_trigger="date_based")
    _record(db, held_cat, "held", None, legal_hold=True)
    _record(db, other, "not-consent-triggered", None)
    outcomes = {i["reference"]: i["outcome"] for i in simulate_consent_removal(db, 1)["items"]}
    assert outcomes == {"held": "blocked_by_legal_hold", "not-consent-triggered": "no_automatic_disposal"}


# ── the admin screens ──


def test_only_admins_can_open_the_admin_pages(client, db):
    _user(db, "dpo", "dpo@test.local")
    _login(client, "dpo@test.local")
    for url in ("/admin/retention", "/admin/consent"):
        assert client.get(url).status_code == 403
    assert client.post("/admin/retention/run", data={"confirm": "RUN"}).status_code == 403


def test_admin_can_simulate_then_run(client, db):
    cat = _category(db)
    rec = _record(db, cat, "ADMIN-REC", TODAY - timedelta(days=4), status="due_review")
    _user(db, "admin", "boss@test.local")
    _login(client, "boss@test.local")
    page = client.get("/admin/retention")
    assert page.status_code == 200 and "ADMIN-REC" not in page.text
    sim = client.post("/admin/retention/simulate")
    assert sim.status_code == 200 and "ADMIN-REC" in sim.text and "nothing was changed" in sim.text
    db.expire_all()
    assert db.get(DataRecord, rec.id).status == "due_review"
    # a real run needs the confirmation word
    refused = client.post("/admin/retention/run", data={"confirm": "no"}, follow_redirects=False)
    assert refused.status_code == 303
    db.expire_all()
    assert db.get(DataRecord, rec.id).status == "due_review"
    ran = client.post("/admin/retention/run", data={"confirm": "RUN"})
    assert ran.status_code == 200
    db.expire_all()
    assert db.get(DataRecord, rec.id).status == "disposed"


def test_admin_consent_flow(client, db):
    cat = _category(db, legal_basis="consent", disposal_trigger="consent_withdrawal")
    rec = _record(db, cat, "CONSENT-REC", None)
    _user(db, "admin", "boss@test.local")
    _login(client, "boss@test.local")
    assert "CONSENT-REC" in client.get("/admin/consent").text
    sim = client.post("/admin/consent/simulate", data={"record_id": str(rec.id)})
    assert "Would be disposed" in sim.text
    db.expire_all()
    assert db.get(DataRecord, rec.id).consent_withdrawn_at is None
    done = client.post(f"/admin/consent/withdraw/{rec.id}", follow_redirects=False)
    assert done.status_code == 303
    db.expire_all()
    assert isinstance(db.get(DataRecord, rec.id).consent_withdrawn_at, datetime)


def test_sidebar_links_the_admin_tools(client, db):
    _user(db, "admin", "boss@test.local")
    _login(client, "boss@test.local")
    page = client.get("/dashboard").text
    assert 'href="/admin/retention"' in page and 'href="/admin/consent"' in page


@pytest.mark.parametrize("url", ["/admin/retention", "/admin/consent"])
def test_anonymous_users_are_sent_to_login(client, url):
    r = client.get(url, follow_redirects=False)
    assert r.status_code in (303, 401, 403)
