# GitHub Copilot Instructions — 3Consulting ADRS v5
# TWO-TIER PRODUCT: CORE + ENTERPRISE
# ================================================================

## Product Identity
Product:    Automated Data Retention System (ADRS)
Company:    3Consulting Limited (Lagos, Nigeria & Oakham, UK)
Version:    2.0 — Two-Tier Edition (Python)
Website:    https://www.3consult-ng.com
Compliance: GDPR (EU/UK) + Nigeria NDPR 2019 + Global equivalents

---

## The Two Tiers — Understand This First

### ADRS Core (Entry Level)
- Standalone compliance portal — no external system connections
- Manual data intake: compliance team registers records via the UI
- Automated enforcement AFTER intake: background scheduler flags, reviews, disposes
- Deployment: 4–6 weeks, no IT integration required
- Target: any organisation with zero current governance
- `tier = 'core'` on the Organization model

### ADRS Enterprise (Integration Tier)
- Everything in Core PLUS an API integration layer
- Automatic data capture: external systems push records via REST API
- Real-time governance: retention clock starts the moment data is created anywhere
- Outbound disposal: ADRS instructs connected systems to delete/anonymise
- Consent signal capture: external systems send withdrawal events to ADRS
- Deployment: 10–14 weeks, requires API integration work
- Target: fintechs, banks, high-volume data processors
- `tier = 'enterprise'` on the Organization model

### Feature Gating
Every Enterprise-only route and background task MUST check the organization tier:
```python
org = db.query(Organization).filter_by(id=session["organization_id"]).first()
if org.tier != "enterprise":
    # Return 403 for API endpoints
    # Redirect to dashboard with flash for UI pages
    # Skip silently for background tasks
```
Never hard-code tier assumptions. Always read from the Organization model.

---

## Tech Stack — ABSOLUTE CONSTRAINTS
- **Language:** Python 3.10+
- **Web Framework:** FastAPI + Uvicorn
- **ORM / Database:** SQLAlchemy 2.0+ (SQLite locally, MySQL/PostgreSQL in production)
- **Templating:** Jinja2
- **Frontend:** Bootstrap 5.3 + Bootstrap Icons + Vanilla JS ES6+
- **Email:** SMTP via Python `smtplib` / configurable mailer
- **Local dev:** Windows (PowerShell dev-start.ps1) — port 8200
- **Migrations:** Alembic
- **Testing:** Pytest + httpx (TestClient)
- **Auth:** bcrypt via passlib, itsdangerous for token signing
- **Background tasks:** APScheduler (built into the FastAPI lifespan)

---

## Complete File Structure (Core + Enterprise)

```
/retention_py/
├── main.py                           ← FastAPI application entry point
├── requirements.txt                  ← Python dependencies
├── dev-start.ps1                     ← Local dev startup script
├── alembic.ini                       ← Alembic migration config
├── alembic/                          ← Database migrations
├── app/
│   ├── config.py                     ← Environment config (env vars)
│   ├── database.py                   ← SQLAlchemy engine + session
│   ├── models.py                     ← All ORM models (20+ tables)
│   ├── auth.py                       ← Sessions, login/logout, role gates
│   ├── helpers.py                    ← Utilities (audit, categories, email, CSRF)
│   ├── engine.py                     ← Retention engine, housekeeping, reports
│   ├── enterprise.py                 ← Enterprise features (API keys, intake, dispatch)
│   ├── middleware.py                 ← Security headers, CSRF, session enforcement
│   ├── backups.py                    ← Automated backup utilities
│   ├── routes/
│   │   ├── public.py                 ← Login, register, forgot/reset password, setup
│   │   ├── dashboard.py              ← Role-aware dashboard
│   │   ├── categories.py             ← Category CRUD
│   │   ├── records.py                ← Records lifecycle
│   │   ├── app_pages.py              ← Audit, DSAR, notifications, settings, users
│   │   ├── api_v1.py                 ← Enterprise REST API endpoints
│   │   ├── integrations_routes.py    ← Enterprise integration management UI
│   │   ├── import_records.py         ← Bulk CSV import
│   │   ├── recalculations.py         ← Pending recalculations queue
│   │   ├── ropa.py                   ← RoPA (Record of Processing Activities)
│   │   └── platform.py              ← Platform admin routes
│   ├── static/                       ← CSS, JS, images
│   └── templates/                    ← Jinja2 templates
├── tests/                            ← Pytest test suite
└── storage/                          ← Attachments, logs, backups (gitignored)
```

---

## Database Tables (Core + Enterprise)

### Core Tables (all tiers)
| Table | Purpose |
|-------|---------|
| `organizations` | Multi-tenant org registry |
| `users` | Auth + roles |
| `password_resets` | Token-based reset |
| `regulations` | Regulatory framework registry |
| `data_categories` | Retention register |
| `retention_rules` | Category-level retention rules |
| `data_records` | Data assets lifecycle |
| `audit_log` | Append-only evidence (31+ actions) |
| `notifications` | Email + in-app alerts |
| `dsar_requests` | DSAR lifecycle |
| `schedule_reviews` | Quarterly review log |
| `pending_recalculations` | B2 DPO queue |
| `attachments` | File metadata |
| `import_jobs` | Bulk import history |
| `system_settings` | Config + SMTP + feature flags |
| `ropa_entries` | Record of Processing Activities |

### Enterprise Tables (tier = 'enterprise' only)
| Table | Purpose |
|-------|---------|
| `connected_systems` | Registry of integrated external systems |
| `api_keys` | SHA-256 hashed keys for external auth |
| `field_mappings` | External field → ADRS category mapping |
| `auto_categorization_rules` | Object type → category assignment rules |
| `integration_logs` | All API calls in + out |
| `intake_queue` | Async buffer for inbound records |
| `disposal_dispatches` | Outbound deletion instructions |
| `consent_signals` | Inbound consent withdrawal events |

---

## SMTP Source of Truth — system_settings table
SMTP lives EXCLUSIVELY in `system_settings`. `config.py` has NO SMTP constants.
The mailer reads SMTP via `get_setting(db, 'smtp_host')` etc.
`helpers.py` includes `get_setting()` with in-request caching.

---

## API Authentication (Enterprise)
- External systems authenticate with `X-API-Key: adrs_XXXX` header
- Raw key shown ONCE at creation. SHA-256 hash stored in `api_keys.key_hash`.
- Key validation: `hashlib.sha256(raw_key.encode()).hexdigest()` == `api_keys.key_hash`
- Rate limit checked against `integration_logs` count in last 60 seconds
- All Enterprise API endpoints return JSON only — no HTML ever
- Tier gate runs FIRST, before any other logic

---

## Background Tasks (via APScheduler in FastAPI lifespan)

The following tasks run as background scheduled jobs:

```python
# Daily retention engine + housekeeping — 01:00 AM WAT
scheduler.add_job(run_retention_checks, CronTrigger(hour=1, minute=0))
scheduler.add_job(run_housekeeping, CronTrigger(hour=1, minute=30))

# Intake queue processor — every 5 minutes (Enterprise)
scheduler.add_job(process_intake_queue, IntervalTrigger(minutes=5))

# Disposal dispatch — every 10 minutes (Enterprise)
scheduler.add_job(run_disposal_dispatch, IntervalTrigger(minutes=10))

# Database backup — daily at 02:00 AM
scheduler.add_job(run_backup, CronTrigger(hour=2, minute=0))
```

---

## All 14 Core Decisions (Locked — unchanged from v4)
H5: Subdomain retention.3consult-ng.com | H4: SSL active
B1: consent_withdrawal in seed | B2: recalculations queue
B3: smart reassignment | B4: Data Owner creates with guardrails
B5: risk-tiered dual approval | B7: 14-day escalation
B8: two-pass bulk import | D4: fixed days
N1: DPO fallback if no owner | N2: in-app bell
S8: secure file attachments | C1: DSAR module v1

## Enterprise Decisions (New)
E1: API auth via X-API-Key + SHA-256 hash
E2: Async intake queue by default (sync available via system_settings flag)
E3: Outbound disposal via webhook POST to connected system's base_url/adrs/disposal
E4: Consent signals matched by external_ref; unmatched signals retried by scheduler
E5: Auto-categorisation: first matching rule by priority wins
E6: Integration logs purged after api_log_retention_days (default 90)
E7: Rate limiting via integration_logs count
E8: Tier upgrade via licence key; downgrade not supported (data integrity)

---

## Non-Negotiable Rules (All Versions)
1. `passlib.hash.bcrypt.hash(password)` always for password hashing
2. SQLAlchemy ORM queries — no raw string interpolation in SQL
3. CSRF on every browser form; API uses key auth (no CSRF)
4. Session validation + `require_login()` + role check — every protected route
5. SMTP reads from `system_settings` via `get_setting()`
6. Enterprise tier gate: check `org.tier` before every Enterprise feature
7. API keys: raw key shown once, SHA-256 hash stored — never log raw keys
8. Disposal dispatch: queue first, send async — never block UI for webhook calls
9. Audit log: APPEND-ONLY, REVOKE UPDATE/DELETE at DB level post-install
10. API v1 routes use API key auth (no session/CSRF)
11. All configuration via environment variables or `.env` file
