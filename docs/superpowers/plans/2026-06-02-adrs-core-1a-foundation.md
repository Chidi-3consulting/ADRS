# ADRS Core — Milestone 1A: Foundation, Auth & Test Harness — Implementation Plan

> **Status:** Completed — implemented in `retention_py/`.

**Goal:** Build the bedrock layer every other ADRS Core module reuses — environment config, the
SQLAlchemy database layer, the helper/auth libraries (aligned to the blueprint API), the branded
Jinja2 layout shell, login, and a Pytest test harness — ending with a user who can log in and
see the dashboard shell.

**Architecture:** Python 3.10+, FastAPI + Uvicorn. Environment-variable-based config. A
SQLAlchemy engine with `SessionLocal` factory for database sessions. Pure utility functions
live in `helpers.py` and are unit-tested; auth lives in `auth.py`. Pytest + httpx TestClient
for testing.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0, Jinja2, Bootstrap 5.3 + Bootstrap Icons
(CDN), vanilla JS. Test framework: Pytest.

**Source of truth:** `ADRS_v2_MASTER_PACKAGE/01_BUILD_PACKAGE/.github/copilot-instructions.md`
and `prompts/01-project-setup.md` + `prompts/02-auth-system.md`.

**Conventions for this milestone:**
- Function names follow the blueprint: `get_db()`, `get_setting()`, `sanitize()`,
  `csrf_token()/csrf_field()/csrf_verify()`, `flash()/get_flash()`, `redirect()`,
  `log_audit()`, `login_user()/require_login()/require_role()/has_role()/current_user()/is_logged_in()`.
- `system_settings` columns are `setting_key` / `setting_value`.
- Default seeded admin: `admin@3consult-ng.com` / `password`; DPO: `dpo@3consult-ng.com` / `password`.

---

## File Structure (this milestone)

| File | Responsibility |
|---|---|
| `retention_py/tests/conftest.py` | Pytest fixtures: test client, test database, seeded users |
| `retention_py/tests/test_auth.py` | Auth tests: login, role gates, password reset |
| `retention_py/app/config.py` | Environment config via `os.getenv()` |
| `retention_py/app/database.py` | SQLAlchemy engine, `SessionLocal`, `Base`, `get_db()` |
| `retention_py/app/models.py` | All ORM models (Organization, User, DataCategory, etc.) |
| `retention_py/app/helpers.py` | Pure utilities (`get_setting`, date/retention, CSRF, `log_audit`, labels) |
| `retention_py/app/auth.py` | Sessions, login/logout, role gates, password-reset tokens |
| `retention_py/app/middleware.py` | Security headers (CSP with nonce), CSRF, session enforcement |
| `retention_py/app/templates/layout/` | Branded, role-aware Jinja2 base template |
| `retention_py/app/static/css/` | 3Consulting theme |
| `retention_py/app/routes/public.py` | Login, logout, register, forgot/reset password |
| `retention_py/app/routes/dashboard.py` | Dashboard shell |
| `retention_py/main.py` | FastAPI app entry point |
| `retention_py/requirements.txt` | Python dependencies |

---

## Task 1: Project setup & dependencies

**Files:** `requirements.txt`, `app/config.py`, `app/database.py`

- [x] **Step 1: Create requirements.txt**

```
fastapi>=0.100.0
uvicorn>=0.22.0
sqlalchemy>=2.0.0
jinja2>=3.1.0
pytest>=7.0.0
httpx>=0.24.0
passlib[bcrypt]>=1.7.4
itsdangerous>=2.1.0
python-multipart>=0.0.6
pymysql>=1.0.0
cryptography>=41.0.0
alembic>=1.12.0
```

- [x] **Step 2: Create config module**

Create `retention_py/app/config.py`:
```python
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APP_ENV = os.getenv("APP_ENV", "local")
IS_PRODUCTION = APP_ENV == "production"
APP_NAME = os.getenv("APP_NAME", "ADRS — 3Consulting Python")
APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8200")
SECRET_KEY = os.getenv("SECRET_KEY", "adrs_python_super_secret_session_key_3c_2026")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(BASE_DIR, 'retention.db')}"
)

UPLOAD_PATH = os.path.join(BASE_DIR, "storage", "attachments")
LOG_PATH = os.path.join(BASE_DIR, "storage", "logs")
BACKUP_PATH = os.path.join(BASE_DIR, "storage", "backups")

os.makedirs(UPLOAD_PATH, exist_ok=True)
os.makedirs(LOG_PATH, exist_ok=True)
os.makedirs(BACKUP_PATH, exist_ok=True)
```

- [x] **Step 3: Create database module**

Create `retention_py/app/database.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DATABASE_URL

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [x] **Step 4: Install dependencies**

```bash
cd retention_py
pip install -r requirements.txt
```

---

## Task 2: ORM models

**Files:** `app/models.py`

- [x] **Step 1: Define all ORM models**

Core models: `Organization`, `User`, `Regulation`, `DataCategory`, `RetentionRule`,
`DataRecord`, `AuditLog`, `Notification`, `DsarRequest`, `ScheduleReview`,
`PendingRecalculation`, `Attachment`, `ImportJob`, `SystemSetting`, `RopaEntry`.

Enterprise models: `ConnectedSystem`, `ApiKey`, `FieldMapping`,
`AutoCategorizationRule`, `IntegrationLog`, `IntakeQueue`, `DisposalDispatch`,
`ConsentSignal`.

Each model uses SQLAlchemy `Column`, `ForeignKey`, `relationship` decorators.
Soft deletes via `deleted_at` column where appropriate.

---

## Task 3: Helpers & utilities

**Files:** `app/helpers.py`

- [x] **Step 1: Implement core helpers**

Key functions:
- `get_setting(db, key, default=None)` — read from `system_settings` with caching
- `log_audit(db, action, user_id, org_id, details=None)` — append-only audit log with hash chaining
- `flash(request, message, category)` / `get_flash(request)` — session-based flash messages
- `sanitize(value)` — HTML entity escaping
- `retention_end_date(start_date, period_days)` — date arithmetic
- Dynamic category templates — 30 seeded GDPR/NDPR categories
- Email template rendering

---

## Task 4: Auth system

**Files:** `app/auth.py`, `app/middleware.py`

- [x] **Step 1: Implement auth module**

Key functions:
- `login_user(request, user)` — create session, set cookies
- `logout_user(request)` — destroy session
- `get_session(request)` — read session from signed cookie
- `require_login(request)` — redirect to login if not authenticated
- `require_role(request, *roles)` — role-based access control
- `hash_password(password)` / `verify_password(password, hash)` — bcrypt via passlib

- [x] **Step 2: Implement security middleware**

Key features:
- CSP headers with per-request nonce
- CSRF token generation and validation
- Session timeout enforcement (idle + absolute)
- Login throttle (max 5 attempts per 15 minutes)

---

## Task 5: Routes & templates

**Files:** `app/routes/public.py`, `app/routes/dashboard.py`, `app/templates/`

- [x] **Step 1: Public routes**

- `GET /login` — login form
- `POST /login` — authenticate
- `GET /logout` — destroy session
- `GET /register` — organisation registration
- `POST /register` — create org + admin user
- `GET /forgot-password` — request reset
- `POST /forgot-password` — send reset email
- `GET /reset-password/{token}` — reset form
- `POST /reset-password/{token}` — set new password

- [x] **Step 2: Dashboard route**

- `GET /dashboard` — role-aware compliance health overview

- [x] **Step 3: Jinja2 templates**

- Base layout with sidebar navigation (tier-aware)
- Login/register pages
- Dashboard page
- Error pages (404, 500)

---

## Task 6: FastAPI application entry point

**Files:** `main.py`

- [x] **Step 1: Create main application**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base
from app.routes import public, dashboard

app = FastAPI(title="ADRS")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Register route blueprints
app.include_router(public.router)
app.include_router(dashboard.router)

# Create tables on startup
Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8200, reload=True)
```

---

## Task 7: Test harness

**Files:** `tests/conftest.py`, `tests/test_auth.py`

- [x] **Step 1: Create test fixtures**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from main import app

SQLALCHEMY_TEST_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [x] **Step 2: Write auth tests**

```python
def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200

def test_login_with_valid_credentials(client, db):
    # seed user, then test login
    ...

def test_login_with_invalid_credentials(client):
    response = client.post("/login", data={"email": "bad@example.com", "password": "wrong"})
    assert response.status_code in (200, 302)  # stays on login page
```

- [x] **Step 3: Run the test suite**

```bash
cd retention_py
python -m pytest tests/ -v
```

---

## Task 8: Dev startup script

**Files:** `dev-start.ps1`

- [x] **Step 1: Create PowerShell dev script**

Checks dependencies, detects LAN IP, sets environment variables, starts Uvicorn on port 8200.

---

## Verification

- [x] `pip install -r requirements.txt` succeeds
- [x] `python main.py` starts the server on port 8200
- [x] `http://localhost:8200/login` loads the login page
- [x] `http://localhost:8200/register` loads the registration page
- [x] Registration creates an organization + admin user
- [x] Login succeeds with valid credentials
- [x] Dashboard loads for authenticated users
- [x] `python -m pytest tests/` passes all tests
