"""Lease-based job locks stored in job_locks (portable across SQLite and PostgreSQL)."""

from datetime import timedelta

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.models import JobLock


def acquire(db: Session, job_name: str, holder: str, ttl_seconds: int) -> bool:
    now = utcnow()
    expires = now + timedelta(seconds=ttl_seconds)
    taken = db.execute(
        update(JobLock)
        .where(JobLock.job_name == job_name, JobLock.expires_at < now)
        .values(holder=holder, expires_at=expires)
    ).rowcount
    if taken == 1:
        db.commit()
        return True
    db.rollback()
    if db.get(JobLock, job_name) is not None:
        return False
    db.add(JobLock(job_name=job_name, holder=holder, expires_at=expires))
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def release(db: Session, job_name: str, holder: str) -> None:
    db.execute(delete(JobLock).where(JobLock.job_name == job_name, JobLock.holder == holder))
    db.commit()


def renew(db: Session, job_name: str, holder: str, ttl_seconds: int) -> bool:
    """Extend the lease, only if `holder` still owns it. Returns False if the lease was lost."""
    expires = utcnow() + timedelta(seconds=ttl_seconds)
    n = db.execute(
        update(JobLock).where(JobLock.job_name == job_name, JobLock.holder == holder).values(expires_at=expires)
    ).rowcount
    db.commit()
    return n == 1
