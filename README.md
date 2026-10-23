# SafeData — Automated Data Retention & Governance Platform

A compliance-first, multi-tenant, multi-jurisdiction data lifecycle management platform engineered by **3Consulting**. SafeData governs personal and corporate data assets from point-of-collection to verified, compliant disposal across **14+ international frameworks and full African continental coverage (66+ countries)**.

Built with **Python 3.10+ (FastAPI) + SQLAlchemy ORM (SQLite / MySQL / PostgreSQL) + Jinja2 (Bootstrap 5.3)** — lightweight, secure, and production-ready. The application lives in [`retention_py/`](retention_py/).

---

## Supported Jurisdictions & Legal Baselines

SafeData automatically provisions jurisdiction-specific retention categories and compliance frameworks when an organisation registers:

* **European Union (EU):** General Data Protection Regulation (GDPR) — All 27 EU member states + EEA
* **United Kingdom (UK):** UK GDPR & Data Protection Act 2018
* **Nigeria:** Nigeria Data Protection Regulation (NDPR 2019) / Nigeria Data Protection Act (NDPA 2023), CBN AML/CFT Guidelines, and FIRS Standards
* **United States:** California Consumer Privacy Act (CCPA / CPRA)
* **Brazil:** Lei Geral de Proteção de Dados (LGPD)
* **South Africa:** Protection of Personal Information Act (POPIA)
* **Kenya:** Data Protection Act (ODPC)
* **Ghana:** Data Protection Act (DPC)
* **Singapore:** Personal Data Protection Act (PDPA)
* **India:** Digital Personal Data Protection Act (DPDP)
* **United Arab Emirates:** Personal Data Protection Law (PDPL)
* **Canada:** Personal Information Protection and Electronic Documents Act (PIPEDA)
* **Australia:** Australian Privacy Principles (Privacy Act 1988)
* **Egypt:** Egyptian Data Protection Law (EGDPL)

**Full African continental coverage** — every African country maps to its national data protection law or a GDPR-aligned baseline:

* **East Africa:** Rwanda (Law No. 058/2021 — NCSA), Uganda (DP&PA 2019 — PDPO), Tanzania (PDPA 2022 — PDPC), Ethiopia (Proclamation 1321/2024 — ECA)
* **Southern Africa:** Zambia (DPA No. 3 of 2021), Zimbabwe (Cyber & Data Protection Act 2021 — POTRAZ), Malawi (DPA 2024 — MACRA), Botswana (DPA No. 18 of 2024), Mauritius (DPA 2017), Seychelles (DPA 2023 — Information Commission), Eswatini (DPA No. 5 of 2022), Lesotho (DPA 2011), Cabo Verde (Law 133/V/2001 — CNPD), Mozambique (draft law — GDPR-aligned baseline), Namibia (draft bill — GDPR-aligned baseline)
* **West Africa:** Senegal (Act 2008-12 — CDP), Côte d'Ivoire (Law 2013-450 — ARTCI), Benin (Law 2009-09 — APDP), Togo (Law 2019-014 — IPDCP), Burkina Faso (Law 010-2004/AN — CIL), Mali (Law 2013-015 — APDP), Cameroon (Law 2024/017), Gabon (Law 001/2011 — CNPDCP), Angola (Law 22/11 — APD), Gambia (2025 law pending verification — GDPR-aligned baseline)
* **North Africa:** Morocco (Law 09-08 — CNDP), Tunisia (Organic Law 2004-63 — INPDP), Algeria (Law 18-07 — ANPDP)

Countries whose national law is still in draft fall back to a GDPR-aligned category baseline until the law enters into force.

* **Information Security Standard:** ISO/IEC 27001:2022 Controls (A.8.3 Information Disposal)

---

## Unified Standalone SaaS Architecture

SafeData is a complete, full-featured standalone SaaS platform. All capabilities—from the interactive compliance portal and automated background engine to the REST API, intake queues, outbound disposal webhooks, and cryptographic ledger—are unified into a single cohesive workspace for every tenant.

### Core Capabilities Included in Every Workspace:

* **Automated Retention Lifecycle Engine:** Daily background evaluation flags records entering review windows, calculates statutory dates, batches owner notifications, and purges expired records.
* **Critical Dual-Approval Safeguards:** High-risk, confidential, AML, and special category records requiring dual approval are **never** auto-disposed; they require explicit two-officer authorization.
* **Emergency Disposal Freeze & Dry-Run Mode:** Instantly halt all disposal actions across the organization during active litigation/audits (`is_disposal_frozen`), or simulate retention runs via dry-run mode (`dry_run=True`).
* **Controller vs. Third-Party Processor Tracking:** Monitor internal data controller collections alongside third-party vendors (e.g., cloud hosts, CRM, outsourced payroll) with DPA contract references and compliance verification statuses.
* **REST API v1 Suite:** Cryptographically secured (`X-API-Key` or `Authorization: Bearer`) with SHA-256 hashed keys, granular permissions scoping, and sliding-window rate limiting.
* **Asynchronous Intake Queue:** High-throughput batch data ingestion ($\le 500$ records per call) with automated priority-ordered categorisation rules and field mappings.
* **Outbound Disposal Dispatch Webhooks:** Automated notifications (`POST {base_url}/SafeData/disposal`) instructing source systems (CRM, Core Banking, HR) to delete external copies upon verified disposal.
* **Real-Time Consent Signals:** Listen for external consent revocations matched by `external_ref` to trigger statutory disposal countdown clocks automatically.
* **Retention run & simulation:** admins can simulate a retention run or a consent withdrawal (nothing is changed) and then run it for real; the collection queue is the set of records whose retention period has been reached.
* **Comprehensive Regulatory Registers:**
  * **Article 30 RoPA:** Record of Processing Activities register with third-party processor mappings (`RopaProcessor`).
  * **DPIA Risk Engine:** Data Protection Impact Assessments with necessity, proportionality, likelihood, and severity scoring.
  * **Article 33/34 Breach Register:** Incident logging with automated **72-hour statutory notification countdowns**, severity grading, and authority/subject notification timestamps.
  * **Consent Receipts:** Digital consent certificates with cryptographic SHA-256 receipt hashes.
* **Interactive 8-Chapter Solution Manual:** Built-in operational handbook rendered at `/help`.
* **Two-Pass Validated Bulk Import:** Dry-run CSV validation before committing records to the register.

---

## Advanced Architecture & Security Controls

* **Tamper-Evident Hash-Chained Audit Trail:** Every sensitive operation logs canonical record attributes chained to the previous entry's SHA-256 hash (`prev_hash` + `row_hash`), verifiable via the `/audit/verify` integrity tool.
* **Native 2FA (TOTP):** RFC 6238 two-factor authentication via `pyotp` with QR code setup and hashed emergency recovery codes.
* **Zero-Knowledge Architecture:** Client-side hashing / reference hashing and automated PII detection safeguards scanning notes to prevent unintended data exposure.
* **Step-Up Re-Authentication:** Re-verifies credentials before executing critical actions (record disposal, legal holds, administrative changes).
* **Emergency Disposal Freeze & Dry-Run Engine:** Suspend automated and manual disposal operations instantly across an organisation or simulate retention runs via dry-run mode.
* **Multi-Tenant SaaS Onboarding:** Verified primary domain validation, team invitations via secure token links, 14-day free trial, and geographic currency detection with Paystack payment gateway integration.
* **Platform Super-Admin Portal (`/platform`):** Cross-tenant governance, system metrics, and enterprise licence key provisioning.
* **Native Async Lifespan Tasks:** Background engine execution via native `asyncio.create_task()` in FastAPI lifespan without external daemon dependencies.
* **Defense-in-Depth:** Dynamic nonce-based CSP, CSRF protection, session fixation mitigation, and brute-force login throttling with password history tracking.

---

## Repository Layout

```
retention_py/
├── main.py                FastAPI ASGI application entry point + background task runners
├── requirements.txt       Python dependencies (FastAPI, SQLAlchemy, Uvicorn, pyotp, passlib, etc.)
├── alembic/               Database schema migration scripts
├── alembic.ini            Alembic configuration
├── dev-start.ps1          Windows PowerShell local startup script
├── app/
│   ├── config.py          Application environment configuration
│   ├── database.py        SQLAlchemy database engine and session factory
│   ├── models.py          27+ relational ORM models (Organizations, Records, Audits, Integrations, etc.)
│   ├── auth.py            Sessions, RBAC, TOTP 2FA, password policies, step-up auth
│   ├── helpers.py         Country mappings, category provisioning, audit hashing, mailer, CSRF
│   ├── engine.py          9-Step Retention Engine, disposal executor, quarterly reviews, freeze/dry-run
│   ├── enterprise.py      API key validation, intake queue processor, disposal dispatch webhooks
│   ├── middleware.py      Security headers (nonce CSP), CSRF validation, session enforcement
│   ├── backups.py         Automated database backup routines and storage rotation
│   ├── routes/            FastAPI APIRouters:
│   │   ├── public.py          Landing, auth, registration, trial onboarding, email verification
│   │   ├── dashboard.py       Role-aware executive compliance dashboard
│   │   ├── records.py         Records CRUD, legal holds, consent withdrawal, disposals
│   │   ├── categories.py      Data categories & retention rule management
│   │   ├── api_v1.py          Enterprise REST API v1 endpoints
│   │   ├── integrations_routes.py Connected systems, API keys, mapping, logs
│   │   ├── ropa.py            Article 30 RoPA register and processor sub-entries
│   │   ├── app_pages.py       Audit verifier, DPIA, Breaches, Settings, Help, Billing
│   │   ├── import_records.py  Two-pass validated CSV bulk importer
│   │   ├── recalculations.py  Retention period recalculation queue
│   │   └── platform.py        Platform Super-Admin portal
│   ├── static/            Bootstrap 5.3 stylesheets, client scripts, branding assets
│   └── templates/         Jinja2 HTML templates (themed in 3Consulting orange & teal)
├── tests/                 Pytest test suite (199 test cases covering all modules)
└── storage/               Secure attachments, application logs, backups (gitignored)
```

---

## Detailed Documentation Suite

Comprehensive operational, developer, and compliance handbooks are available in [`Documents/`](Documents/):

1. **[`Documents/01_PRODUCT_OVERVIEW.md`](Documents/01_PRODUCT_OVERVIEW.md):** Executive overview, multi-jurisdiction matrix, tier comparison, and feature index.
2. **[`Documents/02_USER_AND_ADMINISTRATOR_GUIDE.md`](Documents/02_USER_AND_ADMINISTRATOR_GUIDE.md):** RBAC matrix, organization setup, user invitations, and daily administrative operations.
3. **[`Documents/03_API_INTEGRATION_GUIDE.md`](Documents/03_API_INTEGRATION_GUIDE.md):** REST API v1 specifications, Bearer / API key auth, batch intake, and dispatch webhooks.
4. **[`Documents/04_TECHNICAL_ARCHITECTURE_AND_DEPLOYMENT.md`](Documents/04_TECHNICAL_ARCHITECTURE_AND_DEPLOYMENT.md):** System architecture, security middleware, database schemas, and production deployment guide.
5. **[`Documents/05_COMPLIANCE_AUDIT_AND_SECURITY_HANDBOOK.md`](Documents/05_COMPLIANCE_AUDIT_AND_SECURITY_HANDBOOK.md):** 14+ regulatory alignments (GDPR, NDPR, CCPA, etc.), 69 category templates, hash-chain verification, and incident response.
6. **[`Documents/06_DEVELOPER_EXTENSIBILITY_GUIDE.md`](Documents/06_DEVELOPER_EXTENSIBILITY_GUIDE.md):** Data model extensions, new regulatory rule authoring, custom webhook drivers, and test suite execution.

---

## Development & Testing

```bash
cd retention_py
pip install -r requirements.txt
python -m pytest tests/          # executes full 199-test suite
```

To run the development server locally:

```bash
cd retention_py
.\dev-start.ps1                  # Windows PowerShell
# or
python main.py                   # Starts on http://127.0.0.1:8200
```

---

## Production Deployment

1. Configure environment variables in `.env` (Database URL, `SECRET_KEY`, SMTP credentials, Paystack keys).
2. Execute schema migrations:
   ```bash
   alembic upgrade head
   ```
3. Run behind Nginx/Caddy reverse proxy with TLS 1.3:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8200 --workers 4
   ```

### InMotion shared cPanel deployment gate

SafeData is a FastAPI ASGI application launched with Uvicorn/Gunicorn. cPanel's documented Python Application Manager path uses Passenger and a WSGI entry point. Do not upload the production app and assume it will run on shared hosting: first ask InMotion to confirm ASGI support, persistent process/background-job support, Python 3.12 availability, outbound database/object-storage access, and the production database requirements for this account.

Until those checks are confirmed, use the compatibility-first runbook in [`Documents/launch/08_INMOTION_SHARED_CPANEL_DEPLOYMENT.md`](Documents/launch/08_INMOTION_SHARED_CPANEL_DEPLOYMENT.md). It does not change the application runtime or claim that the cPanel plan is compatible. SafeData remains a standalone product; the separately hosted company website and FraudGuard demo are not part of this application deployment.

---

## Security

SafeData incorporates OWASP Top 10 controls, RBAC, native TOTP 2FA, session rotation, dynamic CSP nonces, CSRF protection, login rate-throttling, tamper-evident audit hashing, and zero-knowledge data protections.

Security disclosures: `security@3consult-ng.com` ([`/.well-known/security.txt`](.well-known/security.txt)).
