# ADRS — Production Build Design (Two-Tier + Advanced)

**Date:** 2026-06-02
**Author:** 3Consulting / Claude (brainstorming session)
**Status:** Approved for planning
**Scope:** Full production build — ADRS Core, ADRS Enterprise, and a curated advanced
feature set. Delivered in 3 sequenced phases.

---

## 1. Purpose & Context

3Consulting is building the **Automated Data Retention System (ADRS)** — a GDPR/NDPR
compliance-first data lifecycle platform, sold in two tiers (Core, Enterprise).

An earlier AI-generated build exists in `retention/`. Review found it to be a
**competently-wired skeleton but not production-ready** (~15–20% complete): it maps the
20-table schema and routes, with good security hygiene (CSRF, prepared statements, output
escaping, soft deletes), but it does **not** implement the compliance engine or business
rules. Critically:

- The retention engine (`retention_cron.php`) **auto-disposes every record past its date**,
  ignoring `requires_dual_approval` — it would silently delete children's/health/biometric
  data that must never auto-dispose. 🔴 Critical safety bug.
- Disposal methods (`delete`/`anonymise`/`archive`) all behave identically — "anonymise"
  does not anonymise.
- Record creation captures only category + reference + date — **no lawful basis, no purpose,
  no owner**, contradicting the product's core promise.
- Email is a 62-line PHPMailer **stub**; no templates wired into any workflow.
- Legal hold, consent lifecycle, NDPR export, DSAR workflow, bulk import, role-aware
  dashboard: absent or stubbed.

## 2. Goal

Deliver a **production-ready ADRS** covering both tiers and a curated advanced feature set,
implemented correctly against the blueprint's locked business rules, with automated tests on
compliance-critical logic, deployable to cPanel shared hosting.

## 3. Locked Decisions (this session)

| Decision | Choice |
|---|---|
| Deployment target | cPanel shared hosting — **PHP 8.2 + MySQL, no framework, no Composer** |
| Existing code | **Rebuild the application + engine layer**; keep the 20-table schema |
| Scope | **Core + Enterprise + advanced features**, all to production |
| Sequencing | **Phase 1 Core → Phase 2 Enterprise → Phase 3 Advanced** |
| Tenancy | **Single-tenant per deployment** (one install per client; white-label by theming) |
| Testing | **Lightweight CLI test harness** (no Composer), focused on compliance-critical logic |
| UI | **Bootstrap 5.3 themed in 3Consulting orange/teal** + logo |

## 4. Non-Goals (explicitly deferred, with rationale)

- **SSO / SAML** — IdP-specific, awkward on shared hosting; cleanly bolt-on-able later per
  enterprise customer with no rework. Not built speculatively.
- **Multi-tenant / multi-organisation** — would change every table and query; only needed for
  a SaaS-hosting model the user is not pursuing. Single-tenant chosen.
- **Premium *services*** (audits, workshops, advisory) from the product paper — these are
  consulting services, not software.

## 5. Source of Truth

1. `ADRS_v2_MASTER_PACKAGE/01_BUILD_PACKAGE/.github/copilot-instructions.md` — master rules,
   14 locked Core decisions (B1–B8, D4, N1/N2, S8, C1), 8 Enterprise decisions (E1–E8),
   tech constraints, file structure.
2. `.../prompts/01–17` — module specs (Core 01–12, Enterprise 13–17).
3. `.../docs/` — architecture, compliance library.
4. The product paper — deployment promises, lifecycle stages, benefits, white-label.

Where the existing `retention/` build deviates from these, **correct to the blueprint.**

## 6. Architecture (mandatory constraints, all phases)

- **Front controller:** `retention/index.php` routes to `src/pages/*`. Enterprise REST under
  `src/api/v1/` (own key-auth layer, reachable, not blocked by `.htaccess`).
- **Layers:** `src/config/` (DB + app constants; no SMTP), `src/includes/` (db, auth, helpers,
  mailer, email_templates, enterprise_dispatch, layout), `src/engine/` (crons), `src/pages/`
  (UI), `sql/` (schema + seed), `tests/`, `storage/` (attachments + logs, outside webroot).
- **DB access:** PDO prepared statements only; `SET time_zone='+01:00'` after every connect.
- **Config:** secrets in gitignored `src/config/config.local.php`; SMTP **only** in
  `system_settings`, via `get_setting()` (in-request static cache).
- **Tier gating:** every Enterprise page/endpoint/cron-step checks `get_setting('adrs_tier')`;
  Core is default. API tier gate runs **first**, before any other logic.
- **Module boundaries:** thin page controllers; pure utilities in `helpers.php`; the engine is
  the one stateful core unit. Pure functions are unit-tested; the engine is integration-tested.

### Schema policy
Keep the existing 20 tables. Additions are **additive only**: new columns
(e.g. audit hash-chain, user 2FA secret) and **new tables for advanced modules**
(DPIA, breach register, consent receipts, RoPA snapshots, webhook endpoints, backup log).
No destructive schema changes.

---

## 7. PHASE 1 — ADRS Core (production)

### 7.1 The compliance engine (`src/engine/retention_cron.php`)
CLI-only. Daily job = locked **9 steps**:

1. Bootstrap: read `review_alert_days`, `escalation_days`, `consent_disposal_days`; structured
   logging to `LOG_PATH` (outside webroot).
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

**`execute_disposal(PDO,$record)`** — transactional, idempotent: re-verify legal hold + not
already disposed; switch on method — `delete` (soft-delete + purge policy), `anonymise` (NULL
PII columns), `archive` (retain); `log_audit('record_disposed_<method>')`; queue
`disposal_confirmation` to DPO; Enterprise outbound dispatch hook (guarded; built in Phase 2).

**Quarterly task** (`--task=quarterly_review`): categories overdue for review, disposals by
method this quarter, holds, DSAR stats → email Admins + DPOs; log to `schedule_reviews`.

### 7.2 Core modules & build order (blueprint Part A, 01–12)
Each built **and tested** before the next:
1. **Foundation** — config, `db.php`, `helpers.php` (`get_setting`, CSRF, `log_audit`),
   `auth.php`, tier-aware layout, error pages, front controller.
2. **Auth & users** — login, logout, forgot/reset password, forced first-login password change,
   user CRUD with 3 roles (Admin / DPO / Data Owner).
3. **Categories** — full-field CRUD (`legal_basis`, `disposal_trigger`,
   `requires_dual_approval`, `disposal_method`, retention period/label, `owner_id`,
   `review_frequency`); B2 queue `pending_recalculations` on retention change.
4. **Records lifecycle** — create/edit/view/list capturing purpose, category (→lawful basis),
   owner, dates; auto-calc `retention_end_date` (consent → NULL until withdrawal);
   `src/api/get_category.php` (session-auth AJAX); B4 owner-create guardrails.
5. **Engine** — §7.1.
6. **Audit viewer + NDPR export** — filterable append-only log; NDPR Annual Report (NITDA).
7. **Email** — real PHPMailer (3-file include), 15 templates wired into engine/DSAR/auth/
   disposal; SMTP from `system_settings`; test-email tool.
8. **Dashboard** — role-aware compliance health (due/overdue/escalated, upcoming disposals,
   DSAR status, holds, recent audit).
9. **DSAR (C1)** — create/track/view; auto reference + 30-day deadline; status workflow; ID
   verification; engine-driven deadline alerts.
10. **Attachments (S8)** — secure upload (type/size), stored outside webroot, authed download.
11. **Bulk import (B8)** — two-pass CSV (validate-all then commit); `import_jobs`.
12. **Advanced Core** — settings (SMTP/app/tier), `pending_recalculations` queue (B2/D4),
    legal hold place/lift (cascade hook stubbed for Enterprise), consent withdrawal UI (B1),
    category reassignment (B3, preserve `original_category_id`), in-app notification bell (N2).

---

## 8. PHASE 2 — ADRS Enterprise (production)

Built on the working, tested Core. Enterprise decisions E1–E8 (blueprint prompts 13–17).

- **REST API** (`src/api/v1/`): `bootstrap.php`, `router.php`, endpoints `health`,
  `categories`, `ingest`, `ingest_batch` (≤500), `consent_withdraw`, `record_status`.
  Auth: `X-API-Key` + SHA-256 hash (E1, raw key shown once, never logged). Tier gate first.
  Rate limiting via `integration_logs` count in last 60s (E7). JSON only.
- **Inbound intake:** async `intake_queue` by default (E2; sync via setting);
  `intake_queue_processor.php` cron (every 5 min) → `process_intake_item()`: auto-categorise by
  first matching rule by priority (E5), calc retention, assign owner, create `data_record`,
  `log_audit`. Unmatched → flagged.
- **Outbound disposal dispatch (E3):** `disposal_dispatches` queue; `disposal_dispatch_cron.php`
  (every 10 min) → webhook `POST {base_url}/adrs/disposal` via cURL; retries + status; never
  blocks UI. Wired into `execute_disposal()` hook from Phase 1.
- **Consent signals (E4):** inbound API event → `consent_signals`; matched by `external_ref`;
  unmatched retried by engine step B.
- **Integration management UI** (Admin, Enterprise-gated): `connected_systems` CRUD; `api_keys`
  (create/revoke, raw shown once); `field_mappings`; `auto_categorization_rules` (priority
  ordered); `integration_logs` viewer; intake-queue viewer; monitoring page; `ping`.
- **Engine Enterprise steps A/B/C:** process intake fallback; retry unmatched consent signals;
  purge `integration_logs` older than `api_log_retention_days` (E6, default 90).
- **Onboarding wizard** (5 steps) + **tier upgrade** page (E8 licence key; downgrade
  unsupported for data integrity) + Enterprise dashboard additions.

---

## 9. PHASE 3 — Advanced Features

Curated "best-recommendable" set (user delegated selection). Each is a self-contained module
with additive schema, built on the stable two-tier base. Each tested.

1. **Analytics & management reporting** — compliance-health dashboards (charts/trends via a
   lightweight JS chart lib, no build tools), disposal & DSAR analytics, exportable
   management/board reports (PDF/print + CSV) beyond the NDPR export.
2. **Two-factor auth (2FA)** — TOTP in pure PHP (no external service); per-user secret +
   recovery codes; enforced-by-role option; columns added to `users`.
3. **Tamper-evident audit log** — hash-chaining: each `audit_log` row stores
   `prev_hash` + `row_hash` (SHA-256 over canonical row + prev_hash); a verifier page/CLI proves
   the chain is unbroken. Complements the existing append-only REVOKE policy.
4. **RoPA / Article 30 register** — auto-generated Record of Processing Activities from category
   + processing metadata; exportable; new `ropa_entries` (or category-derived snapshot table).
5. **DPIA workflow** — structured Data Protection Impact Assessment module (questionnaire, risk
   scoring, mitigation, sign-off); `dpia_assessments` table.
6. **Data-breach incident register** — log incidents; Art. 33/34 **72-hour notification**
   countdown + status; affected-records linkage; `breach_incidents` table.
7. **Consent receipts** — issue/store consent receipts tied to consent lifecycle;
   `consent_receipts` table.
8. **Automated DB backups** — cron `mysqldump` to `storage/backups` (outside webroot), rotation,
   `backup_log` table; restore guidance in deploy docs.
9. **Outbound webhooks / ops alerts** — configurable endpoints (Slack/Teams/generic) for key
   events (escalations, breaches, failures) via cURL; reuses the dispatch pattern;
   `webhook_endpoints` table.
10. **White-label theming** — logo, colours, product name, footer via `system_settings`; applied
    across layout + emails. Fulfils the product paper's Enterprise white-label promise.

---

## 10. Testing Strategy (all phases)

- **Harness:** `tests/run.php` — minimal no-Composer runner with `assert_*` helpers, discovers
  `tests/**/*_test.php`, exits non-zero on failure; runnable on shared hosting.
- **Test database:** disposable `*_test` DB via `config.local.php`; setup re-imports
  `schema.sql` + fixtures.
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
- bcrypt; session hardening (httponly, samesite, regenerate on login); optional 2FA.
- CSRF on every browser form; API uses key auth; never log raw API keys.
- Secrets only in gitignored `config.local.php`; `.htaccess` blocks `src/config/` + `sql/`.
- Attachments, logs, backups outside `public_html`.
- Forced default-credential change on first login.
- `APP_ENV=production` hides verbose errors; errors logged outside webroot.
- `docs/architecture.md` deploy checklist updated + verified (incl. all 4 cron jobs for
  Enterprise, backup cron for Phase 3).
- `php tests/run.php` green; per-module manual smoke test documented.

## 12. Risks & Mitigations

- **Large scope** → strict phase/module sequencing; ship working Core before Enterprise before
  advanced; each module built+tested in isolation.
- **No-Composer testing** → custom harness; keep pure functions pure.
- **Shared-hosting cron reliability** → idempotent engine (safe to re-run); structured logs.
- **Safety-bug regression** → explicit test that dual-approval records survive the engine.
- **Schema sprawl from advanced modules** → additive-only, one focused table per module.

## 13. Deliverable Layout (under `retention/`)

```
retention/
├── index.php, 404/500/maintenance.php, .htaccess(.local)
├── sql/        (schema.sql [+ additive migrations], seed_gdpr_ndpr.sql)
├── src/
│   ├── api/    (get_category.php; v1/ REST — Phase 2)
│   ├── config/ (database.php, config.local.php[gitignored])
│   ├── includes/ (db, auth, helpers, mailer, email_templates, enterprise_dispatch,
│   │             twofactor, audit_chain, layout_*, phpmailer/)
│   ├── engine/ (retention_cron.php; intake_queue_processor.php, disposal_dispatch_cron.php,
│   │            backup_cron.php — Phases 2/3)
│   └── pages/  (auth, users, categories, records, audit, dsar, attachments, import,
│               recalculations, notifications, settings, dashboard, reports, ropa, dpia,
│               breaches, integrations[Phase 2], help)
├── storage/    (attachments, logs, backups — outside webroot in production)
└── tests/      (run.php + *_test.php)
```

## 14. Implementation Plans

This design is too large for a single implementation plan. Each phase gets its **own**
implementation plan (spec → plan → build → test → review), produced when the prior phase is
complete and verified:

- **Plan 1:** Phase 1 — ADRS Core (created next).
- **Plan 2:** Phase 2 — ADRS Enterprise.
- **Plan 3:** Phase 3 — Advanced features.
