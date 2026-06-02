# 3Consulting — ADRS v2 (Two-Tier Edition)
## CORE + ENTERPRISE | GDPR + NDPR + Global | PHP 8.2 + MySQL
### All decisions locked · All audit fixes applied · Complete two-tier build

---

## What Changed in v2

v2 introduces the **Enterprise tier** on top of the existing Core foundation.

| | ADRS Core | ADRS Enterprise |
|---|---|---|
| Data intake | Manual via UI | Automatic via REST API |
| Connected systems | None | Unlimited via API keys |
| Consent withdrawal | Logged manually by DPO | Received automatically via API |
| Disposal | Internal (ADRS only) | Outbound to connected systems |
| Deployment | 4–6 weeks | 10–14 weeks |
| IT involvement | None | Required (API integration) |
| Target client | Any organisation | Fintechs, banks, high-volume |

---

## 🚀 Copilot Chat Feed Order

### Part A — ADRS Core (build first, works standalone)

| Step | File | What it builds |
|------|------|----------------|
| 0 | `.github/copilot-instructions.md` | **Master context — open first, keep open ALWAYS** |
| — | `prompts/00-local-dev-setup.md` | **Do manually** — Laragon + Mailpit + htaccess |
| 1 | `sql/schema.sql` | 20-table DB (Core 12 + Enterprise 8) |
| 2 | `sql/seed_gdpr_ndpr.sql` | 30 categories with correct disposal_trigger |
| 3 | `prompts/01-project-setup.md` | Config, DB, helpers, auth, layout |
| 4 | `prompts/02-auth-system.md` | Login, forgot/reset password, user management |
| 5 | `prompts/03-data-category-register.md` | Category CRUD, B1/B2/B5 |
| 6 | `prompts/04-retention-schedule-manager.md` | api/get_category.php + records lifecycle |
| 7 | `prompts/05-automated-engine-cron.md` | 9-step cron + Enterprise steps A/B/C |
| 8 | `prompts/06-audit-log-viewer.md` | Audit trail + NDPR export |
| 9 | `prompts/07-email-notifications.md` | PHPMailer + 15 templates |
| 10 | `prompts/08-dashboard.md` | Role-aware dashboard |
| 11 | `prompts/09-dsar-module.md` | DSAR tracking |
| 12 | `prompts/10-file-attachments.md` | Secure file attachments |
| 13 | `prompts/11-bulk-import.md` | Two-pass CSV import |
| 14 | `prompts/12-advanced-features.md` | Settings, recalculations, consent UI, bell |

**→ Test Core fully before proceeding to Enterprise.**

### Part B — ADRS Enterprise (build on top of working Core)

| Step | File | What it builds |
|------|------|----------------|
| 15 | `prompts/13-enterprise-api-layer.md` | REST API, router, 6 endpoints, intake queue processor |
| 16 | `prompts/14-integration-management.md` | Connected systems, API keys, field mapping, rules UI |
| 17 | `prompts/15-outbound-disposal-dispatch.md` | Disposal dispatch cron + webhook sending |
| 18 | `prompts/16-enterprise-monitoring.md` | Enterprise dashboard additions + monitoring page |
| 19 | `prompts/17-enterprise-onboarding-wizard.md` | 5-step wizard + tier upgrade page |

---

## 🐛 All Bugs Fixed (from v4 audit)

| Bug | Fix |
|-----|-----|
| `password_resets` table missing | Added to schema as table 2 |
| `disposal_trigger` defaulting wrong | Set explicitly in every seed INSERT |
| `forgot_password.php` missing | Fully built in Prompt 02 |
| `api/get_category.php` undefined | Defined first in Prompt 04 |
| `notifications.related_dsar_id` no FK | FK constraint added |
| `.htaccess` RewriteBase conflict | Two-file strategy (.htaccess.local gitignored) |
| SMTP source-of-truth conflict | SMTP in `system_settings` DB only |
| Enterprise API route not in .htaccess | Added to both .htaccess files |

---

## 🗄️ Database Tables (20 Total)

### Core (12)
`users` · `password_resets` · `data_categories` · `data_records` · `audit_log`
`notifications` · `dsar_requests` · `schedule_reviews` · `pending_recalculations`
`attachments` · `import_jobs` · `system_settings`

### Enterprise (8)
`connected_systems` · `api_keys` · `field_mappings` · `auto_categorization_rules`
`integration_logs` · `intake_queue` · `disposal_dispatches` · `consent_signals`

---

## ⚙️ Cron Jobs

### Core (2 jobs)
```
# Daily retention engine — 01:00 AM WAT
0 1 * * * php retention_cron.php >> logs/retention_cron.log 2>&1

# Quarterly review email — 1st Jan/Apr/Jul/Oct 08:00 AM
0 8 1 1,4,7,10 * php retention_cron.php --task=quarterly_review >> logs/quarterly_review.log 2>&1
```

### Enterprise (2 additional jobs)
```
# Intake queue processor — every 5 minutes
*/5 * * * * php intake_queue_processor.php >> logs/intake_queue.log 2>&1

# Outbound disposal dispatch — every 10 minutes
*/10 * * * * php disposal_dispatch_cron.php >> logs/dispatch.log 2>&1
```

---

## 🌐 Enterprise REST API Endpoints

| Method | Endpoint | Purpose | Permission |
|--------|----------|---------|------------|
| `GET` | `/api/v1/health` | Health check | health |
| `GET` | `/api/v1/categories` | List categories | categories |
| `POST` | `/api/v1/ingest` | Ingest single record | ingest |
| `POST` | `/api/v1/ingest/batch` | Ingest up to 500 records | batch |
| `POST` | `/api/v1/consent/withdraw` | Log consent withdrawal | consent |
| `GET` | `/api/v1/records/{id}/status` | Check record status | ingest |

**Authentication:** `X-API-Key: adrs_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`

---

## 👥 Roles & Tier Access

| Feature | Admin | DPO | Data Owner |
|---------|-------|-----|------------|
| All Core features | ✅ | ✅/partial | ✅/limited |
| Integration Management | ✅ Enterprise | ❌ | ❌ |
| API Key Management | ✅ Enterprise | ❌ | ❌ |
| Field Mapping & Rules | ✅ Enterprise | ❌ | ❌ |
| Integration Logs | ✅ Enterprise | ✅ read | ❌ |
| Monitoring Dashboard | ✅ Enterprise | ✅ | ❌ |
| Tier Upgrade | ✅ | ❌ | ❌ |

---

## 🔐 Default Credentials (CHANGE IMMEDIATELY)
Admin: `admin@3consult-ng.com` / `password`
DPO:   `dpo@3consult-ng.com`   / `password`

---

## 📜 Compliance Coverage
GDPR Art. 5, 6, 12–22, 17, 30 · UK GDPR · NDPR 2019
CBN AML/CFT · FIRS · ISO 27001 A.8.3

---

## 📁 Prompt Files (19 total)

```
prompts/
├── 00-local-dev-setup.md          ← Laragon + Enterprise API testing
├── 01-project-setup.md            ← Foundation + get_setting()
├── 02-auth-system.md              ← Auth + forgot/reset password
├── 03-data-category-register.md   ← Categories + B1/B2/B5
├── 04-retention-schedule-manager.md ← Records + api/get_category.php
├── 05-automated-engine-cron.md    ← Core cron + Enterprise steps A/B/C
├── 06-audit-log-viewer.md         ← Audit log + NDPR export
├── 07-email-notifications.md      ← PHPMailer + 15+ templates
├── 08-dashboard.md                ← Dashboard (Core)
├── 09-dsar-module.md              ← DSAR tracking
├── 10-file-attachments.md         ← Secure attachments
├── 11-bulk-import.md              ← CSV import
├── 12-advanced-features.md        ← Settings, recalculations, bell
├── 13-enterprise-api-layer.md     ← REST API + endpoints
├── 14-integration-management.md   ← Systems, keys, mappings, rules
├── 15-outbound-disposal-dispatch.md ← Webhook dispatch
├── 16-enterprise-monitoring.md    ← Enterprise dashboard + monitoring
└── 17-enterprise-onboarding-wizard.md ← 5-step wizard + tier upgrade
```

---
*3Consulting Limited · projects@3consult-ng.com · www.3consult-ng.com*
