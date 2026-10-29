from app.core.clock import business_today
import pytest
from datetime import date, timedelta, datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    Organization, User, DataCategory, DataRecord,
    AuditLog, SystemSetting,
)
from app.auth import hash_password
from app.engine import (
    run_retention_checks,
    request_disposal,
    approve_disposal,
    verify_audit_chain,
    compliance_scorecard_details,
    upcoming_deadlines,
    disposals_by_month,
    compliance_metrics,
)
from app.helpers import log_audit


@pytest.fixture(scope="module")
def e2e_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(SystemSetting(setting_key="setup_complete", setting_value="1"))
    db.commit()
    yield db
    db.close()


@pytest.fixture(scope="module")
def e2e_org(e2e_db):
    org = Organization(
        name="E2E Test Corp",
        slug="e2e-test-corp",
        primary_domain="e2e-test.com",
        country="GB",
        status="active",
    )
    e2e_db.add(org)
    e2e_db.commit()
    e2e_db.refresh(org)
    return org


@pytest.fixture(scope="module")
def e2e_admin(e2e_db, e2e_org):
    admin = User(
        organization_id=e2e_org.id, name="E2E Admin", email="admin@e2e-test.com",
        password_hash=hash_password("Str0ng!Pass#99"), role="admin", is_active=True,
        email_verified_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    e2e_db.add(admin)
    e2e_db.commit()
    e2e_db.refresh(admin)
    return admin


@pytest.fixture(scope="module")
def e2e_dpo(e2e_db, e2e_org):
    dpo = User(
        organization_id=e2e_org.id, name="E2E DPO", email="dpo@e2e-test.com",
        password_hash=hash_password("Str0ng!Pass#99"), role="dpo", is_active=True,
        email_verified_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    e2e_db.add(dpo)
    e2e_db.commit()
    e2e_db.refresh(dpo)
    return dpo


class TestE2ERetentionWorkflow:

    def test_01_create_standard_category(self, e2e_db, e2e_org):
        """Create a standard delete category (single approval)."""
        cat = DataCategory(
            organization_id=e2e_org.id,
            name="Customer HR Records",
            compliance_framework="UK_GDPR",
            retention_period_days=365,
            retention_period_label="1 year",
            disposal_method="delete",
            disposal_trigger="date_based",
            processing_role="controller",
            requires_dual_approval=False,
        )
        e2e_db.add(cat)
        e2e_db.commit()
        e2e_db.refresh(cat)
        assert cat.id is not None
        assert not cat.requires_dual_approval

    def test_02_create_dual_approval_category(self, e2e_db, e2e_org):
        """Create a sensitive category requiring dual-approval for disposal."""
        cat = DataCategory(
            organization_id=e2e_org.id,
            name="Medical Records",
            compliance_framework="UK_GDPR",
            retention_period_days=2557,
            retention_period_label="7 years",
            disposal_method="anonymise",
            disposal_trigger="date_based",
            processing_role="controller",
            requires_dual_approval=True,
        )
        e2e_db.add(cat)
        e2e_db.commit()
        e2e_db.refresh(cat)
        assert cat.requires_dual_approval is True

    def test_03_create_overdue_record(self, e2e_db, e2e_org):
        """Intake a record 2 days past its retention end date."""
        cat = e2e_db.query(DataCategory).filter(
            DataCategory.organization_id == e2e_org.id,
            DataCategory.requires_dual_approval == False,
        ).first()
        record = DataRecord(
            organization_id=e2e_org.id,
            category_id=cat.id,
            record_reference="E2E-HR-001",
            data_subject_type="employee",
            collection_date=business_today() - timedelta(days=367),
            retention_end_date=business_today() - timedelta(days=2),
            status="active",
            legal_hold=False,
        )
        e2e_db.add(record)
        e2e_db.commit()
        assert record.retention_end_date < business_today()

    def test_04_create_upcoming_record(self, e2e_db, e2e_org):
        """Create a record approaching deadline in 10 days."""
        cat = e2e_db.query(DataCategory).filter(
            DataCategory.organization_id == e2e_org.id,
            DataCategory.requires_dual_approval == False,
        ).first()
        record = DataRecord(
            organization_id=e2e_org.id,
            category_id=cat.id,
            record_reference="E2E-HR-002",
            data_subject_type="employee",
            collection_date=business_today() - timedelta(days=355),
            retention_end_date=business_today() + timedelta(days=10),
            status="active",
            legal_hold=False,
        )
        e2e_db.add(record)
        e2e_db.commit()
        assert record.retention_end_date > business_today()

    def test_05_create_dual_approval_record(self, e2e_db, e2e_org):
        """Create a record that needs dual approval for disposal."""
        med_cat = e2e_db.query(DataCategory).filter(
            DataCategory.organization_id == e2e_org.id,
            DataCategory.requires_dual_approval == True,
        ).first()
        record = DataRecord(
            organization_id=e2e_org.id,
            category_id=med_cat.id,
            record_reference="E2E-MED-001",
            data_subject_type="patient",
            collection_date=business_today() - timedelta(days=2557),
            retention_end_date=business_today() - timedelta(days=5),
            status="active",
            legal_hold=False,
        )
        e2e_db.add(record)
        e2e_db.commit()
        e2e_db.refresh(record)
        assert record.category.requires_dual_approval is True

    def test_06_retention_engine_flags_overdue(self, e2e_db, e2e_org):
        """The retention engine should flag overdue records as due_review."""
        results = run_retention_checks(e2e_db, e2e_org.id)
        assert results.get("flagged", 0) >= 1, f"Expected flagged>=1, got: {results}"
        overdue = e2e_db.query(DataRecord).filter(
            DataRecord.organization_id == e2e_org.id,
            DataRecord.record_reference == "E2E-HR-001",
        ).first()
        assert overdue.status == "due_review", f"Expected due_review, got {overdue.status}"

    def test_07_upcoming_deadlines_dict_keys(self, e2e_db, e2e_org):
        """upcoming_deadlines() should return correct dict keys (B2 regression)."""
        deadlines = upcoming_deadlines(e2e_db, e2e_org.id)
        assert isinstance(deadlines, list)
        refs = [d["reference"] for d in deadlines]
        assert "E2E-HR-002" in refs, f"E2E-HR-002 not found in: {refs}"
        for item in deadlines:
            for key in ("record_id", "reference", "category", "due_date",
                        "days_remaining", "days_left", "status", "retention_end_date"):
                assert key in item, f"Missing key: {key} in {item}"

    def test_08_compliance_metrics(self, e2e_db, e2e_org):
        """compliance_metrics() should return valid counts."""
        metrics = compliance_metrics(e2e_db, e2e_org.id)
        assert isinstance(metrics, dict)
        assert metrics.get("due_review", 0) >= 1, f"Should have due_review records: {metrics}"

    def test_09_disposals_by_month_has_label(self, e2e_db, e2e_org):
        """disposals_by_month() should return 12 months with 'label' key (P5/S2 regression)."""
        chart = disposals_by_month(e2e_db, e2e_org.id, months=12)
        assert len(chart) == 12, f"Expected 12 months, got {len(chart)}"
        for entry in chart:
            assert "label" in entry, f"Missing label key: {entry}"
            assert "count" in entry
            assert isinstance(entry["count"], int)

    def test_10_single_approval_disposal(self, e2e_db, e2e_org, e2e_admin):
        """Single-approval category record disposes immediately on request."""
        record = e2e_db.query(DataRecord).filter(
            DataRecord.organization_id == e2e_org.id,
            DataRecord.record_reference == "E2E-HR-001",
        ).first()
        result = request_disposal(e2e_db, e2e_org.id, record.id, e2e_admin.id, "127.0.0.1")
        assert result["status"] == "disposed", f"Expected disposed, got: {result}"
        e2e_db.refresh(record)
        assert record.status == "disposed"
        assert record.disposed_by == e2e_admin.id

    def test_11_dual_approval_goes_to_pending(self, e2e_db, e2e_org, e2e_admin):
        """Dual-approval category goes to disposal_requested on first request."""
        record = e2e_db.query(DataRecord).filter(
            DataRecord.organization_id == e2e_org.id,
            DataRecord.record_reference == "E2E-MED-001",
        ).first()
        result = request_disposal(e2e_db, e2e_org.id, record.id, e2e_admin.id, "127.0.0.1")
        assert result["status"] == "pending_approval", f"Expected pending_approval, got: {result}"
        e2e_db.refresh(record)
        assert record.status == "disposal_requested"
        assert record.disposal_requested_by == e2e_admin.id

    def test_12_same_user_cannot_approve_own_request(self, e2e_db, e2e_org, e2e_admin):
        """B5 safeguard: same user cannot approve their own disposal request."""
        record = e2e_db.query(DataRecord).filter(
            DataRecord.organization_id == e2e_org.id,
            DataRecord.record_reference == "E2E-MED-001",
        ).first()
        result = approve_disposal(e2e_db, e2e_org.id, record.id, e2e_admin.id, "127.0.0.1")
        assert result.get("status") == "error", f"B5 safeguard failed - got: {result}"
        e2e_db.refresh(record)
        assert record.status == "disposal_requested", "Record should still be pending"

    def test_13_second_approver_completes_disposal(self, e2e_db, e2e_org, e2e_admin, e2e_dpo):
        """DPO (different user) approves disposal - record should be disposed."""
        record = e2e_db.query(DataRecord).filter(
            DataRecord.organization_id == e2e_org.id,
            DataRecord.record_reference == "E2E-MED-001",
        ).first()
        result = approve_disposal(e2e_db, e2e_org.id, record.id, e2e_dpo.id, "127.0.0.1")
        assert result["status"] == "disposed", f"Expected disposed, got: {result}"
        e2e_db.refresh(record)
        assert record.status == "disposed"
        assert record.disposed_at is not None

    def test_14_legal_hold_set_and_blocks_disposal(self, e2e_db, e2e_org, e2e_admin):
        """Legal hold prevents disposal and blocks disposal requests."""
        cat = e2e_db.query(DataCategory).filter(
            DataCategory.organization_id == e2e_org.id,
        ).first()
        record = DataRecord(
            organization_id=e2e_org.id,
            category_id=cat.id,
            record_reference="E2E-HOLD-001",
            data_subject_type="employee",
            collection_date=business_today() - timedelta(days=400),
            retention_end_date=business_today() - timedelta(days=30),
            status="active",
            legal_hold=False,
        )
        e2e_db.add(record)
        e2e_db.commit()
        e2e_db.refresh(record)

        # Set legal hold directly (mimics what the route handler does)
        record.legal_hold = True
        record.legal_hold_reason = "Litigation hold - do not dispose"
        record.legal_hold_by = e2e_admin.id
        record.legal_hold_at = datetime.now(timezone.utc).replace(tzinfo=None)
        e2e_db.commit()
        e2e_db.refresh(record)

        assert record.legal_hold is True
        assert "Litigation" in record.legal_hold_reason

        # Legal hold must block disposal
        result = request_disposal(e2e_db, e2e_org.id, record.id, e2e_admin.id, "127.0.0.1")
        assert result.get("status") in ("error", "legal_hold"), f"Expected blocked, got: {result}"

        e2e_db.refresh(record)
        assert record.status != "disposed", "Legal-hold record must not be disposed"

    def test_15_lift_hold_and_dispose(self, e2e_db, e2e_org, e2e_admin):
        """After lifting legal hold, disposal should succeed normally."""
        record = e2e_db.query(DataRecord).filter(
            DataRecord.organization_id == e2e_org.id,
            DataRecord.record_reference == "E2E-HOLD-001",
        ).first()

        # Lift the legal hold directly
        record.legal_hold = False
        record.legal_hold_lifted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        record.status = "due_review"
        e2e_db.commit()
        e2e_db.refresh(record)
        assert record.legal_hold is False

        result = request_disposal(e2e_db, e2e_org.id, record.id, e2e_admin.id, "127.0.0.1")
        assert result["status"] == "disposed", f"Expected disposed after hold lifted, got: {result}"
        e2e_db.refresh(record)
        assert record.status == "disposed"

    def test_16_audit_chain_intact(self, e2e_db, e2e_org):
        """Audit chain should be cryptographically intact after all operations."""
        result = verify_audit_chain(e2e_db, org_id=e2e_org.id)
        assert result["ok"] is True, f"Chain broken at: {result.get('first_broken_log_id')}"
        assert result["checked"] >= 0

    def test_17_audit_log_has_disposal_entries(self, e2e_db, e2e_org):
        """Audit log must record disposal events."""
        logs = e2e_db.query(AuditLog).filter(
            AuditLog.organization_id == e2e_org.id
        ).all()
        actions = {log.action for log in logs}
        assert any(
            a.startswith("record_disposed") or a == "disposal_requested" for a in actions
        ), f"No disposal action audited. Found: {actions}"

    def test_18_compliance_scorecard_valid(self, e2e_db, e2e_org):
        """Compliance scorecard should return valid structure and grade."""
        scorecard = compliance_scorecard_details(e2e_db, e2e_org.id)
        assert isinstance(scorecard, dict)
        assert 0 <= scorecard["overall_score"] <= 100
        assert scorecard["grade"] in ("A", "B", "C", "D", "F")
        assert "pillars" in scorecard
        for name, pillar in scorecard["pillars"].items():
            assert 0 <= pillar["score"] <= 100, f"Pillar {name!r} score out of range: {pillar}"

    def test_19_final_disposed_count(self, e2e_db, e2e_org):
        """All expected records should be disposed by end of workflow."""
        from sqlalchemy import func
        disposed = e2e_db.query(func.count(DataRecord.id)).filter(
            DataRecord.organization_id == e2e_org.id,
            DataRecord.status == "disposed",
        ).scalar()
        assert disposed >= 3, f"Expected >=3 disposed records, got {disposed}"

    def test_20_upcoming_record_still_active(self, e2e_db, e2e_org):
        """E2E-HR-002 (10 days away) should not have been disposed."""
        record = e2e_db.query(DataRecord).filter(
            DataRecord.organization_id == e2e_org.id,
            DataRecord.record_reference == "E2E-HR-002",
        ).first()
        assert record is not None
        assert record.status in ("active", "due_review"), (
            f"E2E-HR-002 should be active/due_review, got {record.status}"
        )
