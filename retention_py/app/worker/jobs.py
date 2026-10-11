"""Job registry. Intake and dispatch run for every organisation that has queued work
(the old global SafeData_tier == 'enterprise' gate is removed; plan entitlements gate
these in Phase 3)."""

from sqlalchemy.orm import Session

from app.worker.runner import Job


def _retention(db: Session) -> dict:
    from app.engine import run_retention_checks
    from app.models import Organization

    orgs = [o.id for o in db.query(Organization.id).all()]
    for org_id in orgs:
        run_retention_checks(db, org_id)
    return {"organisations": len(orgs)}


def _housekeeping(db: Session) -> dict:
    from app.engine import run_housekeeping

    return run_housekeeping(db) or {}


def _backup(db: Session) -> dict:
    from app.backups import backup_database, prune_backups
    from app.core.storage import get_storage

    storage = get_storage()
    result = backup_database(db, storage)
    if result["status"] != "success":
        raise RuntimeError(result.get("message") or "backup failed")
    pruned = prune_backups(db, storage, 30)
    return {"key": result["key"], "size": result["size"], "pruned": pruned}


def _dispatch(db: Session) -> dict:
    from app import enterprise

    return enterprise.process_disposal_dispatches(db, 50)


def _intake(db: Session) -> dict:
    from app import enterprise

    return enterprise.process_intake_queue(db, 100)


def _audit_chain(db: Session) -> dict:
    from app.engine import notify_role, verify_audit_chain
    from app.models import Organization

    result = verify_audit_chain(db)
    if not result.get("ok"):
        broken = result.get("first_broken_log_id")
        for (org_id,) in db.query(Organization.id).all():
            notify_role(
                db,
                org_id,
                ["admin", "dpo"],
                "security_alert",
                "CRITICAL: Audit Ledger Tamper Alert",
                f"Cryptographic audit chain verification failed at entry #{broken}. "
                "Immediate compliance review required.",
            )
        raise RuntimeError(f"audit chain broken at {broken}")
    return {"verified": result.get("verified_count", 0)}


JOBS: list[Job] = [
    Job("retention", 600, _retention),
    Job("housekeeping", 3600, _housekeeping),
    Job("backup", 86400, _backup),
    Job("dispatch", 600, _dispatch),
    Job("intake", 300, _intake),
    Job("audit_chain", 21600, _audit_chain),
]
