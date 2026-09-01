import pytest
from datetime import datetime, date, timedelta, timezone
from app.models import (
    DataCategory, DataRecord, User, Notification, LoginAttempt, PasswordReset
)
from app.engine import (
    run_retention_checks, execute_disposal, run_housekeeping,
    run_quarterly_review, verify_audit_chain, create_notification,
    notify_role, engine_send_follow_ups
)
from app.helpers import log_audit


def test_b5_dual_approval_safeguard(db):
    """
    CRITICAL B5 SAFEGUARD: Overdue records in categories requiring dual approval
    must NEVER be auto-disposed by the daily retention engine.
    """
    # Create category with requires_dual_approval = 1
    cat = DataCategory(
        organization_id=1,
        name="Sensitive HR Records",
        compliance_framework="GDPR",
        retention_period_days=30,
        disposal_method="delete",
        disposal_trigger="date_based",
        requires_dual_approval=True
    )
    db.add(cat)
    db.commit()

    # Create an overdue record flagged due_review
    past_date = date.today() - timedelta(days=40)
    rec = DataRecord(
        organization_id=1,
        category_id=cat.id,
        record_reference="HR-001",
        data_subject_type="employee",
        collection_date=past_date,
        retention_end_date=past_date,
        status="due_review",
        review_flagged_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
    )
    db.add(rec)
    db.commit()

    # Run engine
    results = run_retention_checks(db, org_id=1)

    db.refresh(rec)
    # Status MUST still be due_review (skipped due to dual approval)
    assert rec.status == "due_review"
    assert results["skipped_dual"] == 1
    assert results["auto_disposed"] == 0


def test_auto_disposal_standard_category(db):
    """Standard categories (dual_approval=False) ARE auto-disposed when overdue."""
    cat = DataCategory(
        organization_id=1,
        name="Standard Logs",
        compliance_framework="NDPA",
        retention_period_days=30,
        disposal_method="delete",
        disposal_trigger="date_based",
        requires_dual_approval=False
    )
    db.add(cat)
    db.commit()

    past_date = date.today() - timedelta(days=40)
    rec = DataRecord(
        organization_id=1,
        category_id=cat.id,
        record_reference="LOG-001",
        data_subject_type="system",
        collection_date=past_date,
        retention_end_date=past_date,
        status="due_review",
        review_flagged_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
    )
    db.add(rec)
    db.commit()

    results = run_retention_checks(db, org_id=1)
    db.refresh(rec)
    assert rec.status == "disposed"
    assert results["auto_disposed"] == 1


def test_housekeeping(db):
    """Housekeeping prunes old login attempts, password resets, and read notifications."""
    old_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
    
    # Old login attempt
    la = LoginAttempt(email="test@test.com", ip_address="127.0.0.1", success=False, created_at=old_date)
    db.add(la)

    # Old expired password reset
    pr = PasswordReset(email="test@test.com", token_hash="abc", expires_at=old_date, used=True)
    db.add(pr)

    db.commit()

    hk = run_housekeeping(db)
    assert hk["login_attempts"] >= 1
    assert hk["password_resets"] >= 1


def test_quarterly_review(db):
    res = run_quarterly_review(db, org_id=1)
    assert "total_categories" in res
    assert "on_legal_hold" in res
    assert "disposed_quarter" in res


def test_audit_chain_verification(db):
    log_audit(db, 1, "test_action", "system", 1, 1, {"foo": "bar"}, "127.0.0.1")
    res = verify_audit_chain(db, org_id=1)
    assert res["ok"] is True
    assert res["checked"] >= 1
