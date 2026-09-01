# SafeData — Developer & Extensibility Guide

This document provides software engineers, devops specialists, and internal contributors with a complete technical breakdown of the `retention_py` codebase, all 27+ object models, middleware architecture, extension points, multi-tenant isolation patterns, and automated testing framework.

---

## 1. Codebase Directory Organisation

```
retention_py/
├── alembic/                  # Alembic DB migration scripts & versions
├── alembic.ini               # Alembic configuration
├── dev-start.ps1             # Local PowerShell environment launcher
├── main.py                   # FastAPI entry point, lifespan scheduler, middleware registration
├── requirements.txt          # Python dependencies
├── retention.db              # Local SQLite database (dev)
├── test.db                   # Isolated test database (created/destroyed by pytest)
├── storage/                  # Application runtime storage (gitignored)
│   ├── attachments/          # File attachments for data records
│   ├── backups/              # Automated database backup dumps
│   └── logs/                 # Application logs
├── app/
│   ├── auth.py               # Password hashing (bcrypt), session management, login throttle, email verification
│   ├── backups.py            # SQLite/MySQL automated backup runner & pruning
│   ├── config.py             # Configuration loader (env vars & security constants)
│   ├── database.py           # SQLAlchemy engine, session factory, get_db() dependency
│   ├── engine.py             # Retention engine, disposal logic, analytics, reports, lifecycle, webhooks
│   ├── enterprise.py         # Enterprise: API key lifecycle, intake queue, disposal dispatch, consent signals
│   ├── helpers.py            # Audit logging (log_audit), category seeds, country/regulation maps, pricing
│   ├── middleware.py         # SecurityHeaders, CSRF, SessionEnforcement middleware classes
│   ├── models.py             # 27+ Declarative SQLAlchemy ORM models
│   ├── routes/               # FastAPI APIRouter blueprints
│   │   ├── api_v1.py         # Enterprise REST API endpoints (/api/v1/*)
│   │   ├── app_pages.py      # Core web pages (audit, DSAR, users, settings, breach, DPIA, consent)
│   │   ├── categories.py     # Data Category management routes
│   │   ├── dashboard.py      # Role-based dashboard views
│   │   ├── import_records.py # Bulk CSV importer routes
│   │   ├── integrations_routes.py # Enterprise integration UI routes
│   │   ├── platform.py       # Multi-tenant platform admin routes (/platform/*)
│   │   ├── public.py         # Auth routes (login, register, reset password, invite accept)
│   │   ├── recalculations.py # Category rule change recalculation queue
│   │   ├── records.py        # Data Records lifecycle management routes
│   │   └── ropa.py           # RoPA (Article 30) register routes with sub-processor management
│   ├── static/               # Static assets (CSS, JS, images)
│   └── templates/            # Jinja2 HTML templates
├── scratch/                  # Development scratch files
└── tests/                    # Pytest test suite (26 test modules)
```

---

## 2. Core Object Models (`app/models.py`)

SafeData uses **SQLAlchemy 2.0 Declarative Models**. The system contains **27+ models** organised into functional groups.

### 2.1 Entity Relationship Overview

```
┌─────────────────┐       1:N       ┌──────────────────┐       1:N       ┌─────────────────┐
│  Organization   │ ──────────────> │       User       │ ──────────────> │   AuditLog      │
└────────┬────────┘                 └──────────────────┘                 └─────────────────┘
         │                                   │
         │ 1:N                               │ 1:N
         ▼                                   ▼
┌─────────────────┐       1:N       ┌──────────────────┐      1:N    ┌──────────────────┐
│  DataCategory   │ ──────────────> │    DataRecord    │ ──────────> │   Attachment     │
└────────┬────────┘                 └──────────────────┘             └──────────────────┘
         │
         │ 1:N
         ▼
┌──────────────────────┐
│ CategoryRetentionRule │
└──────────────────────┘

┌─────────────────┐       1:N       ┌──────────────────┐
│ ConnectedSystem │ ──────────────> │     ApiKey       │
└────────┬────────┘                 └──────────────────┘
         │
         │ 1:N
         ▼
┌───────────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ AutoCategorizationRule│   │   FieldMapping   │   │  IntegrationLog  │
└───────────────────────┘   └──────────────────┘   └──────────────────┘

┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│   RopaEntry      │   │  DpiaAssessment  │   │  BreachIncident  │
│   └─RopaProcessor│   └──────────────────┘   └──────────────────┘
└──────────────────┘

┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  ConsentReceipt  │   │ WebhookEndpoint  │   │  ConsentSignal   │
└──────────────────┘   └──────────────────┘   └──────────────────┘
```

### 2.2 Complete Model Reference

#### Multi-Tenancy & Identity

| Model | Table | Description |
| :--- | :--- | :--- |
| `Organization` | `organizations` | Primary tenant. Properties: `name`, `slug`, `primary_domain`, `country`, `tier` (core/enterprise), `status` (active/trial/suspended), `subscription_status` (trial/active/past_due/cancelled), `billing_email`, `paystack_customer_code`, `enterprise_licence_key`, `trial_ends_at` |
| `User` | `users` | User account. Roles: `admin`, `dpo`, `data_owner`. Flags: `is_platform_admin`, `must_change_password`, `twofa_enabled`. Fields: `email_verified_at`, `verification_token_hash`, `twofa_secret`, `twofa_recovery` (JSON), `deleted_at` (soft delete) |
| `Regulation` | `regulations` | Reference table for supported regulations. Fields: `code` (PK), `name`, `country`, `continent`, `is_active` |
| `OrganizationInvitation` | `organization_invitations` | Token-based user invitation system with `token_hash`, `expires_at`, `accepted_at`, `revoked_at` |
| `LoginAttempt` | `login_attempts` | Brute-force throttling records: `email`, `ip_address`, `success`, `created_at` |
| `PasswordReset` | `password_resets` | Token-based password reset and email verification: `token_hash`, `expires_at`, `used` |

#### Retention Core

| Model | Table | Description |
| :--- | :--- | :--- |
| `DataCategory` | `data_categories` | Retention schedule with lawful basis, disposal trigger, retention period, review frequency, owner assignment. Source: `seeded` or `custom`. Soft-deletable |
| `CategoryRetentionRule` | `category_retention_rules` | Per-institution-type retention rule overrides. Fields: `institution_type` (all/banking/insurance/healthcare/etc.), `processing_purpose`, `sort_order`, `is_default` |
| `DataRecord` | `data_records` | Individual data entry with full lifecycle tracking: `status` (active/due_review/disposal_requested/legal_hold/disposed), `legal_hold` flag, `consent_withdrawn_at`, `disposal_requested_at/by`, `disposed_at/by`, `category_reassigned_at/by`, `escalation_sent_at` |
| `Attachment` | `attachments` | File attachments for records: `original_filename`, `stored_filename`, `file_size`, `mime_type` |
| `ScheduleReview` | `schedule_reviews` | Category review log: `outcome` (no_change/updated/flagged/escalated), `next_review_date` |
| `PendingRecalculation` | `pending_recalculations` | Records queued for retention date recalculation: `old_retention_end_date`, `new_retention_end_date`, `status` (pending/recalculate/keep_original/ignored) |
| `ImportJob` | `import_jobs` | Bulk CSV import tracking: `total_rows`, `valid_rows`, `imported_rows`, `skipped_rows`, `error_rows`, `error_report` (JSON) |

#### Compliance & Governance

| Model | Table | Description |
| :--- | :--- | :--- |
| `AuditLog` | `audit_log` | Append-only, hash-chained audit trail: `action`, `entity_type`, `entity_id`, `performed_by`, `details` (JSON), `prev_hash`, `row_hash` |
| `DsarRequest` | `dsar_requests` | Data subject access requests. Types: access, rectification, erasure, restriction, portability, objection. Statuses: open, identity_check, in_progress, completed, rejected, extended |
| `RopaEntry` | `ropa_entries` | Record of Processing Activities (Art. 30): `role_type` (controller/processor), data subjects, recipients, transfers, security measures |
| `RopaProcessor` | `ropa_processors` | Sub-processor records linked to RoPA entries: `processor_name`, `processing_purpose`, `contract_reference` |
| `DpiaAssessment` | `dpia_assessments` | DPIA with risk scoring: necessity, proportionality, likelihood, severity → composite `risk_score` and `risk_level`. Status: draft/in_review/approved/rejected |
| `BreachIncident` | `breach_incidents` | Breach management: `severity` (low/medium/high/critical), `status` (open/contained/notified/closed), `notify_deadline` (72hr), authority and subject notification tracking |
| `ConsentReceipt` | `consent_receipts` | Individual consent events with `purpose`, `lawful_basis`, `channel`, `given_at`, `withdrawn_at`, `receipt_hash` |
| `Notification` | `notifications` | In-app notifications: `type`, `subject`, `message`, `status` (pending/sent/failed), `read_at`, `follow_up_sent_at`, `owner_missing` flag |

#### Enterprise Integration

| Model | Table | Description |
| :--- | :--- | :--- |
| `ConnectedSystem` | `connected_systems` | External system registry: `system_type` (crm/core_banking/hr_platform/etc.), `base_url`, `signing_secret`, `health_status` |
| `ApiKey` | `api_keys` | API keys: `key_hash` (SHA-256), `key_prefix` (first 12 chars), `permissions` (JSON), `rate_limit_per_min`, `expires_at` |
| `FieldMapping` | `field_mappings` | External-to-SafeData field mapping for auto-categorisation: `external_object_type`, `external_field`, `SafeData_field`, `transform` |
| `AutoCategorizationRule` | `auto_categorization_rules` | Rule engine for auto-categorising inbound records: `object_type`, `condition_field`, `condition_value`, `category_id`, `priority` |
| `IntakeQueue` | `intake_queue` | Inbound API record buffer: `batch_id`, `payload` (JSON), `status` (pending/processing/completed/failed/duplicate), `attempts` |
| `DisposalDispatch` | `disposal_dispatches` | Outbound disposal instructions: `dispatch_type`, `endpoint_url`, `payload`, `status` (pending/sent/confirmed/failed), `attempts` |
| `ConsentSignal` | `consent_signals` | Inbound consent events from external systems: `signal_type` (withdrawal/restriction/erasure_request), `status` (pending/matched/processed/unmatched/error) |
| `WebhookEndpoint` | `webhook_endpoints` | Configurable webhook destinations: `url`, `event_types` (* or CSV), `is_active`, `last_fired_at` |

#### Platform & Billing

| Model | Table | Description |
| :--- | :--- | :--- |
| `EnterpriseLicenceKey` | `enterprise_licence_keys` | Platform-generated licence keys: `key_hash`, `key_prefix`, `redeemed_by_organization_id`, `redeemed_at` |
| `PaymentTransaction` | `payment_transactions` | Payment records: `amount_kobo`, `currency`, `plan_tier`, `status` (pending/success/failed), `provider` (paystack) |
| `SystemSetting` | `system_settings` | Platform-wide settings: `setting_key` (PK), `setting_value` |
| `OrganizationSetting` | `organization_settings` | Per-org settings: `(organization_id, setting_key)` composite PK, `setting_value` |
| `BackupLog` | `backup_log` | Automated backup records: `filename`, `size_bytes`, `status` (success/failed) |

---

## 3. Authentication & Authorisation Helpers

All authentication functions are in `app/auth.py`. **There is no `require_login()` function** — use the helpers below.

### 3.1 Key Auth Functions

| Function | Usage | Description |
| :--- | :--- | :--- |
| `current_user(request)` | `Depends(current_user)` | Returns session dict or raises `401 Unauthorized` |
| `require_role(roles)` | `Depends(require_role(["admin", "dpo"]))` | Returns session dict or raises `403 Permission Denied` if user's role not in list |
| `get_session(request)` | Direct call | Returns parsed session dict from signed cookie (empty dict if no session) |
| `set_session(response, data)` | Direct call | Sets signed session cookie on response |
| `build_session_data(user, org)` | Login flow | Builds canonical session dict with all user/org properties and timestamps |
| `hash_password(password)` | Registration | Returns bcrypt hash string |
| `verify_password(plain, hash)` | Login | Returns True/False |
| `password_policy_error(password)` | Registration/change | Returns error message string or None |
| `login_throttle_seconds(db, email, ip)` | Login | Returns seconds to wait (0 = not throttled) |
| `record_login_attempt(db, email, ip, success)` | Login | Records attempt for throttling |
| `setup_is_complete(db)` | Middleware | Checks if `setup_complete` system setting is set |

### 3.2 Route Protection Patterns

```python
# Pattern 1: Any authenticated user
from app.auth import current_user

@router.get("/profile")
def view_profile(request: Request, session=Depends(current_user), db=Depends(get_db)):
    # session is a dict with user_id, role, org_id, etc.
    ...

# Pattern 2: Specific roles only
from app.auth import require_role

@router.get("/categories/create")
def create_category(request: Request, session=Depends(require_role(["admin", "dpo"])), db=Depends(get_db)):
    ...

# Pattern 3: API endpoint (Bearer token auth)
from app.routes.api_v1 import authenticate_api_key

@router.post("/api/v1/custom")
def api_custom(authorization: str = Header(None), db: Session = Depends(get_db)):
    api_key = authenticate_api_key(db, authorization)
    org_id = api_key.organization_id
    ...
```

---

## 4. Audit Logging Helper

The `log_audit()` function in `helpers.py` is the single entry point for creating audit trail entries:

```python
from app.helpers import log_audit

# Parameters: db, org_id, action, entity_type, entity_id, performed_by, details_dict, ip_address
log_audit(db, org_id, "record_disposed_delete", "data_record", record.id, user_id,
          {"method": "delete", "reason": "Retention expired"}, request.client.host)
```

This function:
1. Fetches the previous audit entry's `row_hash`.
2. Normalises `details` to canonical key-sorted JSON.
3. Computes `row_hash = SHA-256(org_id | action | entity_type | entity_id | performed_by | details_json | ip_address | prev_hash | created_at)`.
4. Inserts the new `AuditLog` row with the hash chain intact.

---

## 5. Settings System

SafeData uses a two-tier settings architecture:

### 5.1 System Settings (`system_settings`)
Platform-wide settings that apply to all organisations. Read with `get_setting(db, key, default)`.

### 5.2 Organisation Settings (`organization_settings`)
Per-tenant overrides. Read with `get_org_setting(db, org_id, key, default)` — this checks org-level first, then falls back to system-level, then to the default.

### 5.3 Key Settings

| Key | Default | Description |
| :--- | :--- | :--- |
| `setup_complete` | *(unset)* | Guard: if missing or != "1", redirect all users to /setup |
| `SafeData_tier` | `core` | Platform tier: `core` or `enterprise` |
| `review_alert_days` | `30` | Days before retention end date to flag for review |
| `escalation_days` | `14` | Days after flagging before escalation to admins |
| `consent_disposal_days` | `30` | Days after consent withdrawal before auto-disposal |
| `ops_webhooks_enabled` | `0` | Enable/disable outbound operational webhooks |
| `require_2fa_roles` | *(empty)* | Comma-separated roles that must enable 2FA |

---

## 6. Multi-Tenant Isolation Patterns

SafeData enforces strict tenant isolation at the database query level:

```python
# Every query MUST include organization_id filter
categories = db.query(DataCategory).filter(
    DataCategory.organization_id == session["org_id"],
    DataCategory.deleted_at == None,
).all()

# org_id comes from the authenticated session (web) or API key (API)
org_id = session["org_id"]       # Web routes
org_id = api_key.organization_id  # API routes
```

Key isolation rules:
- **All models** except `SystemSetting`, `Regulation`, `BackupLog`, `LoginAttempt`, and `PasswordReset` have an `organization_id` foreign key.
- **Session data** includes `org_id` baked into the signed cookie at login.
- **API keys** are scoped to a specific organisation via `ApiKey.organization_id`.
- **Platform Admins** (`is_platform_admin = True`) can access cross-tenant data through the `/platform/*` routes.

---

## 7. Extending the Application

### 7.1 Adding a New Web Route

1. Create a new file in `app/routes/` (e.g., `app/routes/analytics.py`):
```python
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_role

router = APIRouter(prefix="/analytics", tags=["analytics"])
templates = Jinja2Templates(directory="app/templates")

@router.get("", response_class=HTMLResponse)
def view_analytics(
    request: Request,
    session=Depends(require_role(["admin", "dpo"])),
    db: Session = Depends(get_db),
):
    org_id = session["org_id"]
    # Query data scoped to the user's organisation
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "user": session,
    })
```

2. Register the router in `main.py`:
```python
from app.routes import analytics

app.include_router(analytics.router)
```

### 7.2 Adding an Enterprise API Endpoint

All REST API endpoints belong in `app/routes/api_v1.py` under the `/api/v1` prefix:

```python
class CustomEventRequest(BaseModel):
    record_reference: str
    event_type: str

@router.post("/events/custom")
def api_custom_event(
    payload: CustomEventRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    api_key = authenticate_api_key(db, authorization)
    org_id = api_key.organization_id
    # Business logic here...
    return {"status": "success", "event": payload.event_type}
```

### 7.3 Adding a New Background Task

Add to `main.py` following the existing pattern:

```python
async def custom_scheduler_task():
    """Description of what this task does."""
    while True:
        await asyncio.sleep(3600)  # Run every hour
        db = SessionLocal()
        try:
            # Your logic here
            pass
        except Exception as e:
            print(f"[{datetime.now()}] Custom task error: {e}")
        finally:
            db.close()
```

Register in the lifespan context:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing tasks ...
    task6 = asyncio.create_task(custom_scheduler_task())
    yield
    # ... existing cancels ...
    task6.cancel()
```

---

## 8. Template Context Injection

SafeData patches `Jinja2Templates.TemplateResponse` in `main.py` to automatically inject common context variables into all templates:

| Variable | Source | Description |
| :--- | :--- | :--- |
| `request` | Argument | FastAPI Request object |
| `csrf_token` | `request.state.csrf_token` | CSRF token string for forms |
| `csrf_field` | `request.state.csrf_field` | Pre-built `<input type="hidden">` HTML for CSRF |
| `csp_nonce` | `request.state.csp_nonce` | Per-request CSP nonce for inline scripts |
| `is_platform_admin` | Session | Boolean flag for template conditionals |

Templates can reference these without explicit passing:
```html
<form method="POST">
  {{ csrf_field | safe }}
  <script nonce="{{ csp_nonce }}">...</script>
</form>
```

---

## 9. Automated Testing with Pytest

The project includes **26 test modules** in `tests/` covering authentication, engine logic, enterprise features, security, and more.

### 9.1 Running Tests
```bash
cd retention_py

# Run all tests
python -m pytest tests/ -v

# Run a specific test module
python -m pytest tests/test_auth.py -v

# Run tests with output printed
python -m pytest tests/ -s
```

### 9.2 Test Architecture (`tests/conftest.py`)

Tests execute against an isolated SQLite database using FastAPI's `TestClient`:

```python
@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    # Seed default test organisation
    org = Organization(id=1, name="Test Organisation", slug="test-org",
                       primary_domain="test.local", country="NG", tier="core", status="active")
    session.add(org)
    session.commit()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]
```

### 9.3 Test Modules

| Module | Coverage |
| :--- | :--- |
| `test_auth.py` | Login, session management |
| `test_password_policy.py` | Password validation rules |
| `test_login_throttle.py` | Brute-force throttling |
| `test_email_verification.py` | Token generation and verification |
| `test_twofa.py` | TOTP setup and validation |
| `test_invitations.py` | User invitation system |
| `test_categories.py` | Category CRUD operations |
| `test_records_crud.py` | Record lifecycle operations |
| `test_engine.py` / `test_engine_full.py` | Retention engine logic |
| `test_lifecycle.py` | Legal hold, consent withdrawal, disposal |
| `test_enterprise.py` | API keys, intake queue, dispatch |
| `test_audit_chain.py` | Hash chain integrity verification |
| `test_housekeeping.py` | Housekeeping pruning |
| `test_backups.py` | Backup creation and pruning |
| `test_recalculations.py` | Retention date recalculation queue |
| `test_reports.py` | Compliance report generation |
| `test_import.py` | Bulk CSV import |
| `test_security.py` | CSRF, session enforcement |
| `test_settings.py` | System and org settings |
| `test_setup.py` | Initial setup wizard |
| `test_onboarding.py` | Onboarding checklist |
| `test_billing.py` | Subscription management |
| `test_attachments.py` | File upload/download |
| `test_features.py` | Feature integration tests |

### 9.4 Writing New Tests

When writing new tests:
- Use `db` fixture for direct database assertions.
- Use `client` fixture for sending HTTP requests (`client.get()`, `client.post()`).
- Use `auth_user` fixture for a pre-provisioned admin user.
- Always test both positive cases and permission failure cases (e.g., Data Owner attempting Admin actions).
- CSRF is disabled in test mode (`APP_ENV = "test"`).
