"""
Test backups — ported from PHP backups_test.php.
Tests database backup and pruning.
"""
import pytest
import os
import tempfile
from app.backups import backup_database, prune_backups


def test_backup_creates_file(db, tmp_path):
    """Backup should create a .sql file."""
    result = backup_database(db, str(tmp_path))

    assert result["status"] == "success"
    assert os.path.exists(result["file"])
    assert result["size"] > 0
    assert result["file"].endswith(".sql")


def test_backup_file_content(db, tmp_path):
    """Backup file should contain SQL statements."""
    result = backup_database(db, str(tmp_path))

    with open(result["file"], "r", encoding="utf-8") as f:
        content = f.read()
    assert "ADRS backup" in content or "CREATE" in content or "INSERT" in content


def test_prune_removes_old_files(db, tmp_path):
    """Prune should remove files older than specified days."""
    # Create a fake old backup file
    old_file = os.path.join(str(tmp_path), "adrs_backup_20200101_000000.sql")
    with open(old_file, "w") as f:
        f.write("-- old backup")

    # Set file modification time to 60 days ago
    old_time = os.path.getmtime(old_file) - (60 * 86400)
    os.utime(old_file, (old_time, old_time))

    removed = prune_backups(db, str(tmp_path), days=30)
    assert removed >= 1
    assert not os.path.exists(old_file)


def test_prune_keeps_recent_files(db, tmp_path):
    """Prune should keep files newer than specified days."""
    recent_file = os.path.join(str(tmp_path), "adrs_backup_99991231_235959.sql")
    with open(recent_file, "w") as f:
        f.write("-- recent backup")

    removed = prune_backups(db, str(tmp_path), days=30)
    assert os.path.exists(recent_file)


def test_backup_logs_on_failure(db):
    """Backup to invalid path should return failed status."""
    # Pass a path pointing to a file (not directory) so opening filename inside it fails
    invalid_path = os.path.join(tempfile.gettempdir(), "adrs_test_invalid_file_path.txt")
    with open(invalid_path, "w") as f:
        f.write("not a directory")
    try:
        result = backup_database(db, os.path.join(invalid_path, "sub"))
        assert result["status"] == "failed"
        assert result["message"] is not None
    finally:
        if os.path.exists(invalid_path):
            os.remove(invalid_path)
