# SafeData — Production Build Design (Two-Tier + Advanced)

**Date:** 2026-06-02
**Author:** 3Consulting / Claude (brainstorming session)
**Status:** Implemented (Python build)
**Scope:** Full production build — SafeData Core, SafeData Enterprise, and a curated advanced
feature set. Delivered in 3 sequenced phases.

---

## 1. Purpose & Context

3Consulting is building the **SafeData — Data Retention & Governance Platform** — a GDPR/NDPR
compliance-first data lifecycle platform, sold in two tiers (Core, Enterprise).

An earlier design specified a build in `retention/`. That build has been superseded by
the Python implementation in `retention_py/`, which delivers the same business logic
with a modern stack: **FastAPI + SQLAlchemy + Jinja2 + Pytest**.

## 2. Goal

Deliver a **production-ready SafeData** covering both tiers and a curated advanced feature set,
implemented correctly against the blueprint's locked business rules, with automated tests on
compliance-critical logic.

## 3. Locked Decisions (this session)

| Decision | Choice |
|---|---|
| Tech stack | **Python 3.10+ (FastAPI + SQLAlchemy + Jinja2)** |
| Database | **SQLite (dev) / MySQL (production)** via SQLAlchemy ORM |
| Existing code | **Rebuild the application + engine layer** in Python |
| Scope | **Core + Enterprise + advanced features**, all to production |
| Sequencing | **Phase 1 Core → Phase 2 Enterprise → Phase 3 Advanced** |
| Tenancy | **Multi-tenant SaaS** (organizations register, pick Core or Enterprise) |
| Testing | **Pytest + httpx** test suite |
| UI | **Bootstrap 5.3 themed in 3Consulting orange/teal** + Jinja2 templates |
| Migrations | **Alembic** for schema evolution |
| Background tasks | **APScheduler** in FastAPI lifespan (no external cron needed) |

## 4. Non-Goals (explicitly deferred, with rationale)

- **SSO / SAML** — IdP-specific; cleanly bolt-on-able later per enterprise customer
  with no rework. Not built speculatively.
- **Premium *services*** (audits, workshops, advisory) from the product paper — these are
  consulting services, not software.

## 5. Source of Truth

1. `SafeData_v2_MASTER_PACKAGE/01_BUILD_PACKAGE/.github/copilot-instructions.md` — master rules,
   14 locked Core decisions (B1–B8, D4, N1/N2, S8, C1), 8 Enterprise decisions (E1–E8),
   tech constraints, file structure.
2. `.../prompts/01–17` — module specs (Core 01–12, Enterprise 13–17).
3. `.../docs/` — architecture, compliance library.
4. The product paper — deployment promises, lifecycle stages, benefits, white-label.

## 6. Architecture (mandatory constraints, all phases)

- **Entry point:** `retention_py/main.py` — FastAPI app with Uvicorn, registers all route
  blueprints and background scheduled tasks.
- **Layers:** `app/config.py` (env-var config), `app/database.py` (SQLAlchemy engine/session),
  `app/models.py` (ORM models), `app/auth.py` (sessions/roles), `app/helpers.py` (utilities),
  `app/engine.py` (retention engine + reports), `app/enterprise.py` (Enterprise features),
  `app/middleware.py` (security headers, CSRF, session enforcement), `app/routes/` (blueprints),
  `app/templates/` (Jinja2), `app/static/` (CSS/JS/images).
- **DB access:** SQLAlchemy ORM only; no raw string interpolation in queries.
- **Config:** secrets via environment variables or `.env` file; SMTP in `system_settings`,
  via `get_setting()`.
- **Tier gating:** every Enterprise route/endpoint/task checks `org.tier`;
  Core is default. API tier gate runs **first**, before any other logic.
- **Module boundaries:** thin route handlers; pure utilities in `helpers.py`; the engine is
  the one stateful core unit. Pure functions are unit-tested; the engine is integration-tested.

### Schema policy
Additive-only schema changes via Alembic migrations. New columns and new tables for
advanced modules. No destructive schema changes.

---

## 7. PHASE 1 — SafeData Core (production)

### 7.1 The compliance engine (`app/engine.py`)
Background scheduled task. Daily job = locked **9 steps**:

1. Bootstrap: read `review_alert_days`, `escalation_days`, `consent_disposal_days`; structured
   logging to `LOG_PATH`.
2. Flag **date_based** records approaching `retention_end_date` (active, not legal-held, not
   soft-deleted, category not soft-deleted) → `due_review`, `review_flagged_at`,
   `log_audit('record_flagged_review')`, queue review notification (batched by owner).
3. **Consent-based disposal (B1):** `consent_withdrawal` records withdrawn ≥
   `consent_disposal_days` ago → `execute_disposal()`.
4. **Auto-dispose overdue date_based** — **SKIP any `requires_dual_approval=1`** (B5 safeguard,
   the critical fix). Dual-approval records stay `due_review` for manual two-person action.
5. **14-day escalation (B7):** `due_review` ≥ escalation_days old, `escalation_sent_at IS NULL`
   → set `escalation_sent_at`, one summary email to all Admins, `log_audit('escalation_sent')`.
6. **DSAR deadline alerts (C1):** due-in-5-days + overdue → assignee + all DPOs.
7. **Batched notifications:** one email per owner; N1 fallback to all DPOs if `owner_id` NULL.
8. **Retry failed notifications:** `status IN('failed','pending')`, `attempts<3`, last 48h.
9. **Completion log** + error-summary email to Admins on failure.

**`execute_disposal(db, record)`** — transactional, idempotent: re-verify legal hold + not
already disposed; switch on method — `delete` (soft-delete + purge policy), `anonymise` (NULL
PII columns), `archive` (retain); `log_audit('record_disposed_<method>')`.

**Quarterly task:** categories overdue for review, disposals by method this quarter, holds,
DSAR stats → email Admins + DPOs; log to `schedule_reviews`.

### 7.2 Core modules & build order (blueprint Part A, 01–12)
Each built **and tested** before the next:
1. **Foundation** — config, database, models, helpers (`get_setting`, CSRF, `log_audit`),
   auth, Jinja2 layout, error handlers, main entry point.
2. **Auth & users** — login, logout, forgot/reset password, forced first-login password change,
   user CRUD with 3 roles (Admin / DPO / Data Owner).
3. **Categories** — full-field CRUD (`legal_basis`, `disposal_trigger`,
   `requires_dual_approval`, `disposal_method`, retention period/label, `owner_id`,
   `review_frequency`); B2 queue `pending_recalculations` on retention change.
4. **Records lifecycle** — create/edit/view/list capturing purpose, category (→lawful basis),
   owner, dates; auto-calc `retention_end_date` (consent → NULL until withdrawal);
   category AJAX endpoint; B4 owner-create guardrails.
5. **Engine** — §7.1.
6. **Audit viewer + NDPR export** — filterable append-only log; NDPR Annual Report (NITDA).
7. **Email** — SMTP mailer via `smtplib`, 15 templates wired into engine/DSAR/auth/
   disposal; SMTP from `system_settings`; test-email tool.
8. **Dashboard** — role-aware compliance health (due/overdue/escalated, upcoming disposals,
   DSAR status, holds, recent audit).
9. **DSAR (C1)** — create/track/view; auto reference + 30-day deadline; status workflow; ID
   verification; engine-driven deadline alerts.
10. **Attachments (S8)** — secure upload (type/size), stored in `storage/attachments/`, authed download.
11. **Bulk import (B8)** — two-pass CSV (validate-all then commit); `import_jobs`.
12. **Advanced Core** — settings (SMTP/app/tier), `pending_recalculations` queue (B2/D4),
    legal hold place/lift, consent withdrawal UI (B1),
    category reassignment (B3, preserve `original_category_id`), in-app notification bell (N2).

---

## 8. PHASE 2 — SafeData Enterprise (production)

Built on the working, tested Core. Enterprise decisions E1–E8 (prompts 13–17).

- **REST API** (`app/routes/api_v1.py`): endpoints `health`, `categories`, `ingest`,
  `ingest_batch` (≤500), `consent_withdraw`, `record_status`.
  Auth: `X-API-Key` + SHA-256 hash (E1, raw key shown once, never logged). Tier gate first.
  Rate limiting via `integration_logs` count in last 60s (E7). JSON only.
- **Inbound intake:** async `intake_queue` by default (E2; sync via setting);
  intake queue processor (background task, every 5 min) → `process_intake_item()`: auto-categorise
  by first matching rule by priority (E5), calc retention, assign owner, create `DataRecord`,
  `log_audit`. Unmatched → flagged.
- **Outbound disposal dispatch (E3):** `disposal_dispatches` queue; dispatch cron
  (every 10 min) → webhook `POST {base_url}/SafeData/disposal` via `httpx`; retries + status;
  never blocks UI.
- **Consent signals (E4):** inbound API event → `consent_signals`; matched by `external_ref`;
  unmatched retried by engine.
- **Integration management UI** (Admin, Enterprise-gated): `connected_systems` CRUD; `api_keys`
  (create/revoke, raw shown once); `field_mappings`; `auto_categorization_rules` (priority
  ordered); `integration_logs` viewer; intake-queue viewer; monitoring page.
- **Engine Enterprise tasks A/B/C:** process intake fallback; retry unmatched consent signals;
  purge `integration_logs` older than `api_log_retention_days` (E6, default 90).
- **Onboarding wizard** (5 steps) + **tier upgrade** page (E8 licence key; downgrade
  unsupported for data integrity) + Enterprise dashboard additions.

---

## 9. PHASE 3 — Advanced Features

Curated "best-recommendable" set. Each is a self-contained module
with additive schema, built on the stable two-tier base. Each tested.

1. **Analytics & management reporting** — compliance-health dashboards (charts/trends via a
   lightweight JS chart lib, no build tools), disposal & DSAR analytics, exportable
   management/board reports (PDF/print + CSV) beyond the NDPR export.
2. **Two-factor auth (2FA)** — TOTP in pure Python (`pyotp`); per-user secret +
   recovery codes; enforced-by-role option; columns added to `users`.
3. **Tamper-evident audit log** — hash-chaining: each `audit_log` row stores
   `prev_hash` + `row_hash` (SHA-256 over canonical row + prev_hash); a verifier page proves
   the chain is unbroken. Complements the existing append-only REVOKE policy.
4. **RoPA / Article 30 register** — auto-generated Record of Processing Activities from category
   + processing metadata; exportable; `ropa_entries` table.
5. **DPIA workflow** — structured Data Protection Impact Assessment module (questionnaire, risk
   scoring, mitigation, sign-off); `dpia_assessments` table.
6. **Data-breach incident register** — log incidents; Art. 33/34 **72-hour notification**
   countdown + status; affected-records linkage; `breach_incidents` table.
7. **Consent receipts** — issue/store consent receipts tied to consent lifecycle;
   `consent_receipts` table.
8. **Automated DB backups** — scheduled backup to `storage/backups/`, rotation,
   `backup_log` table; restore guidance in deploy docs.
9. **Outbound webhooks / ops alerts** — configurable endpoints (Slack/Teams/generic) for key
   events (escalations, breaches, failures) via `httpx`; reuses the dispatch pattern;
   `webhook_endpoints` table.
10. **White-label theming** — logo, colours, product name, footer via `system_settings`; applied
    across layout + emails. Fulfils the product paper's Enterprise white-label promise.

---

## 10. Testing Strategy (all phases)

- **Framework:** Pytest + httpx `TestClient` for FastAPI integration tests.
- **Test database:** disposable SQLite in-memory or `test.db`; setup re-creates all tables
  via `Base.metadata.create_all()` + fixtures.
- **Priorities (compliance-critical first):**
  - Engine: **dual-approval records never auto-disposed** (regression test for the 🔴 bug);
    date_based flagging window; consent countdown; escalation timing; disposal idempotency +
    legal-hold race guard; per-method disposal effects.
  - Helpers: retention-date math, `get_setting` caching, CSRF, role checks.
  - Auth: login, reset-token expiry, role gating, 2FA verify.
  - Enterprise: API key auth + tier gate (403s), rate limit, intake categorisation by priority,
    consent matching by `external_ref`, dispatch queue/retry.
  - Advanced: audit hash-chain verify (tamper detection), breach 72h countdown, DPIA scoring,
    backup creation.
- TDD where practical (failing test for a rule, then implement), especially the engine.

## 11. Production Hardening / Definition of Done (per phase)

- Audit log append-only: `REVOKE UPDATE, DELETE` in deploy guide; app only INSERTs (test-proven);
  hash-chain verifier green (Phase 3).
- bcrypt via passlib; session hardening (httponly, samesite, regenerate on login); optional 2FA.
- CSRF on every browser form; API uses key auth; never log raw API keys.
- Secrets via environment variables; never committed to git.
- Attachments, logs, backups in `storage/` (outside public web root in production).
- Forced default-credential change on first login.
- `APP_ENV=production` hides verbose errors; errors logged to file.
- Architecture deployment checklist updated & verified.
- `pytest tests/` green; per-module manual smoke test documented.

## 12. Risks & Mitigations

- **Large scope** → strict phase/module sequencing; ship working Core before Enterprise before
  advanced; each module built+tested in isolation.
- **Safety-bug regression** → explicit test that dual-approval records survive the engine.
- **Schema sprawl from advanced modules** → additive-only, one focused table per module.

## 13. Deliverable Layout (under `retention_py/`)

```
retention_py/
├── main.py                FastAPI entry point + APScheduler tasks
├── requirements.txt       Python dependencies
├── alembic.ini            Alembic migration config
├── dev-start.ps1          Local dev startup (Windows)
├── alembic/               Database migrations
├── app/
│   ├── config.py          Environment config (env vars)
│   ├── database.py        SQLAlchemy engine + session
│   ├── models.py          All ORM models
│   ├── auth.py            Sessions, login/logout, role gates
│   ├── helpers.py         Utilities (audit, categories, email, CSRF)
│   ├── engine.py          Retention engine, housekeeping, reports, analytics
│   ├── enterprise.py      Enterprise features (API keys, intake, dispatch)
│   ├── middleware.py       Security headers, CSRF, session enforcement
│   ├── backups.py         Automated backup utilities
│   ├── routes/            Route blueprints (public, dashboard, categories,
│   │                      records, api_v1, app_pages, integrations, etc.)
│   ├── static/            CSS, JS, images
│   └── templates/         Jinja2 templates
├── tests/                 Pytest test suite
└── storage/               Attachments, logs, backups (gitignored)
```

## 14. Implementation Plans

This design is too large for a single implementation plan. Each phase gets its **own**
implementation plan (spec → plan → build → test → review), produced when the prior phase is
complete and verified:

- **Plan 1:** Phase 1 — SafeData Core (completed).
- **Plan 2:** Phase 2 — SafeData Enterprise (completed).
- **Plan 3:** Phase 3 — Advanced features (completed).
