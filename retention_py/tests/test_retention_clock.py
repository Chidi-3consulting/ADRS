"""One retention clock for every record, whichever way it arrived.

Clock start:
  date_based         -> collection date
  consent_withdrawal -> the day consent was withdrawn
  account_closure    -> the day the relationship ended (account closed, contract or event over)
Deletion date = clock start + the category's retention period. When the lawful basis is
consent and consent is withdrawn, the record may not outlive the post-withdrawal window.
"""
import hashlib
from datetime import date, datetime, timedelta

from app.engine import (
    calculate_retention_end_date,
    log_consent_withdrawal,
    retention_clock,
    run_retention_checks,
)
from app.models import ApiKey, ConnectedSystem, DataCategory, DataRecord, Notification, User

TODAY = date.today()


def _category(db, **kw):
    vals = dict(
        organization_id=1, name="Cat", compliance_framework="GDPR", retention_period_days=30,
        disposal_method="delete", disposal_trigger="date_based", data_classification="standard",
        approval_type="auto_disposal", requires_dual_approval=False, legal_basis="legitimate_interest",
    )
    vals.update(kw)
    c = DataCategory(**vals)
    db.add(c)
    db.commit()
    return c


def _record(db, cat, ref, collected=TODAY, **kw):
    r = DataRecord(organization_id=1, category_id=cat.id, record_reference=ref,
                   collection_date=collected, status="active", **kw)
    r.category = cat
    calculate_retention_end_date(db, r)
    db.add(r)
    db.commit()
    return r


def _api_key(db, permissions):
    system = ConnectedSystem(organization_id=1, name="Google Forms", system_type="custom")
    db.add(system)
    db.commit()
    raw = "sd_test_" + "k" * 24
    db.add(ApiKey(organization_id=1, system_id=system.id, key_name="forms",
                  key_hash=hashlib.sha256(raw.encode()).hexdigest(), key_prefix=raw[:8],
                  permissions=permissions, rate_limit_per_min=600, is_active=True))
    db.commit()
    return {"Authorization": f"Bearer {raw}"}


# ── clock start per trigger ──


def test_collection_date_clock(db):
    cat = _category(db, retention_period_days=90)
    rec = _record(db, cat, "R1", collected=TODAY - timedelta(days=10))
    assert rec.retention_end_date == TODAY + timedelta(days=80)
    clock = retention_clock(rec, "date_based")
    assert clock["state"] == "running" and clock["days_left"] == 80 and clock["basis"] == "Collected"


def test_consent_clock_waits_then_starts_on_withdrawal(db):
    cat = _category(db, legal_basis="consent", disposal_trigger="consent_withdrawal", retention_period_days=14)
    rec = _record(db, cat, "C1")
    assert rec.retention_end_date is None
    assert retention_clock(rec, "consent_withdrawal")["state"] == "waiting"

    assert log_consent_withdrawal(db, 1, rec.id, actor_id=None)
    db.refresh(rec)
    assert rec.retention_end_date == TODAY + timedelta(days=14)


def test_consent_withdrawal_caps_a_long_consent_clock(db):
    cat = _category(db, legal_basis="consent", disposal_trigger="date_based", retention_period_days=3650)
    rec = _record(db, cat, "C2")
    assert rec.retention_end_date == TODAY + timedelta(days=3650)
    log_consent_withdrawal(db, 1, rec.id, actor_id=None)
    db.refresh(rec)
    assert rec.retention_end_date == TODAY + timedelta(days=30)  # default post-withdrawal window


def test_withdrawal_does_not_shorten_a_legal_obligation_record(db):
    cat = _category(db, legal_basis="legal_obligation", retention_period_days=2190)
    rec = _record(db, cat, "KYC-1")
    log_consent_withdrawal(db, 1, rec.id, actor_id=None)
    db.refresh(rec)
    assert rec.retention_end_date == TODAY + timedelta(days=2190)


def test_relationship_end_survives_recalculation(db):
    cat = _category(db, disposal_trigger="account_closure", retention_period_days=365)
    rec = _record(db, cat, "ACC-1")
    assert rec.retention_end_date is None
    rec.relationship_ended_on = TODAY - timedelta(days=5)
    calculate_retention_end_date(db, rec)
    db.commit()
    assert rec.retention_end_date == TODAY + timedelta(days=360)
    calculate_retention_end_date(db, rec)  # e.g. category edited later
    assert rec.retention_end_date == TODAY + timedelta(days=360)


# ── the engine acts on every clock type ──


def test_relationship_ended_records_are_disposed_when_due(db):
    cat = _category(db, disposal_trigger="account_closure", retention_period_days=30)
    rec = _record(db, cat, "ACC-2")
    rec.relationship_ended_on = TODAY - timedelta(days=40)
    calculate_retention_end_date(db, rec)
    db.commit()
    result = run_retention_checks(db, 1)
    db.refresh(rec)
    assert result["auto_disposed"] == 1 and rec.status == "disposed"


def test_consent_withdrawn_record_is_disposed_on_its_shown_date_not_before(db):
    cat = _category(db, legal_basis="consent", disposal_trigger="consent_withdrawal", retention_period_days=10)
    rec = _record(db, cat, "C3")
    rec.consent_withdrawn_at = datetime.now() - timedelta(days=5)
    calculate_retention_end_date(db, rec)
    db.commit()
    assert run_retention_checks(db, 1)["consent_disposed"] == 0  # 5 days still to go
    rec.consent_withdrawn_at = datetime.now() - timedelta(days=11)
    calculate_retention_end_date(db, rec)
    db.commit()
    assert run_retention_checks(db, 1)["consent_disposed"] == 1


def test_owner_is_told_once_when_records_become_due(db):
    owner = User(organization_id=1, name="Owner", email="owner@test.local", role="data_owner",
                 password_hash="x", is_active=True)
    db.add(owner)
    db.commit()
    cat = _category(db, retention_period_days=40, owner_id=owner.id, approval_type="single_approval")
    _record(db, cat, "SOON-1", collected=TODAY - timedelta(days=20))  # 20 days left, inside the 30-day window
    run_retention_checks(db, 1)
    run_retention_checks(db, 1)
    notes = db.query(Notification).filter(Notification.recipient_id == owner.id,
                                          Notification.type == "review_due").all()
    assert len(notes) == 1
    assert "SOON-1" in notes[0].message


# ── the Google Forms / API path ──


def test_api_ingest_then_consent_signal_starts_the_clock(client, db):
    cat = _category(db, legal_basis="consent", disposal_trigger="consent_withdrawal", retention_period_days=7)
    headers = _api_key(db, ["ingest", "consent", "read"])
    ref = hashlib.sha256(b"attendee@example.com").hexdigest()
    r = client.post("/api/v1/ingest", headers=headers,
                    json={"record_reference": ref, "category_id": cat.id, "collection_date": TODAY.isoformat()})
    assert r.status_code == 200, r.text
    rec = db.query(DataRecord).filter(DataRecord.record_reference == ref).one()
    assert rec.retention_end_date is None  # consent still given

    r = client.post("/api/v1/consent/signal", headers=headers, json={"record_reference": ref})
    assert r.status_code == 200, r.text
    db.expire_all()
    rec = db.query(DataRecord).filter(DataRecord.record_reference == ref).one()
    assert rec.retention_end_date == TODAY + timedelta(days=7)


def test_api_terminate_records_the_relationship_end_day(client, db):
    cat = _category(db, disposal_trigger="account_closure", retention_period_days=60)
    _record(db, cat, "CUST-9")
    headers = _api_key(db, ["terminate"])
    ended = TODAY - timedelta(days=10)
    r = client.post("/api/v1/records/terminate", headers=headers,
                    json={"external_ref": "CUST-9", "termination_date": ended.isoformat()})
    assert r.status_code == 200, r.text
    db.expire_all()
    rec = db.query(DataRecord).filter(DataRecord.record_reference == "CUST-9").one()
    assert rec.relationship_ended_on == ended
    assert rec.retention_end_date == ended + timedelta(days=60)


# ── the data collection page ──


def _admin_login(client, db):
    from app.auth import hash_password
    pw = "Correct-Horse-9-Battery"
    db.add(User(organization_id=1, name="Admin", email="admin@test.local", password_hash=hash_password(pw),
                role="admin", is_active=True, must_change_password=False))
    db.commit()
    assert client.post("/login", data={"email": "admin@test.local", "password": pw},
                       follow_redirects=False).status_code == 303


def test_data_collection_page_lists_every_held_record_with_its_countdown(client, db):
    _admin_login(client, db)
    long = _category(db, name="Invoices", retention_period_days=400)
    consent = _category(db, name="Webinar", legal_basis="consent", disposal_trigger="consent_withdrawal")
    _record(db, long, "INV-RUNNING")
    _record(db, long, "INV-SOON", collected=TODAY - timedelta(days=390))
    _record(db, long, "INV-OVERDUE", collected=TODAY - timedelta(days=402))
    _record(db, consent, "WEB-WAITING")

    page = client.get("/records").text
    for ref in ("INV-RUNNING", "INV-SOON", "INV-OVERDUE", "WEB-WAITING"):
        assert ref in page
    assert "400 days left" in page
    assert "10 days left" in page
    assert "2 days overdue" in page
    assert "Starts when consent is withdrawn" in page
    # soonest deletion first, not-started last
    assert page.index("INV-OVERDUE") < page.index("INV-SOON") < page.index("INV-RUNNING") < page.index("WEB-WAITING")

    soon = client.get("/records?status=soon").text
    assert "INV-SOON" in soon and "INV-RUNNING" not in soon and "INV-OVERDUE" not in soon
    waiting = client.get("/records?status=waiting").text
    assert "WEB-WAITING" in waiting and "INV-SOON" not in waiting


def test_legacy_closed_record_keeps_its_deletion_date(db):
    cat = _category(db, disposal_trigger="account_closure", retention_period_days=30)
    rec = _record(db, cat, "OLD-CLOSED")
    rec.retention_end_date = TODAY + timedelta(days=12)  # set by the old terminate path
    db.commit()
    calculate_retention_end_date(db, rec)
    assert rec.retention_end_date == TODAY + timedelta(days=12)
