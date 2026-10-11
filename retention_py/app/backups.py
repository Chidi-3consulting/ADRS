"""Encrypted database backups written to object storage.
SQLite → iterdump SQL; PostgreSQL → pg_dump custom format (pg_dump 16 is in the Docker image)."""
from __future__ import annotations

import logging
import subprocess
from datetime import timedelta

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.config import BACKUP_ENCRYPTION_KEY
from app.core.clock import utcnow
from app.models import BackupLog

log = logging.getLogger("safedata.backups")
PREFIX = "backups/"


def _dump(db: Session) -> tuple[bytes, str]:
    engine = db.get_bind()
    if engine.dialect.name == "sqlite":
        raw = engine.raw_connection()
        try:
            return ("\n".join(raw.iterdump()) + "\n").encode("utf-8"), "sqlite.sql"
        finally:
            raw.close()
    if engine.dialect.name == "postgresql":
        url = engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
        out = subprocess.run(["pg_dump", "--format=custom", "--no-owner", url],
                             check=True, capture_output=True, timeout=1800)
        return out.stdout, "pgdump"
    raise RuntimeError(f"backups not supported for dialect {engine.dialect.name}")


def backup_database(db: Session, storage) -> dict:
    key = ""
    try:
        data, ext = _dump(db)
        if BACKUP_ENCRYPTION_KEY:
            data, ext = Fernet(BACKUP_ENCRYPTION_KEY.encode()).encrypt(data), ext + ".enc"
        key = f"{PREFIX}SafeData_backup_{utcnow():%Y%m%d_%H%M%S}.{ext}"
        storage.put(key, data, "application/octet-stream")
        db.add(BackupLog(filename=key, size_bytes=len(data), status="success"))
        db.commit()
        return {"status": "success", "key": key, "size": len(data), "message": None}
    except Exception as exc:
        db.rollback()
        log.exception("backup failed")
        db.add(BackupLog(filename=key or "unknown", size_bytes=None, status="failed", message=str(exc)[:500]))
        db.commit()
        return {"status": "failed", "key": key, "size": 0, "message": str(exc)}


def prune_backups(db: Session, storage, days: int = 30) -> int:
    cutoff = utcnow() - timedelta(days=days)
    removed = 0
    for key, modified in storage.list(PREFIX):
        if modified < cutoff:
            storage.delete(key)
            removed += 1
    db.query(BackupLog).filter(BackupLog.created_at < cutoff).delete()
    db.commit()
    return removed
