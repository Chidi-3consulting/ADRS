# SafeData — Automated Data Retention & Governance Platform

A compliance-first, multi-tenant, multi-jurisdiction data lifecycle management platform engineered by **3Consulting**. SafeData governs personal and corporate data assets from point-of-collection to verified, compliant disposal across **14+ international and regional jurisdictions (40+ countries)**.

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
* **Information Security Standard:** ISO/IEC 27001:2022 Controls (A.8.3 Information Disposal)

---

## Operational Tiers

### 1. SafeData Core (Compliance & Governance Portal)
Standalone multi-tenant portal for compliance officers, DPOs, and department heads:
* **Pre-seeded Regulatory Library:** Automatically provisions categories tailored to the organisation's country upon registration.
* **Controller vs. Third-Party Processor Governance:** Track internal data controller categories as well as third-party processor vendors (e.g. cloud providers, outsourced payroll) with DPA contract references and compliance statuses.
* **Full Records Lifecycle:** Active records, retention date calculations, status workflows, and disposal options (`delete` with soft-delete/purge, `anonymise` with PII wiping, `archive`).
* **Critical Dual-Approval Safeguard:** Sensitive, confidential, AML, and special category data flagged with `requires_dual_approval` is **never** auto-disposed; it requires explicit two-person authorization.
* **Legal Hold & Consent Management:** Freeze records during audits or litigation; manage consent withdrawals and issue cryptographic consent receipts.
* **Data Subject Access Requests (DSAR):** Track 6 request types with an automated 30-day statutory countdown and identity verification.
* **Compliance Modules:** Article 30 RoPA (Record of Processing Activities) with sub-processor mapping, DPIA risk scoring assessments, and Article 33/34 Data Breach Incident register with a 72-hour statutory notification clock.
* **Interactive 8-Chapter Solution Manual:** Built-in operational manual rendered at `/help`.
* **Two-Pass Validated Bulk Import:** Dry-run CSV validation before committing records to the register.

### 2. SafeData Enterprise (Automated Integration Engine)
Everything in Core, plus enterprise-scale automation and external system synchronization:
* **REST API v1:** Bearer Token & `X-API-Key` authentication with SHA-256 key hashing (raw keys never stored), permissions scoping, and sliding-window rate limiting.
* **Asynchronous Intake Queue:** High-throughput batch data ingestion ($\le 500$ records per batch) with automated rule-based categorisation by priority.
* **Real-Time Consent Signals:** External consent revocation webhooks matched against existing records by `external_ref`.
* **Outbound Disposal Dispatch:** Automated webhooks (`POST {base_url}/SafeData/disposal`) dispatching disposal instructions back to connected source systems (CRM, Core Banking, HR).
* **Integration Management Hub:** Connected systems registry, API key management, field mapping rules, and real-time integration logs.

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
│   │   ├── app_pages.py       DSAR, Audit verifier, DPIA, Breaches, Settings, Help, Billing
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

---

## Security

SafeData incorporates OWASP Top 10 controls, RBAC, native TOTP 2FA, session rotation, dynamic CSP nonces, CSRF protection, login rate-throttling, tamper-evident audit hashing, and zero-knowledge data protections.

Security disclosures: `security@3consult-ng.com` ([`/.well-known/security.txt`](.well-known/security.txt)).

