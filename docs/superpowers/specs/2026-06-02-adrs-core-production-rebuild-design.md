# ADRS Core — Production Rebuild Design

**Date:** 2026-06-02
**Author:** 3Consulting / Claude (brainstorming session)
**Status:** Approved for planning
**Phase:** 1 of 2 (Core now; Enterprise deferred to phase 2)

---

## 1. Purpose & Context

3Consulting is building the **Automated Data Retention System (ADRS)** — a GDPR/NDPR
compliance-first data lifecycle platform, sold in two tiers (Core, Enterprise).

An earlier AI-generated build exists in `retention/`. A review found it to be a
**competently-wired skeleton but not production-ready**: it maps the 20-table schema and
routes, with good security hygiene (CSRF, prepared statements, output escaping, soft
deletes), but it does **not** implement the compliance engine or business rules that are
the entire point of the product. Critically:

- The retention engine (`retention_cron.php`) **auto-disposes every record past its date**,
  ignoring `requires_dual_approval` — meaning it would silently delete children's/health/
  biometric data the spec says must never auto-dispose. This is a 🔴 critical safety bug.
- Disposal methods (`delete`/`anonymise`/`archive`) all behave identically (just set
  `status='disposed'`) — "anonymise" does not anonymise.
- Record creation captures only category + reference + date — **no lawful basis, no purpose,
  no owner assignment**, contradicting the product's core promise.
- Email is a 62-line PHPMailer **stub**; no templates are wired into any workflow.
- Legal hold, consent withdrawal lifecycle, NDPR export, DSAR workflow, bulk import, and
  role-aware dashboard are absent or stubbed.

Estimated completeness of the existing build: ~15–20% of production Core.

## 2. Goal

Deliver **ADRS Core, production-ready**: every Core feature in the blueprint implemented
correctly against the locked business rules, with automated tests on the
compliance-critical logic, deployable to cPanel shared hosting.

## 3. Locked Decisions (from this session)

| Decision | Choice |
|---|---|
| Deployment target | cPanel shared hosting — **PHP 8.2 + MySQL, no framework, no Composer** |
| Existing code | **Rebuild the application + engine layer**; keep the schema |
| Scope order | **ADRS Core first to production**, then Enterprise (phase 2) |
| Testing | **Lightweight CLI test harness** (no Composer), focused on compliance-critical logic |
| UI | **Bootstrap 5.3 themed in 3Consulting orange/teal** + logo |

## 4. Non-Goals (this phase)

- ADRS Enterprise: REST API (`src/api/v1/`), intake queue processing, outbound disposal
  dispatch, connected systems / API keys / field mappings / rules UI, consent signals,
  onboarding wizard. **The 8 Enterprise tables and tier-gating remain in the schema and
  code so Core never blocks Enterprise**, but no Enterprise behavior is built now.
- Any change to the database schema beyond additive fixes required by Core correctness.

## 5. Source of Truth

1. `ADRS_v2_MASTER_PACKAGE/01_BUILD_PACKAGE/.github/copilot-instructions.md` — master rules,
   the 14 locked Core decisions (B1–B8, D4, N1/N2, S8, C1), tech constraints, file structure.
2. `ADRS_v2_MASTER_PACKAGE/01_BUILD_PACKAGE/prompts/01–12` — Core module specs.
3. `ADRS_v2_MASTER_PACKAGE/01_BUILD_PACKAGE/docs/` — architecture, compliance library.
4. The product paper (deployment promises, lifecycle stages, benefits).

Where the existing `retention/` build deviates from these, **correct to the blueprint.**

## 6. Architecture

Unchanged from the blueprint (mandatory constraints):

- **Front controller:** `retention/index.php` routes to `src/pages/*`.
- **Layers:** `src/config/` (DB + app constants; no SMTP), `src/includes/`
  (db, auth, helpers, mailer, email_templates, layout), `src/engine/` (cron),
  `src/pages/` (UI), `sql/` (schema + seed).
- **DB access:** PDO prepared statements only; `SET time_zone='+01:00'` after every connect.
- **Config:** secrets in gitignored `src/config/config.local.php`; SMTP lives **only** in the
  `system_settings` table, read via `get_setting()` (in-request static cache).
- **Tier gating:** every Enterprise hook checks `get_setting($pdo,'adrs_tier')`; Core is the
  default. Built now as guards even though Enterprise features are deferred.

### Module boundaries (each independently understandable & testable)

- **helpers.php** — pure utilities: `get_setting()`, CSRF token/validate, `escape_html`,
  `redirect`, flash, date math, `log_audit()`, role checks. Pure functions are unit-tested.
- **auth.php** — session, `require_login()`, `require_role()`, bcrypt verify, reset tokens.
- **engine** — the retention state machine; the single most important unit; integration-tested
  against a disposable DB.
- **mailer + email_templates** — SMTP send + the 15 templates; templates are pure string
  builders (unit-testable); sending is integration-level.
- **pages** — thin controllers that validate input, call helpers/engine functions, render.

## 7. The Compliance Engine (heart of the system)

`src/engine/retention_cron.php` — CLI-only (reject web SAPI). Daily job = locked **9 steps**:

1. **Bootstrap**: read `review_alert_days`, `escalation_days`, `consent_disposal_days` from
   settings; structured logging to `LOG_PATH` (outside webroot).
2. **Flag date_based records** approaching `retention_end_date` (within review window):
   only `disposal_trigger='date_based'`, `status='active'`, not legal-held, not soft-deleted,
   category not soft-deleted → set `status='due_review'`, `review_flagged_at=NOW()`,
   `log_audit('record_flagged_review')`, queue review notification (batched by owner).
3. **Consent-based disposal (B1)**: `disposal_trigger='consent_withdrawal'` records whose
   `consent_withdrawn_at` is ≥ `consent_disposal_days` ago → `execute_disposal()`.
4. **Auto-dispose overdue date_based** (`status='due_review'`, past end date) **— SKIP any
   `requires_dual_approval=1`** (B5 safeguard; the critical fix). Dual-approval records remain
   `due_review` for manual two-person action in the UI.
5. **14-day escalation (B7)**: `due_review` records with `review_flagged_at` ≥ escalation_days
   ago and `escalation_sent_at IS NULL` → set `escalation_sent_at`, send **one** summary email
   to all Admins, `log_audit('escalation_sent')`.
6. **DSAR deadline alerts (C1)**: due-in-5-days and overdue DSARs → alert assignee + all DPOs.
7. **Send batched notifications**: one email per owner (N1: fall back to all DPOs if
   `owner_id IS NULL`); never one email per record.
8. **Retry failed notifications**: `status IN('failed','pending')`, `attempts<3`, last 48h.
9. **Completion log** + if any errors, summary error email to Admins.

**`execute_disposal(PDO, record)`** — transactional, idempotent:
- Re-verify legal hold (race guard) and not-already-disposed (idempotency, D1).
- Switch on `disposal_method`:
  - `delete` → `status='disposed'`, `disposed_at`, `deleted_at` (soft-delete; physical purge
    policy documented).
  - `anonymise` → NULL out PII columns (`record_reference`→tokenised, `data_subject_type`,
    `notes`), `status='disposed'`.
  - `archive` → `status='disposed'`, retain all data.
- `log_audit('record_disposed_<method>')`; queue `disposal_confirmation` notification to DPO.
- Enterprise hook: if `adrs_tier='enterprise'`, queue outbound dispatch — **stubbed/guarded
  now**, implemented in phase 2.

**Quarterly task** (`--task=quarterly_review`): summary of categories overdue for review,
disposals by method this quarter, records on hold, DSAR stats → email Admins + DPOs;
`log_audit`. Recorded in `schedule_reviews`.

## 8. Core Modules & Build Order

Mirrors blueprint Part A (steps 1–14). Each module is implemented **and tested** before the
next. Build order respects dependencies:

1. **Foundation** — `config/database.php` + `config.local.php`, `db.php`, `helpers.php`
   (incl. `get_setting()`, CSRF, `log_audit()`), `auth.php`, tier-aware `layout_header/footer`,
   error pages, `index.php` front controller.
2. **Auth & users** — login, logout, forgot/reset password (token via `password_resets`),
   forced first-login password change, user CRUD with the 3 roles (Admin / DPO / Data Owner).
3. **Categories** — CRUD with full fields: `legal_basis`, `disposal_trigger`,
   `requires_dual_approval`, `disposal_method`, `retention_period_days`/label, `owner_id`,
   `review_frequency`. B2: queue `pending_recalculations` when retention period changes.
4. **Records lifecycle** — create/edit/view/list capturing **purpose (notes), category
   (→lawful basis), owner, collection date**; auto-calc `retention_end_date` (consent
   categories start NULL until withdrawal); `src/api/get_category.php` (session-auth AJAX for
   category metadata). B4: Data Owner can create with guardrails.
5. **Engine** — section 7 above.
6. **Audit log viewer + NDPR export** — filterable append-only log; NDPR Annual Report export
   (CSV/printable) formatted for NITDA.
7. **Email** — real PHPMailer (3-file include), `email_templates.php` with the 15 templates,
   wired into engine + DSAR + auth + disposal flows; SMTP from `system_settings`; test-email tool.
8. **Dashboard** — role-aware compliance health: due-review counts, overdue/escalated, upcoming
   disposals, DSAR status, legal holds, recent audit activity.
9. **DSAR module (C1)** — create/track/view requests; auto reference + 30-day deadline;
   status workflow; identity verification step; deadline + overdue handled by engine step 6.
10. **File attachments (S8)** — secure upload (type/size validation), stored **outside webroot**,
    authenticated download; metadata in `attachments`.
11. **Bulk import (B8)** — two-pass CSV (validate-all then commit); results in `import_jobs`.
12. **Advanced** — settings (SMTP, app config, tier flag), `pending_recalculations` review
    queue (B2/D4 fixed-days recalculation), **legal hold** place/lift (B-rule, cascade hook for
    Enterprise stubbed), **consent withdrawal** UI (B1 manual logging → 30-day countdown),
    **category reassignment** (B3 smart reassignment preserving `original_category_id`),
    **in-app notification bell** (N2).

## 9. Testing Strategy

- **Harness:** `tests/run.php` — a minimal no-Composer runner with `assert_*` helpers,
  discovering `tests/**/*_test.php`. Exit non-zero on any failure. Runnable on shared hosting.
- **Test database:** a disposable DB configured via `config.local.php` (e.g. `*_test`);
  setup/teardown re-imports `schema.sql` + minimal fixtures.
- **Coverage priorities (compliance-critical first):**
  - Engine: dual-approval records are **never** auto-disposed (step 4); date_based flagging
    window; consent countdown (step 3); escalation timing (step 5); disposal idempotency &
    legal-hold race guard; each disposal method's effect on the row.
  - Helpers: retention-date math, `get_setting` caching, CSRF validate, role checks.
  - Auth: login success/failure, reset-token expiry, role gating.
  - Email templates: render with expected fields (pure string assertions).
  - DSAR: deadline calculation, overdue detection.
- **Approach:** TDD where practical (write the failing test for a rule, then implement),
  especially for the engine.

## 10. Production Hardening / Definition of Done

- Audit log append-only: `REVOKE UPDATE, DELETE` documented in deploy guide; engine/app never
  update/delete audit rows; verified by test that app code only INSERTs.
- bcrypt password hashing; session hardening (httponly, samesite, regenerate on login).
- CSRF on every browser form; AJAX uses session auth.
- Secrets only in gitignored `config.local.php`; `.htaccess` blocks `src/config/` and `sql/`.
- Attachments + logs outside `public_html`.
- Forced default-credential change on first login.
- `APP_ENV=production` disables verbose errors; errors logged outside webroot.
- Updated `docs/architecture.md` deploy checklist verified against the rebuilt app.
- `php tests/run.php` green.
- Manual smoke test of each module documented.

## 11. Risks & Mitigations

- **Scope size** → strict module-by-module build+test; Core only; Enterprise deferred.
- **No-Composer testing friction** → custom harness; keep pure functions pure for unit testing.
- **Shared-hosting cron reliability** → idempotent engine (safe to re-run); structured logs.
- **Regression of the safety bug** → explicit regression test that dual-approval records survive
  the engine.

## 12. Deliverable Layout (under `retention/`)

```
retention/
├── index.php, 404/500/maintenance.php, .htaccess(.local)
├── sql/            (kept: schema.sql, seed_gdpr_ndpr.sql; additive fixes only)
├── src/
│   ├── config/     (database.php, config.local.php[gitignored])
│   ├── includes/   (db, auth, helpers, mailer, email_templates, layout_*, phpmailer/)
│   ├── engine/     (retention_cron.php  [intake/dispatch deferred to phase 2])
│   └── pages/      (auth, users, categories, records, audit, dsar, attachments,
│                    import, recalculations, notifications, settings, dashboard, help)
├── storage/        (attachments, logs — outside webroot in production)
└── tests/          (run.php + *_test.php)
```

## 13. Phase 2 Preview (not now)

ADRS Enterprise: `src/api/v1/` REST layer (X-API-Key + SHA-256), intake queue processor,
outbound disposal dispatch cron, connected systems / API keys / field mappings /
auto-categorization rules / integration logs UI, consent signal matching, 5-step onboarding
wizard, tier upgrade, enterprise monitoring dashboard. Built on the working, tested Core.
