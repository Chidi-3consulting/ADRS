from app.core.clock import business_today
import pytest
from datetime import datetime, date, timedelta
from app.models import DataCategory, DataRecord, User
from app.engine import execute_disposal


def test_legal_hold_blocks_disposal(db):
    cat = DataCategory(
        organization_id=1,
        name="Customer PII",
        compliance_framework="GDPR",
        retention_period_days=30,
        disposal_method="delete",
        disposal_trigger="date_based",
        requires_dual_approval=False
    )
    db.add(cat)
    db.commit()

    rec = DataRecord(
        organization_id=1,
        category_id=cat.id,
        record_reference="CUST-001",
        data_subject_type="customer",
        collection_date=business_today(),
        status="due_review",
        legal_hold=True,
        legal_hold_reason="Pending Litigation"
    )
    db.add(rec)
    db.commit()

    # execute_disposal must return False for legal hold
    disposed = execute_disposal(db, rec.id, actor_id=1)
    assert disposed is False
    db.refresh(rec)
    assert rec.status == "due_review"


def test_record_lifecycle_flow(client, auth_user, db):
    cat = DataCategory(
        organization_id=1,
        name="Financial Records",
        compliance_framework="NDPA",
        retention_period_days=365,
        disposal_method="anonymise",
        disposal_trigger="date_based",
        requires_dual_approval=False
    )
    db.add(cat)
    db.commit()

    rec = DataRecord(
        organization_id=1,
        category_id=cat.id,
        record_reference="FIN-100",
        data_subject_type="client",
        collection_date=business_today(),
        status="active"
    )
    db.add(rec)
    db.commit()

    # Assert record is created and active
    assert rec.status == "active"
    assert rec.record_reference == "FIN-100"
