# 3Consulting — ADRS v2 (Two-Tier Edition)
## CORE + ENTERPRISE | GDPR + NDPR + Global | Python (FastAPI) + SQLAlchemy
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

## Quick Start

### 1. Install dependencies
```bash
cd retention_py
pip install -r requirements.txt
```

### 2. Start development server
```powershell
.\dev-start.ps1       # Windows (PowerShell)
# or
python main.py        # direct — runs on port 8200
```

### 3. Register your organisation
Navigate to `http://localhost:8200/register` and create your first organisation.

### 4. Run tests
```bash
python -m pytest tests/
```

---

## 🗄️ Database Tables

### Core
`organizations` · `users` · `password_resets` · `regulations` · `data_categories` ·
`retention_rules` · `data_records` · `audit_log` · `notifications` · `dsar_requests` ·
`schedule_reviews` · `pending_recalculations` · `attachments` · `import_jobs` ·
`system_settings` · `ropa_entries`

### Enterprise
`connected_systems` · `api_keys` · `field_mappings` · `auto_categorization_rules` ·
`integration_logs` · `intake_queue` · `disposal_dispatches` · `consent_signals`

---

## ⚙️ Background Scheduled Tasks

### Core
```
Daily retention engine — 01:00 AM WAT (APScheduler CronTrigger)
Daily housekeeping — 01:30 AM WAT
Daily database backup — 02:00 AM WAT
```

### Enterprise (additional)
```
Intake queue processor — every 5 minutes (IntervalTrigger)
Outbound disposal dispatch — every 10 minutes (IntervalTrigger)
```

All tasks run within the FastAPI application lifespan via APScheduler — no external
cron configuration required.

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

## 📁 Build Prompts (18 total)

These prompts document the module specifications used to build ADRS:

```
prompts/
├── 00-local-dev-setup.md          ← Python + FastAPI dev environment
├── 01-project-setup.md            ← Foundation + config + database
├── 02-auth-system.md              ← Auth + forgot/reset password
├── 03-data-category-register.md   ← Categories + B1/B2/B5
├── 04-retention-schedule-manager.md ← Records lifecycle
├── 05-automated-engine-cron.md    ← Core engine + Enterprise tasks
├── 06-audit-log-viewer.md         ← Audit log + NDPR export
├── 07-email-notifications.md      ← SMTP mailer + 15+ templates
├── 08-dashboard.md                ← Dashboard (Core)
├── 09-dsar-module.md              ← DSAR tracking
├── 10-file-attachments.md         ← Secure attachments
├── 11-bulk-import.md              ← CSV import
├── 12-advanced-features.md        ← Settings, recalculations, bell
├── 13-enterprise-api-layer.md     ← REST API + endpoints
├── 14-integration-management.md   ← Systems, keys, mappings, rules
├── 15-outbound-disposal-dispatch.md ← Webhook dispatch
├── 16-enterprise-monitoring.md    ← Enterprise dashboard + monitoring
└── 17-enterprise-onboarding-wizard.md ← Onboarding + tier upgrade
```

---
*3Consulting Limited · projects@3consult-ng.com · www.3consult-ng.com*
