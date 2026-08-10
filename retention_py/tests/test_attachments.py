"""
Test attachments — ported from PHP attachments_test.php.
Tests attachment model operations.
"""
import pytest
from app.models import Attachment, DataRecord, DataCategory


def _seed_record(db):
    cat = DataCategory(
        organization_id=1, name="Attachment Cat", description="Test",
        compliance_framework="GDPR", legal_basis="consent",
        retention_period_days=365, retention_period_label="1 year",
        disposal_method="delete", disposal_trigger="date_based",
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)

    record = DataRecord(
        organization_id=1, category_id=cat.id,
        record_reference="ATT-001", status="active",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def test_create_attachment(db):
    """Should create an attachment linked to a record."""
    record = _seed_record(db)
    att = Attachment(
        organization_id=1,
        record_id=record.id,
        original_filename="document.pdf",
        stored_filename="uuid_document.pdf",
        file_size=1024,
        mime_type="application/pdf",
        uploaded_by=1,
    )
    db.add(att)
    db.commit()
    db.refresh(att)

    assert att.id is not None
    assert att.original_filename == "document.pdf"


def test_list_attachments_for_record(db):
    """Should list all attachments for a specific record."""
    record = _seed_record(db)
    for i in range(3):
        db.add(Attachment(
            organization_id=1, record_id=record.id,
            original_filename=f"file_{i}.txt",
            stored_filename=f"stored_{i}.txt",
            file_size=100 * (i + 1), mime_type="text/plain", uploaded_by=1,
        ))
    db.commit()

    atts = db.query(Attachment).filter(Attachment.record_id == record.id).all()
    assert len(atts) == 3


def test_allowed_extensions():
    """Should validate allowed file extensions."""
    from app.routes.records import ALLOWED_EXTENSIONS
    assert "pdf" in ALLOWED_EXTENSIONS
    assert "exe" not in ALLOWED_EXTENSIONS
    assert "csv" in ALLOWED_EXTENSIONS
