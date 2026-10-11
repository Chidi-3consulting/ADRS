import time
from datetime import timedelta

from app.core.clock import utcnow
from app.database import SessionLocal
from app.models import JobLock, JobRun
from app.worker import jobs as jobs_mod
from app.worker import runner as runner_mod
from app.worker.locks import acquire, release, renew
from app.worker.runner import Job, is_due, run_forever, run_job


def test_two_holders_only_one_acquires(db):
    assert acquire(db, "retention", "worker-a", 600) is True
    assert acquire(db, "retention", "worker-b", 600) is False


def test_expired_lock_can_be_taken_over(db):
    db.add(JobLock(job_name="retention", holder="dead", expires_at=utcnow() - timedelta(seconds=1)))
    db.commit()
    assert acquire(db, "retention", "worker-b", 600) is True
    assert db.get(JobLock, "retention").holder == "worker-b"


def test_release_only_by_holder(db):
    acquire(db, "intake", "worker-a", 600)
    release(db, "intake", "worker-b")
    assert db.get(JobLock, "intake") is not None
    release(db, "intake", "worker-a")
    db.expire_all()
    assert db.get(JobLock, "intake") is None


def test_successful_job_recorded(db):
    job = Job("noop", 60, lambda s: {"checked": 3})
    assert run_job(job, SessionLocal, "w1") == "success"
    run = db.query(JobRun).filter_by(job_name="noop").one()
    assert run.status == "success" and run.detail == {"checked": 3} and run.finished_at


def test_failed_job_recorded_and_lock_released(db):
    def boom(_s):
        raise RuntimeError("kaboom")

    job = Job("boom", 60, boom)
    assert run_job(job, SessionLocal, "w1") == "failed"
    db.expire_all()
    run = db.query(JobRun).filter_by(job_name="boom").one()
    assert run.status == "failed" and "kaboom" in run.error
    assert db.get(JobLock, "boom") is None


def test_skipped_when_locked(db):
    acquire(db, "noop", "other", 600)
    assert run_job(Job("noop", 60, lambda s: {}), SessionLocal, "w1") == "skipped"


def test_is_due(db):
    job = Job("retention", 600, lambda s: {})
    assert is_due(db, job, utcnow()) is True
    db.add(JobRun(job_name="retention", holder="w", status="success", started_at=utcnow(), finished_at=utcnow()))
    db.commit()
    assert is_due(db, job, utcnow()) is False
    assert is_due(db, job, utcnow() + timedelta(seconds=601)) is True


def test_dispatch_and_intake_run_without_global_enterprise_setting(db, monkeypatch):
    called = {}
    monkeypatch.setattr(
        "app.enterprise.process_disposal_dispatches",
        lambda s, n: called.setdefault("dispatch", {"sent": 0, "failed": 0}),
    )
    monkeypatch.setattr(
        "app.enterprise.process_intake_queue", lambda s, n: called.setdefault("intake", {"processed": 0})
    )
    by_name = {j.name: j for j in jobs_mod.JOBS}
    by_name["dispatch"].fn(db)
    by_name["intake"].fn(db)
    assert set(called) == {"dispatch", "intake"}


def test_registry_names():
    assert {j.name for j in jobs_mod.JOBS} == {
        "retention",
        "housekeeping",
        "backup",
        "dispatch",
        "intake",
        "audit_chain",
    }


def test_renew_only_for_holder(db):
    acquire(db, "retention", "a", 10)
    before = db.get(JobLock, "retention").expires_at
    assert renew(db, "retention", "b", 600) is False
    db.expire_all()
    assert db.get(JobLock, "retention").expires_at == before
    assert renew(db, "retention", "a", 600) is True
    db.expire_all()
    assert db.get(JobLock, "retention").expires_at > before + timedelta(seconds=300)


def test_lease_renewed_while_job_runs(db, monkeypatch):
    monkeypatch.setattr(runner_mod, "LEASE_TTL_SECONDS", 1)
    monkeypatch.setattr(runner_mod, "RENEW_INTERVAL_SECONDS", 0.1)
    seen = {}

    def slow(_s):
        time.sleep(2.5)  # well past the 1s TTL
        other = SessionLocal()
        try:
            lock = other.get(JobLock, "slow")
            seen["holder"] = lock.holder
            seen["valid"] = lock.expires_at > utcnow()
            seen["stolen"] = acquire(other, "slow", "intruder", 1)
        finally:
            other.close()
        return {}

    assert run_job(Job("slow", 1, slow), SessionLocal, "w1") == "success"
    assert seen == {"holder": "w1", "valid": True, "stolen": False}
    db.expire_all()
    assert db.get(JobLock, "slow") is None


def test_loop_survives_error_outside_job_fn(db, monkeypatch):
    real = runner_mod.run_job

    def flaky(job, sf, holder):
        if job.name == "first":
            raise RuntimeError("commit exploded")
        return real(job, sf, holder)

    monkeypatch.setattr(runner_mod, "run_job", flaky)
    passes = iter([False, True])
    run_forever(
        SessionLocal,
        "w1",
        [Job("first", 60, lambda s: {}), Job("second", 60, lambda s: {"ok": 1})],
        stop=lambda: next(passes),
        sleep=lambda _s: None,
    )
    db.expire_all()
    assert db.query(JobRun).filter_by(job_name="second", status="success").count() == 1


def test_release_failure_is_logged_not_raised(db, monkeypatch):
    def bad_release(*_a):
        raise RuntimeError("release boom")

    monkeypatch.setattr(runner_mod, "release", bad_release)
    assert run_job(Job("rel", 60, lambda s: {}), SessionLocal, "w1") == "success"
