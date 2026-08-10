from datetime import date, timedelta
from app.models import DataRecord, DataCategory
from app.engine import calculate_retention_end_date, run_retention_checks, execute_disposal

def test_retention_end_date_calculation(db):
    # Set up category
    cat = DataCategory(
        organization_id=1,
        name="Employee Personnel Records",
        compliance_framework="GDPR",
        legal_basis="legal_obligation",
        retention_period_days=365,
        retention_period_label="1 year",
        disposal_method="delete",
        disposal_trigger="date_based"
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)

    # Register active record
    coll_date = date(2025, 1, 1)
    record = DataRecord(
        organization_id=1,
        category_id=cat.id,
        record_reference="EMP-01",
        collection_date=coll_date,
        status="active"
    )
    calculate_retention_end_date(db, record)
    db.add(record)
    db.commit()

    # Assert end date is exactly 1 year after collection
    assert record.retention_end_date == date(2026, 1, 1)

def test_engine_skips_dual_approval_records(db):
    # Set up category requiring dual approval
    cat = DataCategory(
        organization_id=1,
        name="Sensitive Health Records",
        compliance_framework="GDPR",
        legal_basis="legal_obligation",
        retention_period_days=30,
        retention_period_label="30 days",
        disposal_method="delete",
        disposal_trigger="date_based",
        requires_dual_approval=True
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)

    # Register overdue record (flagged for review)
    coll_date = date(2026, 1, 1)
    record = DataRecord(
        organization_id=1,
        category_id=cat.id,
        record_reference="HLTH-99",
        collection_date=coll_date,
        status="due_review"
    )
    calculate_retention_end_date(db, record)
    db.add(record)
    db.commit()

    # Execute engine checks
    results = run_retention_checks(db, 1)

    # Assert overdue record was skipped from auto-disposal (safeguard)
    assert results["skipped_dual"] == 1
    assert results["auto_disposed"] == 0

    # Re-read status
    db.refresh(record)
    assert record.status == "due_review"
