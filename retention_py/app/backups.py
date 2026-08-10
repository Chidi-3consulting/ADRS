"""
ADRS Backup System

Provides: logical database dump (pure-Python, no external mysqldump dependency),
backup log recording, and old backup pruning.

For SQLite (dev): uses the built-in sqlite3 .dump() for a restorable .sql file.
For MySQL (prod): uses a table-by-table SELECT + INSERT approach matching the legacy version.
"""
import os
import glob
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect

from app.models import BackupLog
from app.config import APP_ENV


def backup_database(db: Session, backup_dir: str) -> dict:
    """
    Dump the whole database to a .sql file in backup_dir.
    Returns {'file': str, 'size': int, 'status': 'success'|'failed', 'message': str|None}.
    Ported from legacy backup_database().
    """
    filename = f"adrs_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    filepath = os.path.join(backup_dir, filename)

    try:
        os.makedirs(backup_dir, exist_ok=True)
        engine = db.get_bind()
        dialect = engine.dialect.name

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(f"-- ADRS backup {datetime.now().isoformat()}\n")
            fh.write("SET FOREIGN_KEY_CHECKS=0;\nSET NAMES utf8mb4;\n\n")

            if dialect == "sqlite":
                # Use SQLite's iterdump for a complete SQL dump
                import sqlite3
                raw_conn = engine.raw_connection()
                try:
                    for line in raw_conn.iterdump():
                        fh.write(f"{line}\n")
                finally:
                    raw_conn.close()
            else:
                # MySQL: table-by-table dump matching legacy approach
                inspector = inspect(engine)
                tables = inspector.get_table_names()

                for table_name in tables:
                    # Get CREATE TABLE
                    result = db.execute(text(f"SHOW CREATE TABLE `{table_name}`"))
                    row = result.fetchone()
                    if row:
                        create_sql = row[1] if len(row) > 1 else str(row)
                        fh.write(f"DROP TABLE IF EXISTS `{table_name}`;\n{create_sql};\n\n")

                    # Dump rows
                    rows = db.execute(text(f"SELECT * FROM `{table_name}`"))
                    columns = rows.keys()
                    for data_row in rows:
                        cols = ",".join(f"`{c}`" for c in columns)
                        vals = ",".join(
                            "NULL" if v is None else f"'{str(v).replace(chr(39), chr(39)+chr(39))}'"
                            for v in data_row
                        )
                        fh.write(f"INSERT INTO `{table_name}` ({cols}) VALUES ({vals});\n")
                    fh.write("\n")

            fh.write("SET FOREIGN_KEY_CHECKS=1;\n")

        size = os.path.getsize(filepath)

        # Record in backup_log
        log = BackupLog(
            filename=filename,
            size_bytes=size,
            status="success",
            message=None,
        )
        db.add(log)
        db.commit()

        return {"file": filepath, "size": size, "status": "success", "message": None}

    except Exception as e:
        # Log failure
        try:
            log = BackupLog(
                filename=filename,
                size_bytes=None,
                status="failed",
                message=str(e)[:500],
            )
            db.add(log)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

        return {"file": filepath, "size": 0, "status": "failed", "message": str(e)}


def prune_backups(db: Session, backup_dir: str, days: int = 30) -> int:
    """
    Delete backup files (and their log rows) older than `days`.
    Returns count removed. Ported from legacy prune_backups().
    """
    cutoff = time.time() - (days * 86400)
    removed = 0

    pattern = os.path.join(backup_dir, "adrs_backup_*.sql")
    for f in glob.glob(pattern):
        try:
            if os.path.getmtime(f) < cutoff:
                os.remove(f)
                removed += 1
        except OSError:
            pass

    # Prune log rows
    cutoff_dt = datetime.utcnow() - timedelta(days=days)
    db.query(BackupLog).filter(BackupLog.created_at < cutoff_dt).delete()
    db.commit()

    return removed
