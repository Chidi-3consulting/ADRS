"""
Test backups.
Tests database backup and pruning against the object-storage API.
"""
import os
from datetime import timedelta

from app.backups import backup_database, prune_backups
from app.core.clock import utcnow
from app.core.storage import LocalStorage
from app.models import BackupLog


def test_backup_creates_object(db, tmp_path):
    """Backup should write an object to storage and log it."""
    storage = LocalStorage(str(tmp_path))
    result = backup_database(db, storage)

    assert result["status"] == "success"
    assert result["key"].startswith("backups/")
    assert result["size"] > 0
    assert [k for k, _ in storage.list("backups/")] == [result["key"]]
    assert db.query(BackupLog).filter(BackupLog.filename == result["key"], BackupLog.status == "success").count() == 1


def test_backup_object_content(db, tmp_path):
    """Unencrypted backup object should contain the dump."""
    storage = LocalStorage(str(tmp_path))
    result = backup_database(db, storage)

    content = storage.get(result["key"])
    if db.get_bind().dialect.name == "sqlite":
        assert b"CREATE TABLE" in content or b"INSERT" in content
    else:
        assert content.startswith(b"PGDMP")


def test_prune_removes_old_objects(db, tmp_path):
    """Prune should remove objects (and log rows) older than specified days."""
    storage = LocalStorage(str(tmp_path))
    storage.put("backups/SafeData_backup_20200101_000000.sql", b"-- old backup", "application/octet-stream")
    old_file = os.path.join(str(tmp_path), "backups", "SafeData_backup_20200101_000000.sql")
    old_time = os.path.getmtime(old_file) - (60 * 86400)
    os.utime(old_file, (old_time, old_time))
    db.add(BackupLog(filename="backups/SafeData_backup_20200101_000000.sql", size_bytes=1, status="success",
                     created_at=utcnow() - timedelta(days=60)))
    db.commit()

    removed = prune_backups(db, storage, 30)
    assert removed >= 1
    assert not os.path.exists(old_file)
    assert db.query(BackupLog).filter(BackupLog.filename == "backups/SafeData_backup_20200101_000000.sql").count() == 0


def test_prune_keeps_recent_objects(db, tmp_path):
    """Prune should keep objects newer than specified days."""
    storage = LocalStorage(str(tmp_path))
    storage.put("backups/SafeData_backup_99991231_235959.sql", b"-- recent backup", "application/octet-stream")

    prune_backups(db, storage, 30)
    assert storage.get("backups/SafeData_backup_99991231_235959.sql") == b"-- recent backup"


def test_backup_logs_on_failure(db):
    """Backup to a failing storage should return failed status and log it."""
    class BrokenStorage:
        def put(self, key, data, content_type):
            raise OSError("disk full")

    result = backup_database(db, BrokenStorage())
    assert result["status"] == "failed"
    assert result["message"] is not None
    assert db.query(BackupLog).filter(BackupLog.status == "failed").count() == 1