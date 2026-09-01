"""
Tests for Bulk Safe Disposal of Due/Expired Records.
"""
import pytest
from datetime import date, timedelta
from app.models import User, Organization, DataCategory, DataRecord, AuditLog
from app.auth import hash_password
from app.engine import execute_disposal


@pytest.fixture
def setup_org_records(db):
    org = db.query(Organization).filter(Organization.id == 1).first()

    user = User(
        organization_id=org.id,
        email="admin.bulk@example.com",
        name="Bulk Admin",
        role="admin",
        password_hash=hash_password("AdminPass123!"),
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    cat_single = DataCategory(
        organization_id=org.id,
        name="Standard Webinar Leads",
        compliance_framework="POPIA",
        retention_period_days=2,
        requires_dual_approval=False,
        disposal_method="delete"
    )
    cat_dual = DataCategory(
        organization_id=org.id,
        name="Financial Tax Invoices",
        compliance_framework="POPIA",
        retention_period_days=1825,
        requires_dual_approval=True,
        disposal_method="delete"
    )
    db.add_all([cat_single, cat_dual])
    db.commit()
    db.refresh(cat_single)
    db.refresh(cat_dual)

    # 1. Expired record in single-approval category (eligible for instant purge)
    rec1 = DataRecord(
        organization_id=org.id,
        category_id=cat_single.id,
        record_reference="LEAD-001",
        collection_date=date.today() - timedelta(days=5),
        retention_end_date=date.today() - timedelta(days=3),
        status="active"
    )
    # 2. Expired record in single-approval category
    rec2 = DataRecord(
        organization_id=org.id,
        category_id=cat_single.id,
        record_reference="LEAD-002",
        collection_date=date.today() - timedelta(days=4),
        retention_end_date=date.today() - timedelta(days=2),
        status="active"
    )
    # 3. Record on LEGAL HOLD (must be skipped / protected)
    rec3_hold = DataRecord(
        organization_id=org.id,
        category_id=cat_single.id,
        record_reference="LEAD-003-HOLD",
        collection_date=date.today() - timedelta(days=10),
        retention_end_date=date.today() - timedelta(days=8),
        status="legal_hold",
        legal_hold=True
    )
    # 4. Record in dual-approval category (should transition to disposal_requested)
    rec4_dual = DataRecord(
        organization_id=org.id,
        category_id=cat_dual.id,
        record_reference="TAX-004",
        collection_date=date.today() - timedelta(days=2000),
        retention_end_date=date.today() - timedelta(days=175),
        status="active"
    )

    db.add_all([rec1, rec2, rec3_hold, rec4_dual])
    db.commit()
    db.refresh(rec1)
    db.refresh(rec2)
    db.refresh(rec3_hold)
    db.refresh(rec4_dual)

    return org, user, [rec1, rec2, rec3_hold, rec4_dual]


def test_bulk_disposal_execution(db, setup_org_records):
    org, user, records = setup_org_records
    rec1, rec2, rec3_hold, rec4_dual = records

    # Execute disposal on rec1 and rec2
    r1_res = execute_disposal(db, rec1.id, actor_id=user.id)
    r2_res = execute_disposal(db, rec2.id, actor_id=user.id)
    r3_res = execute_disposal(db, rec3_hold.id, actor_id=user.id)  # Should return False (on hold)

    assert r1_res is True
    assert r2_res is True
    assert r3_res is False

    db.refresh(rec1)
    db.refresh(rec2)
    db.refresh(rec3_hold)

    assert rec1.status == "disposed"
    assert rec2.status == "disposed"
    assert rec3_hold.status == "legal_hold"
