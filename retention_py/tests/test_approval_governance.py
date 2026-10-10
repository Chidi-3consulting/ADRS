import pytest
from datetime import date, timedelta
from app.models import DataCategory, DataRecord, Organization
from app.engine import run_retention_checks

def test_approval_governance_tiers(db):
    org = db.get(Organization, 1)  # seeded by the db fixture

    # 1. Category with auto_disposal
    cat_auto = DataCategory(
        organization_id=org.id,
        name="Auto Disposal Cat",
        compliance_framework="POPIA",
        legal_basis="consent",
        retention_period_days=1,
        disposal_method="delete",
        disposal_trigger="date_based",
        data_classification="standard",
        approval_type="auto_disposal",
        requires_dual_approval=False
    )
    # 2. Category with single_approval
    cat_single = DataCategory(
        organization_id=org.id,
        name="Single Approval Cat",
        compliance_framework="POPIA",
        legal_basis="consent",
        retention_period_days=1,
        disposal_method="delete",
        disposal_trigger="date_based",
        data_classification="standard",
        approval_type="single_approval",
        requires_dual_approval=False
    )
    # 3. Category with dual_approval
    cat_dual = DataCategory(
        organization_id=org.id,
        name="Dual Approval Cat",
        compliance_framework="POPIA",
        legal_basis="legal_obligation",
        retention_period_days=1,
        disposal_method="delete",
        disposal_trigger="date_based",
        data_classification="special_category",
        approval_type="dual_approval",
        requires_dual_approval=True
    )
    db.add_all([cat_auto, cat_single, cat_dual])
    db.commit()

    # Create overdue records for each
    yesterday = date.today() - timedelta(days=5)
    r_auto = DataRecord(
        organization_id=org.id, category_id=cat_auto.id, record_reference="REF-AUTO-01",
        collection_date=yesterday, retention_end_date=yesterday, status="due_review"
    )
    r_single = DataRecord(
        organization_id=org.id, category_id=cat_single.id, record_reference="REF-SINGLE-01",
        collection_date=yesterday, retention_end_date=yesterday, status="due_review"
    )
    r_dual = DataRecord(
        organization_id=org.id, category_id=cat_dual.id, record_reference="REF-DUAL-01",
        collection_date=yesterday, retention_end_date=yesterday, status="due_review"
    )
    db.add_all([r_auto, r_single, r_dual])
    db.commit()

    # Run cycle
    results = run_retention_checks(db, org.id)

    db.refresh(r_auto)
    db.refresh(r_single)
    db.refresh(r_dual)

    # Assertions
    assert r_auto.status == "disposed"  # Auto disposal purged it!
    assert r_single.status == "due_review"  # Single approval waits for human click!
    assert r_dual.status == "due_review"  # Dual approval waits for two humans!

    # Cleanup
    db.delete(r_auto)
    db.delete(r_single)
    db.delete(r_dual)
    db.delete(cat_auto)
    db.delete(cat_single)
    db.delete(cat_dual)
    db.commit()
