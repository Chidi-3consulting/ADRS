"""
Test audit chain integrity.
Tests the SHA-256 hash chain write + verification.
"""
import pytest
from app.helpers import log_audit
from app.engine import verify_audit_chain
from app.models import AuditLog


def test_audit_chain_single_entry(db, auth_user):
    """Single audit log entry should verify correctly."""
    log_audit(db, 1, "test_action", "test_entity", 1, auth_user.id, {"key": "value"}, "127.0.0.1")

    result = verify_audit_chain(db, org_id=1)
    assert result["ok"] is True
    assert result["checked"] == 1
    assert result["broken_at"] is None


def test_audit_chain_multiple_entries(db, auth_user):
    """Multiple sequential audit log entries should all verify."""
    for i in range(5):
        log_audit(db, 1, f"action_{i}", "test_entity", i, auth_user.id, {"step": i}, "127.0.0.1")

    result = verify_audit_chain(db, org_id=1)
    assert result["ok"] is True
    assert result["checked"] == 5


def test_audit_chain_tamper_detection(db, auth_user):
    """Tampering with a row hash should break the chain."""
    log_audit(db, 1, "action_1", "test", 1, auth_user.id, {"a": "b"}, "127.0.0.1")
    log_audit(db, 1, "action_2", "test", 2, auth_user.id, {"c": "d"}, "127.0.0.1")

    # Tamper with first log's hash
    first_log = db.query(AuditLog).order_by(AuditLog.id.asc()).first()
    first_log.row_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    db.commit()

    result = verify_audit_chain(db)
    assert result["ok"] is False


def test_audit_chain_prev_hash_links(db, auth_user):
    """Each entry's prev_hash should reference the preceding entry's row_hash."""
    log_audit(db, 1, "first", "test", 1, auth_user.id, {}, "127.0.0.1")
    log_audit(db, 1, "second", "test", 2, auth_user.id, {}, "127.0.0.1")

    logs = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    assert len(logs) == 2
    assert logs[1].prev_hash == logs[0].row_hash


def test_audit_empty_chain(db):
    """Empty audit chain should verify ok with 0 checked."""
    result = verify_audit_chain(db)
    assert result["ok"] is True
    assert result["checked"] == 0
