# GitHub Copilot Instructions — 3Consulting ADRS v5
# TWO-TIER PRODUCT: CORE + ENTERPRISE
# ================================================================

## Product Identity
Product:    Automated Data Retention System (ADRS)
Company:    3Consulting Limited (Lagos, Nigeria & Oakham, UK)
Version:    2.0 — Two-Tier Edition
Website:    https://www.3consult-ng.com
Compliance: GDPR (EU/UK) + Nigeria NDPR 2019 + Global equivalents

---

## The Two Tiers — Understand This First

### ADRS Core (Entry Level)
- Standalone compliance portal — no external system connections
- Manual data intake: compliance team registers records via the UI
- Automated enforcement AFTER intake: daily cron flags, reviews, disposes
- Deployment: 4–6 weeks, no IT integration required
- Target: any organisation with zero current governance
- `adrs_tier = 'core'` in system_settings

### ADRS Enterprise (Integration Tier)
- Everything in Core PLUS an API integration layer
- Automatic data capture: external systems push records via REST API
- Real-time governance: retention clock starts the moment data is created anywhere
- Outbound disposal: ADRS instructs connected systems to delete/anonymise
- Consent signal capture: external systems send withdrawal events to ADRS
- Deployment: 10–14 weeks, requires API integration work
- Target: fintechs, banks, high-volume data processors
- `adrs_tier = 'enterprise'` in system_settings

### Feature Gating
Every Enterprise-only page, API endpoint, and cron job MUST check:
```php
if (get_setting($pdo, 'adrs_tier') !== 'enterprise') {
    // Return 403 for API endpoints
    // Redirect to dashboard with flash for UI pages
    // Skip silently for cron steps
}
```
Never hard-code tier assumptions. Always read from system_settings.

---

## Tech Stack — ABSOLUTE CONSTRAINTS
- **Language:** Pure PHP 8.2 — NO framework, NO Composer, NO namespaces
- **Database:** MySQL 8.0 via PDO prepared statements ONLY
- **Frontend:** Bootstrap 5.3 + Bootstrap Icons + Vanilla JS ES6+
- **Email:** PHPMailer 3-file manual include
- **Local dev:** Laragon (Windows) + Mailpit
- **Production:** InMotion Shared Hosting — retention.3consult-ng.com
- **Cron:** cPanel (production) / Windows Task Scheduler (local)
- **HTTP Client:** PHP cURL (for outbound disposal dispatch — built into PHP)
- **No Docker. No npm. No build tools. No Composer.**

---

## Complete File Structure (Core + Enterprise)

```
/retention/
├── .htaccess                         ← production (RewriteBase /)
├── .htaccess.local                   ← gitignored (RewriteBase /data-retention/)
├── index.php                         ← front controller
├── 404.php / 500.php / maintenance.php
├── src/
│   ├── api/
│   │   ├── get_category.php          ← Core AJAX (authenticated, no API key)
│   │   └── v1/                       ← ENTERPRISE API (API key auth)
│   │       ├── bootstrap.php
│   │       ├── router.php
│   │       └── endpoints/
│   │           ├── ingest.php
│   │           ├── ingest_batch.php
│   │           ├── consent_withdraw.php
│   │           ├── categories.php
│   │           ├── record_status.php
│   │           └── health.php
│   ├── config/
│   │   ├── database.php              ← DB + app constants (NO SMTP)
│   │   └── config.local.php          ← gitignored local override
│   ├── includes/
│   │   ├── db.php                    ← PDO + SET time_zone = +01:00
│   │   ├── auth.php                  ← login, logout, reset token
│   │   ├── helpers.php               ← get_setting() + all utilities
│   │   ├── mailer.php                ← reads SMTP from system_settings
│   │   ├── email_templates.php       ← 15+ email templates
│   │   ├── enterprise_dispatch.php   ← ENTERPRISE outbound dispatch helper
│   │   ├── layout_header.php         ← sidebar (tier-aware nav)
│   │   └── layout_footer.php         ← APP_URL + csrfToken JS globals
│   ├── engine/
│   │   ├── retention_cron.php        ← daily + quarterly (Core + Enterprise steps)
│   │   ├── intake_queue_processor.php ← ENTERPRISE: processes intake_queue
│   │   └── disposal_dispatch_cron.php ← ENTERPRISE: sends outbound webhooks
│   └── pages/
│       ├── login.php / logout.php / forgot_password.php / reset_password.php
│       ├── profile.php / dashboard.php
│       ├── categories/
│       ├── schedule/
│       │   ├── index.php / create.php / view.php
│       │   ├── dispose.php           ← triggers dispatch if Enterprise
│       │   ├── legal_hold.php / reassign.php
│       │   ├── consent_withdraw.php / export.php
│       ├── audit/
│       ├── notifications/
│       ├── dsar/
│       ├── attachments/
│       ├── import/
│       ├── recalculations/
│       ├── users/
│       ├── settings/
│       │   ├── index.php / test_email.php
│       │   └── tier.php              ← tier management + upgrade
│       ├── integrations/             ← ENTERPRISE ONLY
│       │   ├── index.php             ← integration dashboard
│       │   ├── create.php            ← register connected system
│       │   ├── onboarding/           ← 5-step wizard
│       │   │   ├── index.php / step2.php / step3.php
│       │   │   └── step4.php / step5.php
│       │   ├── api_keys/
│       │   │   ├── index.php / create.php / revoke.php
│       │   ├── field_mappings/
│       │   │   ├── index.php / create.php / delete.php
│       │   ├── rules/
│       │   │   ├── index.php / create.php / edit.php / delete.php
│       │   ├── logs/
│       │   │   └── index.php
│       │   ├── queue/
│       │   │   └── index.php
│       │   ├── monitoring.php
│       │   └── ping.php
│       └── help.php
```

---

## Database Tables (20 Total — Core 12 + Enterprise 8)

### Core Tables (all tiers)
| Table | Purpose |
|-------|---------|
| `users` | Auth + roles |
| `password_resets` | Token-based reset |
| `data_categories` | Retention register |
| `data_records` | Data assets lifecycle |
| `audit_log` | Append-only evidence (31+ actions) |
| `notifications` | Email + in-app alerts |
| `dsar_requests` | DSAR lifecycle |
| `schedule_reviews` | Quarterly review log |
| `pending_recalculations` | B2 DPO queue |
| `attachments` | File metadata |
| `import_jobs` | Bulk import history |
| `system_settings` | Config + SMTP + tier flag |

### Enterprise Tables (adrs_tier = 'enterprise' only)
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
SMTP lives EXCLUSIVELY in `system_settings`. `database.php` has NO SMTP constants.
`mailer.php` reads SMTP via `get_setting($pdo, 'smtp_host')` etc.
`helpers.php` must include `get_setting()` with in-request static cache.

---

## API Authentication (Enterprise)
- External systems authenticate with `X-API-Key: adrs_XXXX` header
- Raw key shown ONCE at creation. SHA-256 hash stored in `api_keys.key_hash`.
- Key validation: `hash('sha256', $raw_key)` === `api_keys.key_hash`
- Rate limit checked against `integration_logs` count in last 60 seconds
- All Enterprise API endpoints return JSON only — no HTML ever
- Tier gate runs FIRST, before any other logic

---

## Enterprise Cron Jobs (additional to Core crons)

```
# Intake queue processor — every 5 minutes
*/5 * * * * /usr/local/bin/php /path/to/intake_queue_processor.php >> /logs/intake_queue.log 2>&1

# Disposal dispatch — every 10 minutes
*/10 * * * * /usr/local/bin/php /path/to/disposal_dispatch_cron.php >> /logs/dispatch.log 2>&1
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
E1: API auth via X-API-Key + SHA-256 hash (not OAuth for shared hosting simplicity)
E2: Async intake queue by default (sync available via system_settings flag)
E3: Outbound disposal via webhook POST to connected system's base_url/adrs/disposal
E4: Consent signals matched by external_ref; unmatched signals retried by cron
E5: Auto-categorisation: first matching rule by priority wins
E6: Integration logs purged after api_log_retention_days (default 90)
E7: Rate limiting via integration_logs count (no Redis — shared hosting)
E8: Tier upgrade via licence key; downgrade not supported (data integrity)

---

## Non-Negotiable Rules (All Versions)
1. `password_hash($pass, PASSWORD_BCRYPT)` always
2. PDO prepared statements — zero string interpolation in SQL
3. CSRF on every browser form; API uses key auth (no CSRF)
4. `session_start()` + `require_login()` + role check — every protected page
5. `SET time_zone = '+01:00'` after every PDO connection
6. SMTP reads from `system_settings` via `get_setting()`
7. Enterprise tier gate: check `adrs_tier` before every Enterprise feature
8. API keys: raw key shown once, SHA-256 hash stored — never log raw keys
9. Disposal dispatch: queue first, send async — never block UI for webhook calls
10. Audit log: APPEND-ONLY, REVOKE UPDATE/DELETE at DB level post-install
11. `src/api/v1/` is publicly reachable (API) — own auth layer, no .htaccess block
12. `src/api/get_category.php` is session-auth (Core AJAX) — separate from v1 API
