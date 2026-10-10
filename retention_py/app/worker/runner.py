"""Run registered jobs on their intervals with locks and history."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.models import JobRun
from app.worker.locks import acquire, release

log = logging.getLogger("safedata.worker")
TICK_SECONDS = 30


@dataclass(frozen=True)
class Job:
    name: str
    interval_seconds: int
    fn: Callable[[Session], dict]


def is_due(db: Session, job: Job, now: datetime) -> bool:
    last = (db.query(JobRun.started_at)
            .filter(JobRun.job_name == job.name, JobRun.status.in_(("success", "failed")))
            .order_by(JobRun.started_at.desc()).first())
    return last is None or now - last[0] >= timedelta(seconds=job.interval_seconds)


def run_job(job: Job, session_factory, holder: str) -> str:
    db: Session = session_factory()
    try:
        if not acquire(db, job.name, holder, max(job.interval_seconds, 900)):
            return "skipped"
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
        log.info("job finished", extra={"job": job.name, "status": run.status,
                                        "duration_ms": int((time.monotonic() - started) * 1000)})
        return run.status
    finally:
        try:
            release(db, job.name, holder)
        finally:
            db.close()


def run_forever(session_factory, holder: str, jobs: list[Job],
                stop: Callable[[], bool] = lambda: False,
                sleep: Callable[[float], None] = time.sleep) -> None:
    log.info("worker started", extra={"status": holder})
    while not stop():
        for job in jobs:
            db = session_factory()
            try:
                due = is_due(db, job, utcnow())
            finally:
                db.close()
            if due:
                run_job(job, session_factory, holder)
        sleep(TICK_SECONDS)