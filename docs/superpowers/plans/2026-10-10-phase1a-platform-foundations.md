# Phase 1A — Platform Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SafeData deployable and operable as a SaaS: isolated and fast tests, versioned migrations with no import-time side effects, structured logging, a separate locked background worker, object storage for evidence and encrypted backups, configurable domain, Docker, and CI on PostgreSQL.

**Architecture:** Introduce `app/core/` (clock, logging, storage, cli helpers) and `app/worker/` (registry, locks, runner). `main.py` becomes a pure app factory with no DB access at import. Alembic owns the schema; the test suite builds the schema once per session and truncates between tests. The web process runs no background jobs; `python -m app.worker` runs them with lease-based locks recorded in `job_runs`.

**Tech Stack:** Python 3.12 (CI/Docker; local 3.14 also works), FastAPI 0.136, SQLAlchemy 2.0, Alembic 1.18, PostgreSQL 16, boto3 (S3-compatible: Cloudflare R2 / DO Spaces), cryptography (Fernet), pytest, ruff, Docker, GitHub Actions, Render.

**Spec:** `docs/superpowers/specs/2026-10-10-safedata-launch-programme-design.md` (§5.3, §5.4, §5.6, §5.7, §5.8, §10; findings F5–F8, F18)

## Global Constraints

- Work on branch `safedata-launch`; all paths below are relative to the repo root.
- Run commands from `retention_py/` unless stated: `cd retention_py`.
- Production database: **PostgreSQL 16**. Local default stays SQLite for convenience; CI runs the suite on PostgreSQL.
- No DB access, schema change or seeding may happen at import time of any module.
- Background jobs never run in the web process.
- Job locking: lease rows in `job_locks` (portable across SQLite/PostgreSQL; refines spec §5.4's "advisory lock" with an equivalent guarantee that is visible and testable).
- Time: all new code obtains "now" from `app.core.clock.utcnow()` (naive UTC in 1A; Phase 1C switches to timezone-aware).
- Domain: canonical origin from `APP_URL`; default mail domain `safedata.3consult-ng.com`; security contact `security@3consult-ng.com`. No literal `3consulting.com` anywhere in `app/`.
- Secrets only from environment variables; production refuses to start without `SECRET_KEY` and (when backups enabled) `BACKUP_ENCRYPTION_KEY`.
- Existing behaviour must not regress: the full existing suite (199 tests) must pass at the end of every task.
- Commit after every task with a conventional message ending with the co-author trailer used in this repo.

## Review Focus

1. **Two workers start at once** — expect exactly one runs each job; the other records nothing and does not crash (Task 4 test `test_two_holders_only_one_acquires`).
2. **A job throws** — expect the failure is recorded in `job_runs` with the error text, the lock is released, and other jobs still run (Task 4 test `test_failed_job_recorded_and_lock_released`).
3. **Attachment key crafted with `../`** — expect storage rejects it; download of another org's attachment returns 404 (Task 5 tests `test_local_storage_rejects_traversal`, and the existing org filter retained).
4. **Old domain still bookmarked** — expect `https://old-host/path?q=1` → 301 to `APP_URL/path?q=1`, preserving query (Task 6 test).
5. **Database down** — expect `/healthz` returns 503 with `{"status":"degraded"}` instead of 200 or a stack trace (Task 7 test).

---

## File Structure

```
retention_py/
  app/core/__init__.py
  app/core/clock.py          # utcnow()
  app/core/logging.py        # JsonFormatter, configure_logging, RequestIdMiddleware
  app/core/storage.py        # Storage protocol, LocalStorage, S3Storage, get_storage()
  app/core/legacy_schema.py  # moved ensure_schema_columns (used only by cli adopt-legacy-db)
  app/cli.py                 # python -m app.cli migrate | adopt-legacy-db
  app/worker/__init__.py
  app/worker/__main__.py     # python -m app.worker
  app/worker/locks.py        # acquire/release lease locks
  app/worker/jobs.py         # job registry
  app/worker/runner.py       # run_job, is_due, run_forever
  app/backups.py             # rewritten: SQLite/PostgreSQL dump → encrypted object
  app/models.py              # + JobRun, JobLock
  app/config.py              # + BCRYPT_ROUNDS, storage, backup key, domain settings
  app/auth.py                # hash_password uses BCRYPT_ROUNDS
  app/middleware.py          # + CanonicalHostMiddleware
  app/routes/records.py      # attachments via storage
  main.py                    # no import-time DB work; no schedulers; deep healthz
  alembic/env.py             # URL normalisation, batch mode for SQLite
  alembic/versions/0001_baseline.py, 0002_worker_tables.py
  tests/conftest.py          # single engine, schema once, truncate per test
  tests/test_foundation_*.py # new tests per task
  Dockerfile, docker-compose.yml, .dockerignore, render.yaml (updated)
  pyproject.toml             # ruff config
.github/workflows/ci.yml
```

---

### Task 1: Single test engine, fast hashing, per-test truncation

Fixes SD-07-002 (tests and middleware hit the dev DB) and most of the 8-minute runtime.

**Files:**
- Modify: `retention_py/app/config.py` (add `BCRYPT_ROUNDS`)
- Modify: `retention_py/app/auth.py:55-59`
- Modify: `retention_py/tests/conftest.py` (rewrite)
- Test: `retention_py/tests/test_foundation_testdb.py`

**Interfaces:**
- Produces: fixtures `db` (Session bound to `app.database.engine`, org id 1 seeded, `setup_complete=1` seeded), `client` (TestClient with `get_db` overridden to `db`), `auth_user` (unchanged contract). Env var `TEST_DATABASE_URL` selects PostgreSQL.

- [ ] **Step 1: Write the failing test**

```python
# retention_py/tests/test_foundation_testdb.py
import app.database as database


def test_app_engine_is_the_test_database():
    url = str(database.engine.url)
    assert "test" in url, f"app engine points at non-test DB: {url}"


def test_main_uses_the_same_session_factory():
    import main
    assert main.SessionLocal is database.SessionLocal


def test_password_hashing_uses_fast_rounds_in_tests():
    from app.auth import hash_password, verify_password
    h = hash_password("Xyq9$mNpL2!k")
    assert h.startswith("$2b$04$")
    assert verify_password("Xyq9$mNpL2!k", h)


def test_seeded_org_has_id_1(db):
    from app.models import Organization
    assert db.get(Organization, 1) is not None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_foundation_testdb.py -v`
Expected: FAIL — `test_app_engine_is_the_test_database` (URL is `.../retention.db`) and `$2b$12$` prefix.

- [ ] **Step 3: Add `BCRYPT_ROUNDS` to config** (append after the password policy block in `app/config.py`):

```python
# bcrypt cost: 12 in real environments; 4 in tests (bcrypt minimum) for speed.
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "4" if IS_TEST else "12"))
```

- [ ] **Step 4: Use it in `app/auth.py`** — replace `hash_password`:

```python
def hash_password(password: str) -> str:
    from app.config import BCRYPT_ROUNDS
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
```

- [ ] **Step 5: Rewrite `tests/conftest.py`**

```python
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "sqlite:///" + os.path.join(ROOT, "test.db").replace("\\", "/")
)
sys.path.insert(0, ROOT)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app.models  # noqa: E402,F401  (register all models)
from app.auth import hash_password  # noqa: E402
from app.database import Base, SessionLocal, engine, get_db  # noqa: E402
from app.models import Organization, SystemSetting, User  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _truncate_all():
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
            conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        else:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())


@pytest.fixture(scope="function")
def db():
    _truncate_all()
    session = SessionLocal()
    org = Organization(name="Test Organisation", slug="test-org", primary_domain="test.local",
                       country="NG", tier="core", status="active")
    session.add(org)
    session.add(SystemSetting(setting_key="setup_complete", setting_value="1"))
    session.commit()
    assert org.id == 1, "seed organisation must receive id 1"
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_user(db):
    user = User(organization_id=1, name="Test Admin User", email="test@admin.com",
                password_hash=hash_password("Str0ng!Pass#99"), role="admin", is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_header(auth_user):
    return auth_user
```

- [ ] **Step 6: Run the new tests, then the full suite**

Run: `python -m pytest tests/test_foundation_testdb.py -v` → 4 passed.
Run: `python -m pytest tests -q -p no:cacheprovider`
Expected: all pass. Record the runtime (target: under 2 minutes). Any test that now fails was depending on dev-DB contents: fix the **test** to seed what it needs (e.g. users referenced by id), never re-point at the dev DB. Typical fix: a test that posted `/login` for a user that existed only in `retention.db` must create that user with `hash_password` first.

- [ ] **Step 7: Commit**

```bash
git add retention_py/app/config.py retention_py/app/auth.py retention_py/tests/conftest.py retention_py/tests/test_foundation_testdb.py retention_py/tests
git commit -m "test: single test engine, fast bcrypt in tests, per-test truncation"
```

---

### Task 2: Alembic baseline, CLI, and no import-time side effects

Fixes F8 / SD-06-001 and SD-05-003.

**Files:**
- Create: `retention_py/app/core/__init__.py` (empty), `retention_py/app/core/legacy_schema.py`, `retention_py/app/cli.py`
- Modify: `retention_py/alembic/env.py`, `retention_py/main.py:96-180` (delete), `retention_py/dev-start.ps1`
- Create (generated): `retention_py/alembic/versions/0001_baseline.py`
- Test: `retention_py/tests/test_foundation_migrations.py`

**Interfaces:**
- Produces: `python -m app.cli migrate` (alembic upgrade head), `python -m app.cli adopt-legacy-db` (for DBs created by the old `create_all`), `app.cli.alembic_config() -> alembic.config.Config`.

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_foundation_migrations.py
import os
import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]


def test_importing_main_does_not_touch_the_database(tmp_path):
    db_file = tmp_path / "untouched.db"
    env = {**os.environ, "APP_ENV": "test", "DATABASE_URL": f"sqlite:///{db_file.as_posix()}"}
    subprocess.run([sys.executable, "-c", "import main"], cwd=ROOT, env=env, check=True)
    assert not db_file.exists(), "importing main created/modified the database"


def test_migrations_match_models(tmp_path):
    from app.cli import alembic_config
    from app.database import Base
    url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    cfg = alembic_config(url)
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models and migrations differ: {diff}"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_foundation_migrations.py -v`
Expected: FAIL — `untouched.db` exists; `ModuleNotFoundError: app.cli`.

- [ ] **Step 3: Move legacy column patching** — create `app/core/legacy_schema.py` containing the body of `ensure_schema_columns` cut from `main.py:99-157` unchanged, renamed `ensure_legacy_columns(bind_engine)`, with `print(...)` replaced by `logging.getLogger(__name__).warning(...)`.

- [ ] **Step 4: Delete import-time DB work from `main.py`** — remove lines 96–180 (`from sqlalchemy import inspect, text`, `ensure_schema_columns` definition and call, `Base.metadata.create_all(...)`, and the default-organisation seed block). Remove now-unused imports `engine, Base` from the `app.database` import line (keep `SessionLocal`).

- [ ] **Step 5: Update `alembic/env.py`** — replace the URL line and both `context.configure` calls:

```python
from app.database import Base, _db_url as APP_DB_URL
...
config.set_main_option("sqlalchemy.url", config.get_main_option("sqlalchemy.url_override") or APP_DB_URL)
...
# offline:
context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                  dialect_opts={"paramstyle": "named"}, render_as_batch=url.startswith("sqlite"))
# online:
context.configure(connection=connection, target_metadata=target_metadata,
                  render_as_batch=connection.dialect.name == "sqlite")
```

- [ ] **Step 6: Create `app/cli.py`**

```python
"""SafeData operations CLI: python -m app.cli <command>."""
from __future__ import annotations

import argparse
import logging
import os
import sys

from alembic import command
from alembic.config import Config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log = logging.getLogger("safedata.cli")


def alembic_config(url: str | None = None) -> Config:
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(ROOT, "alembic"))
    if url:
        cfg.set_main_option("sqlalchemy.url_override", url)
    return cfg


def cmd_migrate(_args) -> int:
    command.upgrade(alembic_config(), "head")
    return 0


def cmd_adopt_legacy_db(_args) -> int:
    """For databases created by the old import-time create_all: patch legacy columns,
    create any missing tables, verify no drift, then stamp the baseline."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    import app.models  # noqa: F401
    from app.core.legacy_schema import ensure_legacy_columns
    from app.database import Base, engine

    ensure_legacy_columns(engine)
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    if diff:
        log.error("Legacy DB still differs from models; not stamping: %s", diff)
        return 1
    command.stamp(alembic_config(), "0001_baseline")
    command.upgrade(alembic_config(), "head")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate").set_defaults(fn=cmd_migrate)
    sub.add_parser("adopt-legacy-db").set_defaults(fn=cmd_adopt_legacy_db)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
```

Also create `app/__main__.py`? No — `python -m app.cli` runs `app/cli.py` directly.

- [ ] **Step 6b: Make every Enum portable to PostgreSQL** (finding SD-06-002, High: unnamed native `Enum` columns raise `CompileError: PostgreSQL ENUM type requires a name`, so the schema has never been creatable on PostgreSQL). Store enums as `VARCHAR` + `CHECK` instead of native PG ENUM types (adding values later is then a plain migration).

Add to `tests/test_foundation_migrations.py`:

```python
def test_all_enums_are_non_native():
    from sqlalchemy import Enum
    from app.database import Base
    native = [f"{t.name}.{c.name}" for t in Base.metadata.sorted_tables for c in t.columns
              if isinstance(c.type, Enum) and c.type.native_enum]
    assert native == []
```

At the top of `app/models.py`, after the imports, add and use:

```python
from sqlalchemy import Enum as _SAEnum


def Enum(*values, **kw):  # noqa: N802 — drop-in replacement for sqlalchemy.Enum
    """Portable enum: VARCHAR + CHECK constraint on every database."""
    kw.setdefault("native_enum", False)
    kw.setdefault("create_constraint", True)
    return _SAEnum(*values, **kw)
```
and remove `Enum` from the `from sqlalchemy import (...)` list so every existing `Enum(...)` column uses the wrapper. Run `python -m pytest tests/test_foundation_migrations.py::test_all_enums_are_non_native -v` → PASS.

- [ ] **Step 7: Generate the baseline revision** against an empty SQLite file:

```powershell
$env:APP_ENV="local"; $env:DATABASE_URL="sqlite:///./baseline_tmp.db"
alembic revision --autogenerate -m "baseline" --rev-id 0001_baseline
Remove-Item baseline_tmp.db
```

Open `alembic/versions/0001_baseline_baseline.py`: confirm it creates every table in `app/models.py` (35 tables) and that `down_revision = None`. Rename the file to `0001_baseline.py`.

- [ ] **Step 8: Run tests**

Run: `python -m pytest tests/test_foundation_migrations.py -v` → 2 passed.
Run: `python -m pytest tests -q -p no:cacheprovider` → all pass.

- [ ] **Step 9: Update `dev-start.ps1`** — before `python main.py` add:

```powershell
Write-Host "Applying database migrations..." -ForegroundColor Cyan
python -m app.cli migrate
```
and add a comment: existing local `retention.db` created by the old app must run `python -m app.cli adopt-legacy-db` once.

- [ ] **Step 10: Commit**

```bash
git add retention_py/app/core retention_py/app/cli.py retention_py/alembic retention_py/main.py retention_py/dev-start.ps1 retention_py/tests/test_foundation_migrations.py
git commit -m "feat(db): alembic baseline + ops CLI; remove import-time schema changes and seeding"
```

---

### Task 3: Structured logging and request IDs

**Files:**
- Create: `retention_py/app/core/clock.py`, `retention_py/app/core/logging.py`
- Modify: `retention_py/main.py` (configure logging, add middleware)
- Test: `retention_py/tests/test_foundation_logging.py`

**Interfaces:**
- Produces: `app.core.clock.utcnow() -> datetime` (naive UTC); `app.core.logging.configure_logging(json_output: bool) -> None`; `JsonFormatter`; `RequestIdMiddleware` (ASGI); `request_id_var: ContextVar[str]`.

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_foundation_logging.py
import json
import logging

from app.core.logging import JsonFormatter, request_id_var


def test_json_formatter_includes_request_id_and_extras():
    token = request_id_var.set("req-123")
    try:
        rec = logging.LogRecord("safedata.test", logging.INFO, __file__, 1, "hello %s", ("world",), None)
        rec.job = "retention"
        out = json.loads(JsonFormatter().format(rec))
    finally:
        request_id_var.reset(token)
    assert out["msg"] == "hello world"
    assert out["request_id"] == "req-123"
    assert out["job"] == "retention"
    assert out["level"] == "INFO"


def test_request_id_header_is_echoed_or_generated(client):
    r = client.get("/healthz", headers={"X-Request-ID": "abc-1"})
    assert r.headers["X-Request-ID"] == "abc-1"
    r2 = client.get("/healthz")
    assert len(r2.headers["X-Request-ID"]) == 32


def test_utcnow_is_naive_utc():
    from datetime import datetime, timezone
    from app.core.clock import utcnow
    now = utcnow()
    assert now.tzinfo is None
    assert abs((datetime.now(timezone.utc).replace(tzinfo=None) - now).total_seconds()) < 5
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_foundation_logging.py -v` → FAIL (module not found).

- [ ] **Step 3: Implement `app/core/clock.py`**

```python
"""Single source of 'now'. Phase 1C switches this to timezone-aware UTC."""
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

- [ ] **Step 4: Implement `app/core/logging.py`**

```python
"""Structured logging with per-request IDs."""
from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_EXTRA_KEYS = ("job", "org_id", "user_id", "duration_ms", "status", "path", "method")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key in _EXTRA_KEYS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(json_output: bool) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_output else
                         logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


class RequestIdMiddleware:
    """Pure ASGI middleware: accept X-Request-ID (≤64 chars) or generate one; echo it back."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if 0 < len(incoming) <= 64 else uuid.uuid4().hex
        token = request_id_var.set(rid)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"x-request-id", rid.encode("latin-1")))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_var.reset(token)
```

- [ ] **Step 5: Wire into `main.py`** — after imports:

```python
from app.core.logging import RequestIdMiddleware, configure_logging
configure_logging(json_output=IS_PRODUCTION)
```
and after the existing `app.add_middleware(RequestSizeLimitMiddleware)` line add `app.add_middleware(RequestIdMiddleware)` (added last → outermost, so every log line inside the request carries the id).

- [ ] **Step 6: Run tests** — `python -m pytest tests/test_foundation_logging.py -v` → 3 passed; full suite passes.

- [ ] **Step 7: Commit**

```bash
git add retention_py/app/core/clock.py retention_py/app/core/logging.py retention_py/main.py retention_py/tests/test_foundation_logging.py
git commit -m "feat(core): structured JSON logging, request IDs, central clock"
```

---

### Task 4: Separate background worker with lease locks and job history

Fixes F5 / SD-09-001 and F6 / SD-02-001.

**Files:**
- Modify: `retention_py/app/models.py` (append `JobRun`, `JobLock`)
- Create: `retention_py/alembic/versions/0002_worker_tables.py` (autogenerated)
- Create: `retention_py/app/worker/__init__.py` (empty), `locks.py`, `jobs.py`, `runner.py`, `__main__.py`
- Modify: `retention_py/main.py` (delete scheduler functions lines 183–313 and `lifespan=lifespan`)
- Modify: `retention_py/render.yaml` (worker service — completed in Task 7)
- Test: `retention_py/tests/test_foundation_worker.py`

**Interfaces:**
- Consumes: `app.core.clock.utcnow`, `app.engine.run_retention_checks(db, org_id)`, `run_housekeeping(db)`, `verify_audit_chain(db)`, `notify_role(...)`, `app.enterprise.process_disposal_dispatches(db, limit)`, `process_intake_queue(db, limit)`, `app.backups.backup_database(db, storage)` (Task 5 signature; until Task 5 lands the backup job calls the current signature with `BACKUP_PATH`).
- Produces: `acquire(db, job_name: str, holder: str, ttl_seconds: int) -> bool`, `release(db, job_name: str, holder: str) -> None`; `Job(name: str, interval_seconds: int, fn: Callable[[Session], dict])`; `JOBS: list[Job]`; `run_job(job: Job, session_factory, holder: str) -> str` (returns `"success" | "failed" | "skipped"`); `is_due(db, job: Job, now: datetime) -> bool`; `run_forever(session_factory, holder: str, stop: Callable[[], bool], sleep: Callable[[float], None]) -> None`.

- [ ] **Step 1: Add models** (append to `app/models.py`):

```python
class JobRun(Base):
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String(64), nullable=False, index=True)
    holder = Column(String(128), nullable=False)
    status = Column(Enum("running", "success", "failed", name="job_run_status"), nullable=False, default="running")
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    detail = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)


class JobLock(Base):
    __tablename__ = "job_locks"

    job_name = Column(String(64), primary_key=True)
    holder = Column(String(128), nullable=False)
    expires_at = Column(DateTime, nullable=False)
```

- [ ] **Step 2: Generate migration** — `$env:DATABASE_URL="sqlite:///./mig_tmp.db"; python -m app.cli migrate; alembic revision --autogenerate -m "worker tables" --rev-id 0002_worker_tables; Remove-Item mig_tmp.db`. Confirm it only creates `job_runs` and `job_locks`; rename file to `0002_worker_tables.py`.

- [ ] **Step 3: Write the failing tests**

```python
# retention_py/tests/test_foundation_worker.py
from datetime import timedelta

from app.core.clock import utcnow
from app.database import SessionLocal
from app.models import JobLock, JobRun
from app.worker import jobs as jobs_mod
from app.worker.locks import acquire, release
from app.worker.runner import Job, is_due, run_job


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
    db.add(JobRun(job_name="retention", holder="w", status="success",
                  started_at=utcnow(), finished_at=utcnow()))
    db.commit()
    assert is_due(db, job, utcnow()) is False
    assert is_due(db, job, utcnow() + timedelta(seconds=601)) is True


def test_dispatch_and_intake_run_without_global_enterprise_setting(db, monkeypatch):
    called = {}
    monkeypatch.setattr("app.enterprise.process_disposal_dispatches", lambda s, n: called.setdefault("dispatch", {"sent": 0, "failed": 0}))
    monkeypatch.setattr("app.enterprise.process_intake_queue", lambda s, n: called.setdefault("intake", {"processed": 0}))
    by_name = {j.name: j for j in jobs_mod.JOBS}
    by_name["dispatch"].fn(db)
    by_name["intake"].fn(db)
    assert set(called) == {"dispatch", "intake"}


def test_registry_names():
    assert {j.name for j in jobs_mod.JOBS} == {
        "retention", "housekeeping", "backup", "dispatch", "intake", "audit_chain"}
```

- [ ] **Step 4: Run to verify failure** — `python -m pytest tests/test_foundation_worker.py -v` → FAIL (modules missing).

- [ ] **Step 5: Implement `app/worker/locks.py`**

```python
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
```

- [ ] **Step 6: Implement `app/worker/runner.py`**

```python
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
```

- [ ] **Step 7: Implement `app/worker/jobs.py`**

```python
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
    from app.backups import backup_database
    from app.core.storage import get_storage
    result = backup_database(db, get_storage())
    if result["status"] != "success":
        raise RuntimeError(result.get("message") or "backup failed")
    return {"key": result["key"], "size": result["size"]}


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
            notify_role(db, org_id, ["admin", "dpo"], "security_alert",
                        "CRITICAL: Audit Ledger Tamper Alert",
                        f"Cryptographic audit chain verification failed at entry #{broken}. "
                        "Immediate compliance review required.")
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
```

(Until Task 5 is merged, keep `_backup` calling the old API: `backup_database(db, BACKUP_PATH)` returning `file`; Task 5 changes it to the code above.)

- [ ] **Step 8: Implement `app/worker/__main__.py`**

```python
import os
import signal
import socket

from app.config import IS_PRODUCTION
from app.core.logging import configure_logging
from app.database import SessionLocal
from app.worker.jobs import JOBS
from app.worker.runner import run_forever

_stop = False


def _handle(_sig, _frm):
    global _stop
    _stop = True


if __name__ == "__main__":
    configure_logging(json_output=IS_PRODUCTION)
    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    holder = f"{socket.gethostname()}:{os.getpid()}"
    run_forever(SessionLocal, holder, JOBS, stop=lambda: _stop)
```

- [ ] **Step 9: Remove schedulers from `main.py`** — delete `retention_scheduler_task` … `audit_chain_scheduler_task`, the `lifespan` function, the `asyncio`/`asynccontextmanager` imports, the `run_retention_checks, run_housekeeping` import, and `lifespan=lifespan` from `FastAPI(...)`.

- [ ] **Step 10: Run tests** — `python -m pytest tests/test_foundation_worker.py -v` → 10 passed; full suite passes. Add `python -m app.worker` to `dev-start.ps1` as a second background process (`Start-Process python -ArgumentList "-m","app.worker" -NoNewWindow`).

- [ ] **Step 11: Commit**

```bash
git add retention_py/app/models.py retention_py/alembic/versions retention_py/app/worker retention_py/main.py retention_py/dev-start.ps1 retention_py/tests/test_foundation_worker.py
git commit -m "feat(worker): separate locked background worker with job history; remove in-process schedulers and global enterprise gate"
```

---

### Task 5: Object storage for attachments and encrypted backups

Fixes F7 / SD-09-002 and the PostgreSQL-incompatible backup.

**Files:**
- Create: `retention_py/app/core/storage.py`
- Modify: `retention_py/app/config.py` (storage + backup settings), `retention_py/app/backups.py` (rewrite), `retention_py/app/routes/records.py:757-855`, `retention_py/requirements.txt` (+ `boto3==1.40.0`)
- Test: `retention_py/tests/test_foundation_storage.py`

**Interfaces:**
- Produces: `Storage` protocol with `put(key: str, data: bytes, content_type: str) -> None`, `get(key: str) -> bytes`, `delete(key: str) -> None`, `list(prefix: str) -> list[tuple[str, datetime]]`; `LocalStorage(root: str)`; `S3Storage(bucket: str, client)`; `get_storage() -> Storage`; `backup_database(db, storage) -> dict` with keys `status`, `key`, `size`, `message`; `prune_backups(db, storage, days: int) -> int`; attachment key format `orgs/{org_id}/attachments/{uuid}.{ext}`.

- [ ] **Step 1: Config** (append to `app/config.py`):

```python
# ── Object storage (attachments, backups) ──
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")  # 'local' | 's3'
STORAGE_LOCAL_ROOT = os.getenv("STORAGE_LOCAL_ROOT", os.path.join(BASE_DIR, "storage"))
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")  # e.g. https://<account>.r2.cloudflarestorage.com
S3_REGION = os.getenv("S3_REGION", "auto")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "")
# Fernet key (python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")
BACKUP_ENCRYPTION_KEY = os.getenv("BACKUP_ENCRYPTION_KEY", "")
if IS_PRODUCTION and not BACKUP_ENCRYPTION_KEY:
    print("FATAL: BACKUP_ENCRYPTION_KEY must be set in production.", file=sys.stderr)
    sys.exit(1)
```

- [ ] **Step 2: Write the failing tests**

```python
# retention_py/tests/test_foundation_storage.py
import io

import pytest
from cryptography.fernet import Fernet

from app.core.storage import LocalStorage, S3Storage


def test_local_storage_roundtrip(tmp_path):
    s = LocalStorage(str(tmp_path))
    s.put("orgs/1/attachments/a.pdf", b"%PDF-1.4 x", "application/pdf")
    assert s.get("orgs/1/attachments/a.pdf") == b"%PDF-1.4 x"
    assert [k for k, _ in s.list("orgs/1/")] == ["orgs/1/attachments/a.pdf"]
    s.delete("orgs/1/attachments/a.pdf")
    with pytest.raises(FileNotFoundError):
        s.get("orgs/1/attachments/a.pdf")


@pytest.mark.parametrize("bad", ["../x", "/etc/passwd", "orgs/../../x", "C:\\x", ""])
def test_local_storage_rejects_traversal(tmp_path, bad):
    with pytest.raises(ValueError):
        LocalStorage(str(tmp_path)).put(bad, b"x", "text/plain")


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def list_objects_v2(self, Bucket, Prefix):
        import datetime as dt
        return {"Contents": [{"Key": k, "LastModified": dt.datetime(2026, 1, 1)}
                             for k in self.objects if k.startswith(Prefix)]}


def test_s3_storage_roundtrip():
    fake = FakeS3()
    s = S3Storage("bucket", fake)
    s.put("backups/a.enc", b"data", "application/octet-stream")
    assert s.get("backups/a.enc") == b"data"
    assert [k for k, _ in s.list("backups/")] == ["backups/a.enc"]


def test_sqlite_backup_is_encrypted_and_restorable(db, tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr("app.backups.BACKUP_ENCRYPTION_KEY", key)
    from app.backups import backup_database
    storage = LocalStorage(str(tmp_path))
    result = backup_database(db, storage)
    assert result["status"] == "success", result
    blob = storage.get(result["key"])
    assert b"CREATE TABLE" not in blob  # encrypted at rest
    assert b"CREATE TABLE" in Fernet(key.encode()).decrypt(blob)


def test_attachment_upload_and_download_use_storage(client, db, auth_user, tmp_path, monkeypatch):
    from app.auth import build_session_data, serializer
    from app.models import Attachment, DataCategory, DataRecord, Organization
    storage = LocalStorage(str(tmp_path))
    monkeypatch.setattr("app.routes.records.get_storage", lambda: storage)
    cat = DataCategory(organization_id=1, name="C", retention_period_days=30)
    db.add(cat); db.commit()
    rec = DataRecord(organization_id=1, category_id=cat.id, record_reference="R1")
    db.add(rec); db.commit()
    auth_user.email_verified_at = auth_user.created_at; db.commit()
    client.cookies.set("SafeData_session", serializer.dumps(build_session_data(auth_user, db.get(Organization, 1))))
    pdf = b"%PDF-1.4\n%test\n"
    r = client.post(f"/attachments/upload/{rec.id}", files={"file": ("e.pdf", pdf, "application/pdf")},
                    follow_redirects=False)
    assert r.status_code == 303
    att = db.query(Attachment).one()
    assert att.stored_filename.startswith("orgs/1/attachments/")
    assert storage.get(att.stored_filename) == pdf
    d = client.get(f"/attachments/download/{att.id}")
    assert d.status_code == 200 and d.content == pdf
```

- [ ] **Step 3: Run to verify failure** — `python -m pytest tests/test_foundation_storage.py -v` → FAIL.

- [ ] **Step 4: Implement `app/core/storage.py`**

```python
"""Object storage: local filesystem (dev) or S3-compatible (Cloudflare R2 / DO Spaces)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _check_key(key: str) -> str:
    if not key or not _SAFE_KEY.match(key) or ".." in key.split("/") or "\\" in key:
        raise ValueError(f"unsafe storage key: {key!r}")
    return key


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def list(self, prefix: str) -> list[tuple[str, datetime]]: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / _check_key(key)).resolve()
        if self.root not in p.parents:
            raise ValueError(f"unsafe storage key: {key!r}")
        return p

    def put(self, key, data, content_type):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key):
        return self._path(key).read_bytes()

    def delete(self, key):
        self._path(key).unlink(missing_ok=True)

    def list(self, prefix):
        base = self.root
        out = []
        for f in base.rglob("*"):
            if f.is_file():
                k = f.relative_to(base).as_posix()
                if k.startswith(prefix):
                    out.append((k, datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).replace(tzinfo=None)))
        return sorted(out)


class S3Storage:
    def __init__(self, bucket: str, client):
        self.bucket, self.client = bucket, client

    def put(self, key, data, content_type):
        self.client.put_object(Bucket=self.bucket, Key=_check_key(key), Body=data, ContentType=content_type)

    def get(self, key):
        try:
            return self.client.get_object(Bucket=self.bucket, Key=_check_key(key))["Body"].read()
        except Exception as exc:
            raise FileNotFoundError(key) from exc

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=_check_key(key))

    def list(self, prefix):
        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return sorted((o["Key"], o["LastModified"].replace(tzinfo=None)) for o in resp.get("Contents", []))


def get_storage() -> Storage:
    from app import config
    if config.STORAGE_BACKEND == "s3":
        import boto3
        client = boto3.client("s3", endpoint_url=config.S3_ENDPOINT_URL or None, region_name=config.S3_REGION,
                              aws_access_key_id=config.S3_ACCESS_KEY_ID,
                              aws_secret_access_key=config.S3_SECRET_ACCESS_KEY)
        return S3Storage(config.S3_BUCKET, client)
    return LocalStorage(config.STORAGE_LOCAL_ROOT)
```

(Cloudflare R2 encrypts all objects at rest by default; backups are additionally Fernet-encrypted by the app.)

- [ ] **Step 5: Rewrite `app/backups.py`**

```python
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
```

Update any existing caller/test of the old signature: `grep -rn "backup_database\|prune_backups" app tests` and change calls to pass `get_storage()` / a `LocalStorage(tmp_path)`; update `tests/test_backups.py` assertions from file paths to storage keys.

- [ ] **Step 6: Attachments via storage** in `app/routes/records.py`:
  - add `from app.core.storage import get_storage` at top;
  - in `handle_attachment_upload` replace the `stored_filename`/`dest_path`/`open(...)` block with:

```python
    stored_filename = f"orgs/{org_id}/attachments/{uuid.uuid4().hex}.{ext}"
    get_storage().put(stored_filename, content, file.content_type or "application/octet-stream")
```
  - in `handle_attachment_download` replace everything after the `if not att:` check with:

```python
    key = att.stored_filename if "/" in att.stored_filename else f"attachments/{att.stored_filename}"  # legacy local files
    try:
        data = get_storage().get(key)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="File not found on storage server.")
    safe_name = "".join(c for c in att.original_filename if c.isalnum() or c in "._-") or "attachment"
    return Response(content=data, media_type=att.mime_type,
                    headers={"Content-Disposition": f'attachment; filename="{safe_name}"'})
```
  - import `Response` from `fastapi.responses`; remove the now-unused `FileResponse` import if nothing else uses it.

- [ ] **Step 7: Switch the worker backup job** to the Task 4 code (`backup_database(db, get_storage())`) and add pruning: after a successful backup call `prune_backups(db, get_storage(), 30)` and include `"pruned"` in the returned dict.

- [ ] **Step 8: Run tests** — `pip install boto3==1.40.0; python -m pytest tests/test_foundation_storage.py tests/test_backups.py -v` → pass; full suite passes.

- [ ] **Step 9: Commit**

```bash
git add retention_py/app/core/storage.py retention_py/app/config.py retention_py/app/backups.py retention_py/app/routes/records.py retention_py/app/worker/jobs.py retention_py/requirements.txt retention_py/tests
git commit -m "feat(storage): S3-compatible object storage for attachments; encrypted PostgreSQL/SQLite backups"
```

---

### Task 6: Domain portability and canonical host redirects

Fixes F18 / SD-10-001; implements spec §5.8.

**Files:**
- Modify: `retention_py/app/config.py`, `retention_py/app/middleware.py` (add `CanonicalHostMiddleware`), `retention_py/main.py`, every file containing `3consulting.com` (find with grep)
- Test: `retention_py/tests/test_foundation_domain.py`

**Interfaces:**
- Produces: config `APP_URL`, `APP_HOST` (derived), `LEGACY_HOSTS: list[str]`, `MAIL_DOMAIN`, `SMTP_FROM_EMAIL` default `noreply@{MAIL_DOMAIN}`, `SUPPORT_EMAIL`, `SECURITY_EMAIL`; `CanonicalHostMiddleware`.

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_foundation_domain.py
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_no_wrong_domain_literals_in_app():
    offenders = [str(p) for p in APP_DIR.rglob("*") if p.suffix in (".py", ".html")
                 and "3consulting.com" in p.read_text(encoding="utf-8", errors="replace")]
    assert offenders == []


def test_legacy_host_redirects_to_canonical(client, monkeypatch):
    monkeypatch.setattr("app.middleware.LEGACY_HOSTS", ["old.example.com"])
    monkeypatch.setattr("app.middleware.APP_URL", "https://safedata.3consult-ng.com")
    r = client.get("/login?next=/records", headers={"host": "old.example.com"}, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://safedata.3consult-ng.com/login?next=/records"


def test_canonical_host_not_redirected(client):
    r = client.get("/login", follow_redirects=False)
    assert r.status_code == 200


def test_default_sender_uses_mail_domain():
    from app import config
    assert config.SMTP_FROM_EMAIL == f"noreply@{config.MAIL_DOMAIN}"  # SMTP_FROM_EMAIL unset in tests
```

- [ ] **Step 2: Run to verify failure** — FAIL (literals present; middleware missing).

- [ ] **Step 3: Config** — in `app/config.py` replace the `APP_URL` line and SMTP sender defaults:

```python
APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8200").rstrip("/")
from urllib.parse import urlparse as _urlparse
APP_HOST = _urlparse(APP_URL).hostname or "127.0.0.1"
LEGACY_HOSTS = [h.strip().lower() for h in os.getenv("LEGACY_HOSTS", "").split(",") if h.strip()]
MAIL_DOMAIN = os.getenv("MAIL_DOMAIN", "safedata.3consult-ng.com")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", f"support@{MAIL_DOMAIN}")
SECURITY_EMAIL = os.getenv("SECURITY_EMAIL", "security@3consult-ng.com")
```
and `SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", f"noreply@{MAIL_DOMAIN}")`, `SMTP_FROM_NAME` default `"SafeData by 3Consulting"`. Move the `APP_NAME` default to `"SafeData by 3Consulting"`.

- [ ] **Step 4: Middleware** — add to `app/middleware.py` (import `APP_URL, LEGACY_HOSTS` from config at top):

```python
class CanonicalHostMiddleware:
    """301-redirect requests for legacy hosts to APP_URL, preserving path and query."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and LEGACY_HOSTS:
            host = dict(scope.get("headers") or []).get(b"host", b"").decode("latin-1").split(":")[0].lower()
            if host in LEGACY_HOSTS:
                qs = scope.get("query_string", b"").decode("latin-1")
                location = APP_URL + scope.get("path", "/") + (f"?{qs}" if qs else "")
                await send({"type": "http.response.start", "status": 301,
                            "headers": [(b"location", location.encode("latin-1"))]})
                await send({"type": "http.response.body", "body": b""})
                return
        await self.app(scope, receive, send)
```
Register in `main.py` as the outermost middleware (add after `RequestIdMiddleware`). If `ALLOWED_HOSTS` is not `*`, append `LEGACY_HOSTS` to the trusted host list so redirects are reachable.

- [ ] **Step 5: Replace literals** — run `Select-String -Path app\*.py,app\routes\*.py,app\templates\*.html -Pattern "3consulting.com"`; replace each link with `{APP_URL}` (Python f-strings) or `{{ app_url }}` (templates; add `templates.env.globals["app_url"] = APP_URL` where those templates' `Jinja2Templates` instance is created), and each email address with `SUPPORT_EMAIL`/`SECURITY_EMAIL`. Update `/.well-known/security.txt` content (if served) to use `SECURITY_EMAIL`.

- [ ] **Step 6: Run tests** — new tests pass; full suite passes.

- [ ] **Step 7: Commit**

```bash
git add retention_py/app retention_py/main.py retention_py/tests/test_foundation_domain.py
git commit -m "feat(config): configurable canonical domain, legacy-host 301 redirects, 3consult-ng.com defaults"
```

---

### Task 7: Deep health check, Docker image, local stack, Render blueprint

**Files:**
- Modify: `retention_py/main.py` (`/healthz`)
- Create: `retention_py/Dockerfile`, `retention_py/.dockerignore`, `retention_py/docker-compose.yml`
- Modify: `retention_py/render.yaml`
- Test: `retention_py/tests/test_foundation_health.py`

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_foundation_health.py
def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["database"] == "ok"


def test_healthz_degraded_when_db_down(client, monkeypatch):
    import main

    def broken():
        raise RuntimeError("db down")
    monkeypatch.setattr(main, "_db_ping", broken)
    r = client.get("/healthz")
    assert r.status_code == 503
    assert r.json() == {"status": "degraded", "database": "error"}
```

- [ ] **Step 2: Run to verify failure** — FAIL (`database` key missing).

- [ ] **Step 3: Implement in `main.py`** — replace the `/healthz` handler:

```python
from sqlalchemy import text as _sql_text


def _db_ping() -> None:
    db = SessionLocal()
    try:
        db.execute(_sql_text("SELECT 1"))
    finally:
        db.close()


@app.get("/healthz")
def system_healthz():
    try:
        _db_ping()
    except Exception:
        logging.getLogger("safedata.health").exception("database ping failed")
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "error"})
    return JSONResponse(content={"status": "ok", "database": "ok", "service": "SafeData"})
```
(`import logging` at top of `main.py` if absent.)

- [ ] **Step 4: `Dockerfile`**

```dockerfile
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update && apt-get install -y --no-install-recommends postgresql-client-16 \
 && apt-get purge -y gnupg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN useradd --create-home --uid 10001 safedata && chown -R safedata /app
USER safedata
EXPOSE 8200
CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8200", "--workers", "2", "--timeout", "120"]
```

`.dockerignore`:
```
__pycache__/
*.pyc
.pytest_cache/
*.db
storage/
scratch/
cloudflared.exe
tests/
```

- [ ] **Step 5: `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    environment: { POSTGRES_USER: safedata, POSTGRES_PASSWORD: safedata, POSTGRES_DB: safedata }
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck: { test: ["CMD-SHELL", "pg_isready -U safedata"], interval: 5s, retries: 10 }
  mail:
    image: axllent/mailpit:v1.20
    ports: ["8025:8025", "1025:1025"]
  app:
    build: .
    command: sh -c "python -m app.cli migrate && uvicorn main:app --host 0.0.0.0 --port 8200 --reload"
    environment: &env
      APP_ENV: local
      APP_URL: http://localhost:8200
      DATABASE_URL: postgresql+psycopg2://safedata:safedata@db:5432/safedata
      SMTP_HOST: mail
      SMTP_PORT: "1025"
      SMTP_SECURE: none
    ports: ["8200:8200"]
    volumes: [".:/app"]
    depends_on: { db: { condition: service_healthy } }
  worker:
    build: .
    command: python -m app.worker
    environment: *env
    volumes: [".:/app"]
    depends_on: { db: { condition: service_healthy } }
volumes:
  pgdata:
```

- [ ] **Step 6: `render.yaml`**

```yaml
databases:
  - name: safedata-db
    region: frankfurt
    plan: basic-1gb
    postgresMajorVersion: "16"
services:
  - type: web
    name: safedata-web
    runtime: docker
    region: frankfurt
    dockerfilePath: ./Dockerfile
    preDeployCommand: python -m app.cli migrate
    healthCheckPath: /healthz
    envVars: &env
      - { key: APP_ENV, value: production }
      - { key: SECRET_KEY, generateValue: true }
      - { key: BACKUP_ENCRYPTION_KEY, sync: false }
      - { key: APP_URL, value: https://safedata.3consult-ng.com }
      - { key: ALLOWED_HOSTS, value: safedata.3consult-ng.com }
      - { key: TRUSTED_PROXIES, sync: false }
      - { key: DATABASE_URL, fromDatabase: { name: safedata-db, property: connectionString } }
      - { key: STORAGE_BACKEND, value: s3 }
      - { key: S3_BUCKET, sync: false }
      - { key: S3_ENDPOINT_URL, sync: false }
      - { key: S3_ACCESS_KEY_ID, sync: false }
      - { key: S3_SECRET_ACCESS_KEY, sync: false }
      - { key: SMTP_HOST, sync: false }
      - { key: SMTP_USER, sync: false }
      - { key: SMTP_PASS, sync: false }
  - type: worker
    name: safedata-worker
    runtime: docker
    region: frankfurt
    dockerfilePath: ./Dockerfile
    dockerCommand: python -m app.worker
    envVars: *env
```
Note in the commit body: `SECRET_KEY` must be identical for web and worker — after first deploy, copy the generated value into the worker (or use an env group). Verify field names against Render's current Blueprint spec before first deploy (Phase 6).

- [ ] **Step 7: Verify the stack** — `docker compose up -d --build`; `curl http://localhost:8200/healthz` → `{"status":"ok","database":"ok",...}`; `docker compose logs worker` shows `worker started` and JSON-less plain lines (APP_ENV=local); `docker compose down`.

- [ ] **Step 8: Run tests and commit**

```bash
python -m pytest tests/test_foundation_health.py -v
git add retention_py/main.py retention_py/Dockerfile retention_py/.dockerignore retention_py/docker-compose.yml retention_py/render.yaml retention_py/tests/test_foundation_health.py
git commit -m "feat(ops): deep health check, Docker image with pg_dump 16, compose stack, Render blueprint (web+worker+Postgres, Frankfurt)"
```

---

### Task 8: PostgreSQL test run and CI

**Files:**
- Create: `retention_py/pyproject.toml`, `.github/workflows/ci.yml`
- Modify: any app/test code that fails on PostgreSQL (determined in Step 2)

- [ ] **Step 1: Start PostgreSQL** — `docker compose up -d db` (from `retention_py/`).

- [ ] **Step 2: Run the suite on PostgreSQL**

```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg2://safedata:safedata@localhost:5432/safedata"
python -m pytest tests -q -p no:cacheprovider
```
For each failure, find the root cause before changing code (use superpowers:systematic-debugging). Known PostgreSQL differences to check first: string comparison on Enum columns, `func.current_date()` vs Python `date`, integer/boolean coercion (`== 1` vs `is True`), ordering without `ORDER BY` (tests assuming insertion order — add explicit `order_by`), JSON equality. Fix the code, not the assertion, unless the test encoded SQLite-only behaviour. Commit each fix separately: `fix(pg): <what>`.

- [ ] **Step 3: `pyproject.toml`** (lint scope starts with new code and widens as modules are refactored):

```toml
[tool.ruff]
line-length = 120
target-version = "py312"
include = ["app/core/**/*.py", "app/worker/**/*.py", "app/cli.py", "tests/test_foundation_*.py", "../tools/**/*.py"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "S"]
ignore = ["S101"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: `.github/workflows/ci.yml`**

```yaml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-24.04
    defaults: { run: { working-directory: retention_py } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install ruff==0.13.0
      - run: ruff check . && ruff format --check .
  test:
    runs-on: ubuntu-24.04
    defaults: { run: { working-directory: retention_py } }
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_USER: safedata, POSTGRES_PASSWORD: safedata, POSTGRES_DB: safedata_test }
        ports: ["5432:5432"]
        options: --health-cmd "pg_isready -U safedata" --health-interval 5s --health-retries 10
    env:
      TEST_DATABASE_URL: postgresql+psycopg2://safedata:safedata@localhost:5432/safedata_test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip, cache-dependency-path: retention_py/requirements.txt }
      - run: pip install -r requirements.txt
      - run: python -m pytest tests -q -p no:cacheprovider
  security:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install pip-audit && pip-audit -r retention_py/requirements.txt
      - uses: gitleaks/gitleaks-action@v2
        env: { GITHUB_TOKEN: "${{ secrets.GITHUB_TOKEN }}" }
```

- [ ] **Step 5: Run lint locally** — `pip install ruff==0.13.0; ruff check .; ruff format .` and fix findings in the included paths.

- [ ] **Step 6: Commit and push the branch; confirm all three CI jobs pass**

```bash
git add retention_py/pyproject.toml .github/workflows/ci.yml retention_py
git commit -m "ci: lint, PostgreSQL test suite, dependency and secret scanning"
git push -u origin safedata-launch
```
Then `gh run watch` (or the Actions tab). If `pip-audit` reports vulnerable pins, bump each to the nearest fixed version, re-run the suite, and commit `chore(deps): bump <pkg> to <version> (CVE-…)`.
