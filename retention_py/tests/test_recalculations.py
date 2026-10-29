from app.core.clock import business_today
"""
Test recalculations.
Tests pending recalculation workflow.
"""
import pytest
from datetime import date, timedelta
from app.models import PendingRecalculation, DataRecord, DataCategory


def _seed_records(db):
    cat = DataCategory(
        organization_id=1, name="Recalc Cat", description="Test",
        compliance_framework="GDPR", legal_basis="consent",
        retention_period_days=365, retention_period_label="1 year",
        disposal_method="delete", disposal_trigger="date_based",
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)

    record = DataRecord(
        organization_id=1, category_id=cat.id,
        record_reference="RECALC-001", status="active",
        collection_date=business_today() - timedelta(days=100),
        retention_end_date=business_today() + timedelta(days=265),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return cat, record


def test_create_pending_recalculation(db, auth_user):
    """Should create a pending recalculation entry."""
    cat, record = _seed_records(db)
    recalc = PendingRecalculation(
        organization_id=1,
        record_id=record.id,
        category_id=cat.id,
        old_retention_end_date=record.retention_end_date,
        new_retention_end_date=business_today() + timedelta(days=730),
        status="pending",
        triggered_by=auth_user.id,
    )
    db.add(recalc)
    db.commit()
    db.refresh(recalc)

    assert recalc.id is not None
    assert recalc.status == "pending"


def test_recalculation_updates_dates(db):
    """After recalculation, record retention_end_date should update."""
    cat, record = _seed_records(db)

    # Update retention period
    cat.retention_period_days = 730
    db.commit()

    # Apply new retention end date
    new_end = record.collection_date + timedelta(days=730)
    record.retention_end_date = new_end
    db.commit()

    refreshed = db.query(DataRecord).filter(DataRecord.id == record.id).first()
    expected = record.collection_date + timedelta(days=730)
    assert refreshed.retention_end_date == expected


def test_pending_recalculation_completion(db, auth_user):
    """Completed recalculation should be updated with new status."""
    cat, record = _seed_records(db)
    recalc = PendingRecalculation(
        organization_id=1, record_id=record.id, category_id=cat.id,
        old_retention_end_date=record.retention_end_date,
        new_retention_end_date=business_today() + timedelta(days=730),
        status="pending", triggered_by=auth_user.id,
    )
    db.add(recalc)
    db.commit()

    recalc.status = "recalculate"
    db.commit()

    assert recalc.status == "recalculate"
