# SafeData — Data Retention & Governance Platform — Product Overview

## 1. Executive Summary

The **SafeData — Data Retention & Governance Platform** is a compliance-first, multi-tenant enterprise platform engineered by 3Consulting. SafeData enables organisations to automate data lifecycle management in strict alignment with international and regional data protection regulations across **14+ jurisdictions**, including:

- **EU General Data Protection Regulation (GDPR)**
- **UK General Data Protection Regulation (UK GDPR)**
- **Nigeria Data Protection Regulation (NDPR 2019 / NDPA 2023)**
- **Central Bank of Nigeria (CBN) AML/CFT & Data Protection Guidelines**
- **Federal Inland Revenue Service (FIRS) Financial Record Standards**
- **California Consumer Privacy Act (CCPA / CPRA)** — United States
- **Lei Geral de Proteção de Dados (LGPD)** — Brazil
- **Protection of Personal Information Act (POPIA)** — South Africa
- **Data Protection Act (DPA)** — Kenya
- **Data Protection Act (DPA)** — Ghana
- **Personal Data Protection Act (PDPA)** — Singapore
- **Digital Personal Data Protection Act (DPDP)** — India
- **Personal Data Protection Law (PDPL)** — United Arab Emirates
- **Personal Information Protection and Electronic Documents Act (PIPEDA)** — Canada
- **Australian Privacy Principles (APPs)** — Australia
- **Egyptian Data Protection Law (EGDPL)** — Egypt
- **ISO/IEC 27001:2022 Controls (A.8.3 Information Disposal)**

SafeData automatically provisions jurisdiction-specific retention categories when an organisation registers, based on their country of operation. It governs personal and corporate data assets from point-of-collection to verified, compliant disposal. It prevents premature data deletion, eliminates dangerous indefinite storage liability ("data hoarding"), enforces mandatory legal holds, and maintains an unalterable, tamper-evident audit trail for regulatory inquiries and annual audits.

---

## 2. Unified Standalone SaaS Architecture

SafeData is delivered as a **unified, full standalone SaaS application**. Rather than segmenting capabilities across arbitrary tiers, every tenant receives the complete, end-to-end governance and automation suite out of the box.

```
┌─────────────────────────────────────────────────────────────────────────┐
│              SafeData Unified Standalone SaaS Platform                 │
├────────────────────────────────────┬────────────────────────────────────┤
│   Compliance & Governance Portal   │    Automated Integration Engine    │
├────────────────────────────────────┼────────────────────────────────────┤
│ • Full Records Lifecycle & Register│ • High-Throughput REST API v1      │
│ • Country-Aware Retention Engine   │ • Async Data Intake Queue          │
│ • Dual-Approval Deletion Locks     │ • Rule-Based Auto-Categorisation   │
│ • Legal Holds & Consent Receipts   │ • Outbound Disposal Webhooks       │
│ • DSAR 30-Day Tracking (6 Types)   │ • Real-time Consent Signals        │
│ • Article 30 RoPA & Processor DPA  │ • Connected External Systems Hub   │
│ • Breach Register (72h Countdown)  │ • Sliding-Window Rate Limiting     │
│ • DPIA Risk Scoring Assessments    │ • Real-Time Integration Audit Logs │
│ • Tamper-Evident Hash Chain        │ • Outbound Ops Webhooks (Slack/etc)│
│ • 8-Chapter Solution Manual        │ • Two-Pass Validated Bulk Import   │
└────────────────────────────────────┴────────────────────────────────────┘
```

### Complete Platform Capability Matrix

Every licensed organisation workspace has direct access to the entire governance ecosystem:

| Governance Domain | Technical Capability | Execution Method |
| :--- | :--- | :--- |
| **Data Inventory Registration** | Manual Web UI, 2-Pass Bulk CSV, or REST API v1 | Immediate / Asynchronous Queue |
| **Retention Enforcement** | Automated 9-Step Background Engine | Native FastAPI Lifespan Loop |
| **Disposal Safeguards** | Dual-Approval Four-Eyes Review on Sensitive/AML Data | Mandatory Two-Officer Sign-off |
| **Emergency Controls** | Disposal Freeze (`is_disposal_frozen`) & Dry-Run Simulation | Instant Administrative Toggle |
| **Processor Oversight** | Controller vs. Third-Party Processor DPA Tracking | Dedicated Category & RoPA Linkage |
| **Legal Hold Management** | Litigation / Regulatory Audit Freezing & Lifting | Full Audit-Attributed Workflow |
| **Subject Rights (DSAR)** | 6 Statutory Request Types with Identity Verification | 30-Day Automated Countdown |
| **Article 30 RoPA** | Processing Activities Register with Sub-Processors | Exportable Regulatory Register |
| **Incident Management** | Security Breach Log with Statutory Notifications | 72-Hour Notification Countdown |
| **Risk Assessments** | DPIA Matrix (Necessity, Likelihood, Severity) | Automated Risk Level Scoring |
| **Consent Governance** | Digital Consent Certificates & Inbound Revocations | SHA-256 Receipts & Signal Matching |
| **Cryptographic Proof** | Tamper-Evident Hash-Chained Audit Ledger | SHA-256 Re-Verification Tool |
| **External Integration** | Outbound Webhook Dispatch (`/SafeData/disposal`) | Asynchronous Dispatcher with Retries |
| **API Management** | Unlimited API Keys with SHA-256 Storage & Permissions | Bearer / `X-API-Key` Authenticated |

---

## 3. Multi-Tenant Organisation Model

SafeData operates as a fully multi-tenant platform. Each tenant is an **Organisation** with isolated data, settings, and user accounts.

### Organisation Properties

| Property | Description |
| :--- | :--- |
| `name` | Organisation display name |
| `slug` | URL-safe unique identifier |
| `primary_domain` | Verified email domain for the organisation |
| `country` | ISO 3166-1 alpha-2 code (40+ countries supported) |
| `status` | `active`, `trial`, or `suspended` |
| `subscription_status` | `trial`, `active`, `past_due`, or `cancelled` |
| `billing_email` | Email for payment notifications |
| `enterprise_licence_key` | Offline activation licence key |
| `trial_ends_at` | 14-day trial expiration timestamp |

### Platform Administration

A **Platform Admin** (super-admin) has visibility across all tenants and can manage organisations, generate enterprise licence keys, and monitor platform-wide metrics from the Platform Dashboard (`/platform`).

---

## 4. Core Compliance Safeguards & Principles

### 4.1 Risk-Tiered Dual-Approval Safeguard

To prevent catastrophic accidental data loss or unauthorised deletion of sensitive datasets (such as biometric data, health records, or minor/child information), SafeData implements a mandatory **Risk-Tiered Dual Approval** rule.

If a `DataCategory` (or its active `CategoryRetentionRule`) is flagged with `requires_dual_approval = True`:
1. The automated retention engine **never** auto-disposes records in this category when their retention period expires.
2. Expired records transition into a `due_review` state.
3. Final disposal requires explicit DPO/Admin sign-off within the portal.

### 4.2 Tamper-Evident Hash-Chained Audit Trail

Every compliance event (creation, edit, legal hold, disposal, consent withdrawal, user action) is logged in an append-only audit trail. Each record contains:
- `prev_hash`: SHA-256 hash of the preceding audit entry.
- `row_hash`: SHA-256 hash of the current row data concatenated with `prev_hash`.

The hash payload is constructed as:
```
org_id | action | entity_type | entity_id | performed_by | details_json | ip_address | prev_hash | created_at
```

Any unauthorised database modification or row deletion breaks the cryptographic chain and is immediately flagged by the built-in Audit Verifier.

### 4.3 Legal Hold Superiority

Legal holds supersede all retention rules and automated deletion timers. When a `DataRecord` is placed on Legal Hold:
- Calculated retention end dates are frozen.
- Automated engine disposal triggers bypass the record.
- Manual disposal actions are locked.
- Lift of Legal Hold requires DPO/Admin authorisation and generates an immutable audit record.

### 4.4 Three Disposal Trigger Modes

SafeData supports three distinct disposal trigger mechanisms:

| Trigger | Description | Clock Starts |
| :--- | :--- | :--- |
| `date_based` | Clock runs from record collection date | Immediately on ingestion |
| `consent_withdrawal` | Clock starts when consent withdrawal is recorded | When `consent_withdrawn_at` is set |
| `account_closure` | Clock starts when account termination event is received | When termination signal arrives via API |

---

## 5. Key Functional Modules

1. **Category Register**: Manage retention schedules with lawful bases (Contract, Consent, Legal Obligation, Legitimate Interest, Vital Interest, Public Task), retention periods, disposal methods, and review frequencies. Supports multiple retention rules per category via `CategoryRetentionRule`.

2. **Records Lifecycle Engine**: Tracks data collection dates, target disposal dates, and handles transition states (`active` → `due_review` → `disposal_requested` → `disposed`). Supports `legal_hold` freeze.

3. **DSAR (Data Subject Access Request) Management**: Tracks 30-day fulfilment countdowns for six request types: Access, Rectification, Erasure, Restriction, Portability, and Objection. Supports identity verification, SLA extensions, assignment, and status workflow (`open` → `identity_check` → `in_progress` → `completed` / `rejected` / `extended`).

4. **RoPA (Record of Processing Activities)**: Article 30 compliance register documenting categories of processing, data transfers, security measures, controller/processor roles, and linked sub-processor records via `RopaProcessor`.

5. **Breach Incident Management**: Log and track data breaches with severity scoring (low/medium/high/critical), 72-hour notification deadlines, authority and data subject notification tracking, and full status workflow (`open` → `contained` → `notified` → `closed`).

6. **DPIA (Data Protection Impact Assessment)**: Risk assessment module with necessity, proportionality, likelihood, and severity scoring. Generates composite risk levels (low/medium/high) with mitigation tracking and approval workflow.

7. **Consent Receipt Tracking**: Records individual consent events with purpose, lawful basis, channel, timestamps, and cryptographic receipt hashes. Tracks withdrawals.

8. **Bulk Data Importer**: Two-pass validation importer for ingesting legacy data registers safely via CSV. Tracks import jobs with row-level success/failure reporting.

9. **Integrations Manager (Enterprise)**: API Key management (SHA-256 hashed, shown once), Connected Systems registry, Field Mapping, Auto-Categorisation rule engines, Intake Queue, and Disposal Dispatch.

10. **Notifications Centre**: In-app notification system with role-based routing, DPO fallback for unowned categories, follow-up reminders for unread notifications (>3 days), and escalation alerts.

11. **Recalculation Queue**: When category retention rules are modified, affected records are queued for review. Administrators can approve recalculation or keep original dates.

12. **Billing & Subscription**: 14-day free trial, subscription management, enterprise licence key redemption, and trial expiry enforcement.

13. **Platform Administration**: Multi-tenant platform dashboard for super-admins to manage all organisations, generate licence keys, and monitor platform health.

---

## 6. Security Architecture

| Security Layer | Implementation |
| :--- | :--- |
| **Password Hashing** | bcrypt (direct, via `bcrypt.hashpw()`) |
| **Password Policy** | Minimum 10 characters, must include letters and numbers |
| **Session Management** | Signed cookies via `itsdangerous.URLSafeSerializer` |
| **Session Timeouts** | 30-minute idle timeout, 8-hour absolute session cap |
| **CSRF Protection** | Per-session token (64 hex chars), constant-time comparison, form field injection |
| **Content Security Policy** | Per-request nonce-based `script-src`, strict `frame-ancestors 'none'` |
| **Security Headers** | X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, Permissions-Policy, HSTS (production) |
| **Login Throttling** | 5 failed attempts per email/IP within 15 minutes triggers lockout |
| **Two-Factor Authentication** | TOTP (RFC 6238) with QR provisioning, 8 recovery codes |
| **Email Verification** | Token-based verification with 24-hour expiry |
| **Role-Based Access Control** | Three roles: Admin, DPO, Data Owner — plus Platform Admin flag |
| **Forced Password Change** | `must_change_password` flag redirects to profile on login |
| **API Authentication** | Bearer token with SHA-256 key hashing, per-key rate limits, expiry dates |

---

## 7. Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Backend Framework** | Python 3.10+ with FastAPI (Async HTTP & Pydantic validation) |
| **ASGI Server** | Uvicorn |
| **Database ORM** | SQLAlchemy 2.0 Declarative Models |
| **Database Engines** | SQLite (local/dev), MySQL (PyMySQL driver), PostgreSQL (production) |
| **Migrations** | Alembic with auto-schema patching via `ensure_schema_columns()` |
| **Templating** | Jinja2 with custom security context injectors (CSP Nonce, CSRF tokens) |
| **Password Security** | bcrypt (direct), itsdangerous (signed session tokens) |
| **Background Tasks** | Native `asyncio.create_task()` within FastAPI lifespan context |
| **HTTP Client** | httpx (async, for outbound webhook dispatch) |
| **Frontend Layer** | Vanilla JS ES6+, Bootstrap 5.3, Bootstrap Icons |
| **Testing** | Pytest with FastAPI TestClient and isolated SQLite databases |
