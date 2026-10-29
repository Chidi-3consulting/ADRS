from app.core.clock import business_today
"""
Tests for Emergency Disposal Freeze, Dry-Run Simulation, and Anti-Self-Approval Safeguards.
"""
import pytest
from datetime import date, timedelta
from app.models import User, Organization, DataCategory, DataRecord, AuditLog, SystemSetting
from app.engine import execute_disposal, run_retention_checks, is_disposal_frozen


@pytest.fixture
def freeze_test_setup(db):
    org = db.query(Organization).filter(Organization.id == 1).first()

    user_a = User(
        organization_id=org.id,
        email="compliance.a@example.com",
        name="Officer A",
        role="dpo",
        password_hash="fake_hash",
        is_active=True
    )
    user_b = User(
        organization_id=org.id,
        email="compliance.b@example.com",
        name="Officer B",
        role="admin",
        password_hash="fake_hash",
        is_active=True
    )
    cat = DataCategory(
        organization_id=org.id,
        name="Freeze Test Category",
        compliance_framework="GDPR",
        retention_period_days=1,
        disposal_method="delete",
        disposal_trigger="date_based",
        data_classification="standard",
        approval_type="auto_disposal",
        requires_dual_approval=False
    )
    db.add_all([user_a, user_b, cat])
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)
    db.refresh(cat)

    rec = DataRecord(
        organization_id=org.id,
        category_id=cat.id,
        record_reference="FREEZE-REC-001",
        collection_date=business_today() - timedelta(days=10),
        retention_end_date=business_today() - timedelta(days=5),
        status="due_review"
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    return org, user_a, user_b, cat, rec


def test_dry_run_simulation(db, freeze_test_setup):
    org, user_a, _, cat, rec = freeze_test_setup

    # Dry-run execution
    result = execute_disposal(db, rec.id, actor_id=user_a.id, dry_run=True)
    assert result is True

    # Record must NOT be modified
    db.refresh(rec)
    assert rec.status == "due_review"
    assert rec.deleted_at is None
    assert rec.disposed_at is None


def test_emergency_freeze_blocks_disposal(db, freeze_test_setup):
    org, user_a, _, cat, rec = freeze_test_setup

    # Activate emergency freeze
    freeze_setting = SystemSetting(setting_key="disposal_freeze", setting_value="1")
    db.add(freeze_setting)
    db.commit()

    assert is_disposal_frozen(db, org.id) is True

    # Attempt disposal
    result = execute_disposal(db, rec.id, actor_id=user_a.id)
    assert result is False

    # Verify record remained untouched
    db.refresh(rec)
    assert rec.status == "due_review"

    # Verify audit log entry
    audit = db.query(AuditLog).filter(
        AuditLog.action == "disposal_aborted_freeze",
        AuditLog.entity_id == rec.id
    ).first()
    assert audit is not None

    # Deactivate freeze
    freeze_setting.setting_value = "0"
    db.commit()
    assert is_disposal_frozen(db, org.id) is False

    # Now disposal should succeed
    success = execute_disposal(db, rec.id, actor_id=user_a.id)
    assert success is True
    db.refresh(rec)
    assert rec.status == "disposed"


def test_run_retention_checks_respects_freeze_and_dryrun(db, freeze_test_setup):
    org, _, _, cat, rec = freeze_test_setup

    # Reset record to due_review
    rec.status = "due_review"
    rec.deleted_at = None
    rec.disposed_at = None
    db.commit()

    # 1. Test dry_run in retention checks
    res_dry = run_retention_checks(db, org.id, dry_run=True)
    assert res_dry["dry_run"] is True
    assert res_dry["auto_disposed"] >= 1
    db.refresh(rec)
    assert rec.status == "due_review"  # Unchanged!

    # 2. Test emergency freeze in retention checks
    freeze = db.query(SystemSetting).filter(SystemSetting.setting_key == "disposal_freeze").first()
    if not freeze:
        freeze = SystemSetting(setting_key="disposal_freeze", setting_value="1")
        db.add(freeze)
    else:
        freeze.setting_value = "1"
    db.commit()

    res_frozen = run_retention_checks(db, org.id, dry_run=False)
    assert res_frozen["disposal_frozen"] is True
    assert res_frozen["skipped_frozen"] >= 1
    assert res_frozen["auto_disposed"] == 0
    db.refresh(rec)
    assert rec.status == "due_review"  # Kept safe!

    # Reset freeze
    freeze.setting_value = "0"
    db.commit()
