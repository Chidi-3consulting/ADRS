"""Run registered jobs on their intervals with locks and history."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.models import JobRun
from app.worker.locks import acquire, release, renew

log = logging.getLogger("safedata.worker")
TICK_SECONDS = 30
# Fixed lease length; the heartbeat renews it, so a short lease only speeds crash recovery.
LEASE_TTL_SECONDS = 300
# Lease renewal period in seconds; None means ttl/3. Tests override with a short value.
RENEW_INTERVAL_SECONDS: float | None = None


@dataclass(frozen=True)
class Job:
    name: str
    interval_seconds: int
    fn: Callable[[Session], dict]


def is_due(db: Session, job: Job, now: datetime) -> bool:
    last = (
        db.query(JobRun.started_at)
        .filter(JobRun.job_name == job.name, JobRun.status.in_(("success", "failed")))
        .order_by(JobRun.started_at.desc())
        .first()
    )
    return last is None or now - last[0] >= timedelta(seconds=job.interval_seconds)


def _renew_loop(session_factory, job_name: str, holder: str, ttl: int, interval: float, stop: threading.Event) -> None:
    """Keep the lease alive while the job runs so no other worker can take it over."""
    db = session_factory()
    try:
        while not stop.wait(interval):
            try:
                if not renew(db, job_name, holder, ttl):
                    log.error("lease lost", extra={"job": job_name})
                    return
            except Exception:
                db.rollback()
                log.exception("lease renewal failed", extra={"job": job_name})
    finally:
        db.close()


def run_job(job: Job, session_factory, holder: str) -> str:
    db: Session = session_factory()
    renew_stop = threading.Event()
    renewer: threading.Thread | None = None
    try:
        ttl = LEASE_TTL_SECONDS
        if not acquire(db, job.name, holder, ttl):
            return "skipped"
        renewer = threading.Thread(
            target=_renew_loop,
            args=(session_factory, job.name, holder, ttl, RENEW_INTERVAL_SECONDS or ttl / 3, renew_stop),
            daemon=True,
        )
        renewer.start()
        run = JobRun(job_name=job.name, holder=holder, status="running", started_at=utcnow())
        db.add(run)
        db.commit()
        started = time.monotonic()
        try:
            detail = job.fn(db) or {}
            run.status, run.detail = "success", detail
        except Exception as exc:  # recorded, never swallowed silently
            db.rollback()
            run = db.get(JobRun, run.id)
            run.status, run.error = "failed", f"{type(exc).__name__}: {exc}"[:4000]
            log.exception("job failed", extra={"job": job.name})
        run.finished_at = utcnow()
        db.commit()
        log.info(
            "job finished",
            extra={"job": job.name, "status": run.status, "duration_ms": int((time.monotonic() - started) * 1000)},
        )
        return run.status
    finally:
        renew_stop.set()
        if renewer is not None:
            renewer.join(timeout=5)
        try:
            db.rollback()
            release(db, job.name, holder)
        except Exception:
            log.exception("lock release failed", extra={"job": job.name})
        finally:
            db.close()


def run_forever(
    session_factory,
    holder: str,
    jobs: list[Job],
    stop: Callable[[], bool] = lambda: False,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    log.info("worker started", extra={"status": holder})
    while not stop():
        for job in jobs:
            try:
                db = session_factory()
                try:
                    due = is_due(db, job, utcnow())
                finally:
                    db.close()
                if due:
                    run_job(job, session_factory, holder)
            except Exception:
                log.exception("worker loop error", extra={"job": job.name})
        sleep(TICK_SECONDS)
