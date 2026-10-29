from app.core.clock import business_today
"""
Test records CRUD.
Tests record creation, editing, listing, and filtering.
"""
import pytest
from datetime import date, timedelta
from app.models import DataRecord, DataCategory


def _seed_category(db):
    cat = DataCategory(
        organization_id=1, name="Records Test Cat", description="For testing",
        compliance_framework="GDPR", legal_basis="contract",
        retention_period_days=730, retention_period_label="2 years",
        disposal_method="delete", disposal_trigger="date_based",
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def test_create_record(db):
    """Should create a data record with all required fields."""
    cat = _seed_category(db)
    record = DataRecord(
        organization_id=1, category_id=cat.id,
        record_reference="REC-001",
        data_subject_type="employee",
        collection_date=business_today(),
        retention_end_date=business_today() + timedelta(days=730),
        status="active",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    assert record.id is not None
    assert record.status == "active"
    assert record.record_reference == "REC-001"


def test_edit_record(db):
    """Should be able to update record fields."""
    cat = _seed_category(db)
    record = DataRecord(
        organization_id=1, category_id=cat.id,
        record_reference="EDIT-001", status="active",
    )
    db.add(record)
    db.commit()

    record.notes = "Updated notes"
    record.data_subject_type = "customer"
    db.commit()

    refreshed = db.query(DataRecord).filter(DataRecord.id == record.id).first()
    assert refreshed.notes == "Updated notes"
    assert refreshed.data_subject_type == "customer"


def test_filter_by_status(db):
    """Should filter records by status."""
    cat = _seed_category(db)
    for i, status in enumerate(["active", "active", "due_review", "disposed"]):
        db.add(DataRecord(
            organization_id=1, category_id=cat.id,
            record_reference=f"FILTER-{i}", status=status,
        ))
    db.commit()

    active = db.query(DataRecord).filter(DataRecord.status == "active").count()
    assert active == 2

    disposed = db.query(DataRecord).filter(DataRecord.status == "disposed").count()
    assert disposed == 1


def test_filter_by_category(db):
    """Should filter records by category_id."""
    cat1 = _seed_category(db)
    cat2 = DataCategory(
        organization_id=1, name="Other Cat", description="Other",
        compliance_framework="NDPR", legal_basis="consent",
        retention_period_days=365, retention_period_label="1 year",
        disposal_method="delete", disposal_trigger="date_based",
    )
    db.add(cat2)
    db.commit()
    db.refresh(cat2)

    db.add(DataRecord(organization_id=1, category_id=cat1.id, record_reference="CAT1-001", status="active"))
    db.add(DataRecord(organization_id=1, category_id=cat2.id, record_reference="CAT2-001", status="active"))
    db.commit()

    cat1_records = db.query(DataRecord).filter(DataRecord.category_id == cat1.id).count()
    assert cat1_records == 1


def test_search_by_reference(db):
    """Should find records by reference search."""
    cat = _seed_category(db)
    db.add(DataRecord(organization_id=1, category_id=cat.id, record_reference="SEARCH-ABC", status="active"))
    db.add(DataRecord(organization_id=1, category_id=cat.id, record_reference="SEARCH-XYZ", status="active"))
    db.commit()

    results = db.query(DataRecord).filter(DataRecord.record_reference.like("%ABC%")).all()
    assert len(results) == 1
    assert results[0].record_reference == "SEARCH-ABC"
