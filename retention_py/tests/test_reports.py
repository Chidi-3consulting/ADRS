from app.core.clock import business_today
"""
Test reports.
Tests compliance report queries.
"""
import pytest
from app.models import DataRecord, DataCategory
from datetime import date, timedelta


def _seed_data(db):
    cat = DataCategory(
        organization_id=1, name="Report Category", description="Test",
        compliance_framework="GDPR", legal_basis="consent",
        retention_period_days=365, retention_period_label="1 year",
        disposal_method="delete", disposal_trigger="date_based",
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)

    for i in range(5):
        record = DataRecord(
            organization_id=1, category_id=cat.id,
            record_reference=f"RPT-{i:03d}", status="active",
            collection_date=business_today() - timedelta(days=30 * i),
            retention_end_date=business_today() + timedelta(days=365 - 30 * i),
        )
        db.add(record)

    disposed = DataRecord(
        organization_id=1, category_id=cat.id,
        record_reference="RPT-DISPOSED", status="disposed",
    )
    db.add(disposed)
    db.commit()
    return cat


def test_active_records_count(db):
    """Should correctly count active records for compliance reporting."""
    _seed_data(db)
    active = db.query(DataRecord).filter(
        DataRecord.organization_id == 1,
        DataRecord.status != "disposed",
        DataRecord.deleted_at == None,
    ).count()
    assert active == 5


def test_disposed_records_count(db):
    """Should correctly count disposed records."""
    _seed_data(db)
    disposed = db.query(DataRecord).filter(
        DataRecord.organization_id == 1,
        DataRecord.status == "disposed",
    ).count()
    assert disposed == 1


def test_overdue_records(db):
    """Should identify records past their retention end date."""
    cat = _seed_data(db)
    overdue = DataRecord(
        organization_id=1, category_id=cat.id,
        record_reference="OVERDUE-001", status="active",
        retention_end_date=business_today() - timedelta(days=30),
    )
    db.add(overdue)
    db.commit()

    overdue_count = db.query(DataRecord).filter(
        DataRecord.organization_id == 1,
        DataRecord.status != "disposed",
        DataRecord.retention_end_date < business_today(),
    ).count()
    assert overdue_count >= 1
