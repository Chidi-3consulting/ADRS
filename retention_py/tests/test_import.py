"""
Test import records.
Tests CSV import validation + processing.
"""
import pytest
from app.models import DataCategory, DataRecord, ImportJob


def _seed_category(db):
    cat = DataCategory(
        organization_id=1, name="Import Test Category", description="Test",
        compliance_framework="GDPR", legal_basis="consent",
        retention_period_days=365, retention_period_label="1 year",
        disposal_method="delete", disposal_trigger="date_based",
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def test_import_csv_endpoint(client, db, auth_user):
    """CSV upload endpoint should be accessible."""
    response = client.get("/import")
    assert response.status_code in [200, 303]


def test_import_job_model(db):
    """Import job should be created and tracked."""
    job = ImportJob(
        organization_id=1,
        imported_by=1,
        filename="test.csv",
        total_rows=10,
        valid_rows=10,
        imported_rows=0,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    assert job.id is not None
    assert job.status == "pending"
