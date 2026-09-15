# SafeData — Compliance, Audit & Security Hardening Handbook

This handbook provides DPOs, Data Protection Auditors, Information Security Officers, and Compliance Managers with an exhaustive breakdown of regulatory alignments, pre-seeded regulatory libraries, tamper-evident verification mechanisms, security controls, and incident response workflows implemented in **SafeData**.

---

## 1. Supported Jurisdictions & Regulatory Compliance

SafeData supports **14+ regulatory frameworks** across international jurisdictions. When an organisation registers, jurisdiction-specific retention categories are automatically provisioned based on the organisation's country of operation via the `COUNTRY_REGULATION_MAP` in `helpers.py`.

### 1.1 Jurisdiction Matrix

| Country / Region | Regulation | Code | Supervisory Authority | Categories Seeded |
| :--- | :--- | :--- | :--- | :---: |
| **European Union** | General Data Protection Regulation (GDPR) | `GDPR` | National DPA (per member state) | 15 |
| **United Kingdom** | UK General Data Protection Regulation | `UK_GDPR` | ICO | 15 (GDPR) |
| **Nigeria** | Nigeria Data Protection Regulation (NDPR 2019 / NDPA 2023) | `NDPR` | NITDA | 10 |
| **United States** | California Consumer Privacy Act (CCPA / CPRA) | `CCPA` | State AG / FTC | 5 |
| **Brazil** | Lei Geral de Proteção de Dados (LGPD) | `LGPD` | ANPD | 5 |
| **South Africa** | Protection of Personal Information Act (POPIA) | `POPIA` | Information Regulator | 5 |
| **Kenya** | Data Protection Act | `DPA_KE` | ODPC | 3 |
| **Ghana** | Data Protection Act | `DPA_GH` | Data Protection Commission | 3 |
| **Singapore** | Personal Data Protection Act (PDPA) | `PDPA_SG` | PDPC | 3 |
| **India** | Digital Personal Data Protection Act (DPDP) | `DPDP` | Data Protection Board | 3 |
| **United Arab Emirates** | Personal Data Protection Law (PDPL) | `PDPL` | UAE Data Office | 3 |
| **Canada** | Personal Information Protection and Electronic Documents Act (PIPEDA) | `PIPEDA` | OPC | 3 |
| **Australia** | Australian Privacy Principles (APPs) | `APPs` | OAIC | 3 |
| **Egypt** | Egyptian Data Protection Law (EGDPL) | `EGDPL` | Data Protection Center | 3 |

All EU/EEA member states (Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands, Poland, Portugal, Romania, Slovakia, Slovenia, Spain, Sweden, Iceland, Liechtenstein, Norway, Switzerland) are mapped to the GDPR framework.

Every jurisdiction also receives the **5 Dual-Framework** categories (BOTH): Cross-Border Transfer Records, Privacy Notices, Children's Data, Whistleblowing Records, and Biometric Data.

### 1.2 Regulatory Article Alignment

| Regulation & Section | Article / Clause | SafeData Technical Implementation |
| :--- | :--- | :--- |
| **GDPR** Art. 5(1)(e) | Storage Limitation | Automated retention engine calculates `retention_end_date` and enforces disposal upon expiration |
| **GDPR** Art. 6 | Lawful Basis | Every `DataCategory` mandates selection of explicit lawful basis (`consent`, `contract`, `legal_obligation`, `legitimate_interest`, `vital_interest`, `public_task`) |
| **GDPR** Art. 17 | Right to Erasure | Implemented via `execute_disposal()` (delete/anonymise) and Consent Withdrawal API (`/api/v1/consent/withdraw`) |
| **GDPR** Art. 25 | Data Protection by Design | Dual-approval safeguards, automated retention math, legal hold superiority |
| **GDPR** Art. 30 | Records of Processing | Dedicated `ropa_entries` register with sub-processor tracking via `RopaProcessor` |
| **GDPR** Art. 33 | Breach Notification (72 hrs) | `BreachIncident` model with severity scoring, 72-hour `notify_deadline`, authority and data subject notification tracking |
| **GDPR** Art. 35 | DPIA | `DpiaAssessment` model with necessity, proportionality, likelihood, severity scoring and risk level calculation |
| **NDPR** Part 2.2 | Data Processing Principles | Mandates explicit retention periods per category; prohibits indefinite retention |
| **NDPR** Part 2.5 | Data Security | Multi-layer RBAC, bcrypt hashing, TOTP 2FA, nonce-based CSP, CSRF, login throttling |
| **NDPR** Part 4.1 | Annual Audit | Country-aware compliance report generator with NITDA-compatible export |
| **CBN AML/CFT** | Section 4 | Seeded 5-year retention rules for customer KYC post-account closure |
| **FIRS** | Financial Recordkeeping | 6-year retention for tax and accounting records |
| **CCPA** §1798.105 | Right to Delete | Consumer request tracking with 2-year evidence retention |
| **CCPA** §1798.120 | Right to Opt-Out | Marketing opt-out records with consent withdrawal tracking |
| **LGPD** Art. 17-22 | Data Subject Rights | Full DSAR lifecycle with 5-year post-closure retention |
| **POPIA** Section 11 | Conditions for Lawful Processing | Consent management with withdrawal tracking |
| **ISO 27001:2022** A.8.3 | Information Disposal | Multi-step disposal approval, binary file shredding, cryptographic audit logging |

---

## 2. Pre-Seeded Regulatory Data Category Library

SafeData includes **69 pre-configured category templates** across 14 regulatory frameworks. Categories are automatically provisioned on organisation registration based on country selection.

### 2.1 GDPR Categories (15)

| Category Name | Default Retention | Lawful Basis | Disposal Trigger | Method | Dual Approval |
| :--- | :---: | :--- | :--- | :---: | :---: |
| Employee Personnel Records | 6 Years post-employment | Legal Obligation | date_based | Delete | No |
| Employee Payroll & Tax Records | 7 Years (HMRC) | Legal Obligation | date_based | Archive | No |
| Recruitment & Application Data | 6 Months post-rejection | Legitimate Interest | date_based | Delete | No |
| Customer Contracts & Agreements | 7 Years post-expiry | Contract | date_based | Archive | No |
| Marketing Consent Records | Until withdrawal + 1yr | Consent | consent_withdrawal | Delete | No |
| Website & Server Access Logs | 6 Months | Legitimate Interest | date_based | Delete | No |
| Customer Support Tickets | 3 Years post-resolution | Contract | date_based | Anonymise | No |
| Financial Transactions & Invoices | 7 Years (HMRC) | Legal Obligation | date_based | Archive | No |
| Health & Medical Records (Employees) | 10 Years post-employment | Legal Obligation | date_based | Delete | **Yes** |
| CCTV Footage | 30 Days | Legitimate Interest | date_based | Delete | No |
| Data Breach Incident Records | 5 Years (ICO) | Legal Obligation | date_based | Archive | No |
| DSAR Records | 3 Years post-closure | Legal Obligation | date_based | Archive | No |
| Supplier & Vendor Contracts | 7 Years post-expiry | Contract | date_based | Archive | No |
| DPIA Reports | 5 Years | Legal Obligation | date_based | Archive | No |
| Training & Certification Records | 3 Years | Legal Obligation | date_based | Delete | No |

### 2.2 NDPR Categories (10)

| Category Name | Default Retention | Lawful Basis | Disposal Trigger | Method | Dual Approval |
| :--- | :---: | :--- | :--- | :---: | :---: |
| Customer KYC & Onboarding Data | 5 Years (CBN AML) | Legal Obligation | date_based | Archive | No |
| Employee Personal Data (NDPR) | 7 Years post-employment | Legal Obligation | date_based | Delete | No |
| Financial Records (FIRS Compliance) | 6 Years (FIRS) | Legal Obligation | date_based | Archive | No |
| Customer Personal Data (Nigeria) | 3 Years post-relationship | Contract | date_based | Anonymise | No |
| Health Data (Employees - Nigeria) | 10 Years | Legal Obligation | date_based | Delete | **Yes** |
| Consent Records (NDPR) | Until withdrawal + 1yr | Consent | consent_withdrawal | Delete | No |
| Third-Party Data Sharing Agreements | 7 Years | Legal Obligation | date_based | Archive | No |
| Data Breach Records (NDPR) | 5 Years | Legal Obligation | date_based | Archive | No |
| Annual Data Audit Reports | 7 Years | Legal Obligation | date_based | Archive | No |
| Procurement & Tender Records | 6 Years | Legal Obligation | date_based | Archive | No |

### 2.3 Dual-Framework Categories (5) — Applied to All Jurisdictions

| Category Name | Default Retention | Lawful Basis | Disposal Trigger | Method | Dual Approval |
| :--- | :---: | :--- | :--- | :---: | :---: |
| Cross-Border Data Transfer Records | 5 Years | Legal Obligation | date_based | Archive | No |
| Privacy Notices & Policy Versions | 5 Years from retirement | Legal Obligation | date_based | Archive | No |
| Children's Data (Under 13/18) | 5 Years or until age 21 | Consent | consent_withdrawal | Delete | **Yes** |
| Whistleblowing & Grievance Records | 5 Years post-closure | Legal Obligation | date_based | Archive | No |
| Biometric Data | Until consent withdrawn | Consent | consent_withdrawal | Delete | **Yes** |

### 2.4 Additional Jurisdiction Categories

Each of the following jurisdictions includes **3–5 purpose-built templates**: CCPA (5), LGPD (5), POPIA (5), DPA Kenya (3), DPA Ghana (3), PDPA Singapore (3), DPDP India (3), PDPL UAE (3), PIPEDA Canada (3), APPs Australia (3), EGDPL Egypt (3). Templates cover employee records, customer PII, financial records, and consent management per local law.

---

## 3. Cryptographic Tamper-Evident Audit Chain

Every compliance event is logged in an append-only `audit_log` table. Each entry is protected by a SHA-256 hash chain that detects any unauthorised modification.

```
  [Audit Entry N-1]                 [Audit Entry N]
┌──────────────────┐             ┌──────────────────┐
│ ID: 101          │             │ ID: 102          │
│ Action: record_… │             │ Action: dispose… │
│ prev_hash: 0a8f… │ ──────────> │ prev_hash: e3b0… │ (Matches Row 101 row_hash)
│ row_hash:  e3b0… │             │ row_hash:  8f91… │
└──────────────────┘             └──────────────────┘
```

### 3.1 Hash Calculation Formula

For any given audit row $R$, the `row_hash` is computed as:

```
row_hash = SHA-256(
    org_id | action | entity_type | entity_id | performed_by |
    details_json | ip_address | prev_hash | created_at
)
```

Where:
- `|` is a literal pipe delimiter
- `details_json` is the canonical, key-sorted JSON representation of the details field
- `created_at` is formatted as `YYYY-MM-DD HH:MM:SS`
- `prev_hash` is the `row_hash` of the previous audit entry (or `"0" × 64` for the first entry)

### 3.2 Audit Trail Column Reference

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer | Auto-incrementing primary key |
| `organization_id` | Integer (FK) | Tenant isolation |
| `action` | String(100) | Event type (e.g., `record_disposed_delete`, `legal_hold_set`, `consent_withdrawn`) |
| `entity_type` | String(100) | Target entity type (e.g., `data_record`, `data_category`, `system`) |
| `entity_id` | Integer | Target entity primary key |
| `performed_by` | Integer (FK) | User who performed the action |
| `details` | JSON | Structured event metadata |
| `ip_address` | String(45) | Client IP address |
| `prev_hash` | String(64) | SHA-256 hash of the preceding entry |
| `row_hash` | String(64) | SHA-256 hash of the current entry |
| `created_at` | DateTime | Timestamp of the event |

### 3.3 Chain Verification

The `verify_audit_chain()` function walks the entire audit log and verifies:
1. Each entry's `prev_hash` matches the previous entry's `row_hash`.
2. Each entry's `row_hash` matches the recomputed hash from its data.

If an attacker modifies any row directly in the database, the chain breaks at that point. The verifier returns `{ok: False, checked: N, broken_at: ID}`.

---

## 4. Country-Aware Annual Compliance Reporting

SafeData generates annual compliance reports that are **automatically labelled and formatted** based on the organisation's country of operation using the `COUNTRY_REGULATION_LABELS` lookup:

| Country | Report Title | Authority | Applicable Law |
| :--- | :--- | :--- | :--- |
| Nigeria | NDPR Annual Compliance Report | NITDA | NDPR/NDPA |
| United Kingdom | UK GDPR Annual Compliance Report | ICO | UK GDPR |
| EU Member States | GDPR Annual Compliance Report | National DPA | EU GDPR |
| United States | CCPA Annual Compliance Report | State AG / FTC | CCPA/CPRA |
| Brazil | LGPD Annual Compliance Report | ANPD | LGPD |
| South Africa | POPIA Annual Compliance Report | Information Regulator | POPIA |
| Kenya | DPA Kenya Annual Compliance Report | ODPC | DPA Kenya |
| Ghana | DPA Ghana Annual Compliance Report | Data Protection Commission | DPA Ghana |
| Singapore | PDPA Annual Compliance Report | PDPC | PDPA |
| India | DPDP Annual Compliance Report | Data Protection Board | DPDP Act |
| UAE | PDPL Annual Compliance Report | UAE Data Office | PDPL |
| Canada | PIPEDA Annual Compliance Report | OPC | PIPEDA |
| Australia | APPs Annual Compliance Report | OAIC | Privacy Act / APPs |
| Egypt | EGDPL Annual Compliance Report | Data Protection Center | EGDPL |

### Report Contents

The `build_compliance_report()` function compiles:
- Total active data categories
- Active records count
- Records on legal hold
- Disposals by method (delete, anonymise, archive) for the target year
- Total audit events for the year
- Compliance score (0–100%)

Reports are exportable as CSV via `compliance_report_to_csv_rows()`.

---

## 5. Security Architecture

### 5.1 Authentication & Access Control

| Security Layer | Implementation |
| :--- | :--- |
| **Password Hashing** | bcrypt (direct, via `bcrypt.hashpw()` / `bcrypt.checkpw()`) |
| **Password Policy** | Minimum 10 characters, must include both letters and numbers |
| **Forced Password Change** | `must_change_password` flag redirects to `/profile` on login |
| **Session Management** | Signed cookies via `itsdangerous.URLSafeSerializer` |
| **Session Idle Timeout** | 30 minutes of inactivity |
| **Session Absolute Timeout** | 8-hour hard cap per session |
| **Two-Factor Authentication** | TOTP (RFC 6238) with QR provisioning, 8 recovery codes |
| **Email Verification** | Token-based with SHA-256 hashing, 24-hour expiry |
| **Role-Based Access Control** | Three roles: Admin, DPO, Data Owner — plus Platform Admin super-flag |
| **API Authentication** | Bearer token with SHA-256 key hashing, per-key rate limits and expiry dates |

### 5.2 Login Brute-Force Throttling

SafeData implements login throttling using the `LoginAttempt` model:

- Every login attempt (success or failure) is recorded with email, IP address, and timestamp.
- After **5 failed attempts** for the same email or IP within a **15-minute rolling window**, the account is temporarily locked.
- The lockout duration equals the remaining time in the 15-minute window from the earliest failed attempt.
- Throttling is implemented in `login_throttle_seconds()` in `auth.py`.
- The `run_housekeeping()` function prunes login attempt records older than 7 days.

### 5.3 CSRF Protection

- **Token**: 64 hex characters (`secrets.token_hex(32)`) stored in the signed session cookie.
- **Validation**: Constant-time comparison (`secrets.compare_digest()`) on every POST/PUT/PATCH/DELETE request.
- **Exempt routes**: API endpoints (`/api/*`), health checks, static files, webhooks.
- **Template injection**: `csrf_field` is automatically injected into all Jinja2 template contexts as a hidden form input.

### 5.4 Content Security Policy (CSP)

Per-request nonce-based CSP headers prevent cross-site scripting:

- A unique nonce is generated for every request (`secrets.token_urlsafe(16)`).
- The nonce is injected into the CSP `script-src` directive and made available to templates via `csp_nonce`.
- All inline `<script>` tags in templates must include `nonce="{{ csp_nonce }}"`.
- `frame-ancestors 'none'` prevents clickjacking.

### 5.5 Additional Security Headers

| Header | Value |
| :--- | :--- |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=(), payment=(), usb=()` |
| `Cross-Origin-Opener-Policy` | `same-origin` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` (production only) |

---

## 6. Data Breach Incident Management (72-Hour SLA)

Under GDPR Art. 33, NDPR Part 2.10, and equivalent laws, data breaches must be reported to supervisory authorities within **72 hours** of awareness.

### 6.1 Breach Lifecycle

```
┌─────────────────┐      Log Incident      ┌─────────────────┐
│ Breach Detected │ ────────────────────── │      open       │
└─────────────────┘                        └────────┬────────┘
                                                    │
                                        Start 72-Hour Countdown
                                                    │
                                                    ▼
                                           ┌─────────────────┐
                                           │   contained     │
                                           └────────┬────────┘
                                                    │
                                        Notify Authority + Subjects
                                                    │
                                                    ▼
                                           ┌─────────────────┐
                                           │    notified     │
                                           └────────┬────────┘
                                                    │
                                           Close Investigation
                                                    │
                                                    ▼
                                           ┌─────────────────┐
                                           │     closed      │
                                           └─────────────────┘
```

### 6.2 BreachIncident Model Properties

| Property | Description |
| :--- | :--- |
| `reference` | Unique incident reference number |
| `title` | Incident title |
| `description` | Detailed description |
| `discovered_at` | When the breach was discovered |
| `occurred_at` | When the breach actually occurred |
| `severity` | `low`, `medium`, `high`, or `critical` |
| `affected_records` | Estimated number of records affected |
| `status` | `open` → `contained` → `notified` → `closed` |
| `notify_deadline` | 72-hour notification deadline (auto-calculated) |
| `notified_authority_at` | When the supervisory authority was notified |
| `notified_subjects_at` | When data subjects were notified |
| `reported_by` | User who logged the incident |

---

## 7. DPIA (Data Protection Impact Assessment) Module

The `DpiaAssessment` model implements risk scoring per GDPR Art. 35:

### 7.1 Scoring Components

| Dimension | Scale | Description |
| :--- | :---: | :--- |
| `necessity_score` | 1–5 | How necessary is the processing? |
| `proportionality_score` | 1–5 | Is the processing proportionate to the purpose? |
| `likelihood_score` | 1–5 | How likely is the risk to materialise? |
| `severity_score` | 1–5 | How severe would the impact be? |

### 7.2 Risk Calculation

- `risk_score` = `likelihood_score` × `severity_score` (composite, 1–25)
- `risk_level`:
  - `low` — risk_score ≤ 5
  - `medium` — risk_score 6–14
  - `high` — risk_score ≥ 15

### 7.3 DPIA Workflow

Status progression: `draft` → `in_review` → `approved` / `rejected`

| Field | Description |
| :--- | :--- |
| `mitigation` | Risk mitigation measures documented |
| `assessed_by` | User who conducted the assessment |
| `approved_by` | User who approved (or rejected) |
| `approved_at` | Approval timestamp |

---

## 8. Consent Receipt Tracking

The `ConsentReceipt` model provides cryptographic evidence of individual consent events:

| Property | Description |
| :--- | :--- |
| `data_subject_ref` | Reference to the data subject |
| `purpose` | Processing purpose for which consent was given |
| `lawful_basis` | Applicable lawful basis |
| `channel` | Channel through which consent was collected (web, email, paper) |
| `given_at` | Timestamp of consent |
| `withdrawn_at` | Timestamp of withdrawal (if applicable) |
| `receipt_hash` | SHA-256 hash of the receipt data for tamper evidence |

---

## 9. Subscription & Access Enforcement

SafeData enforces subscription status and trial expiry at the middleware level:

- **Trial Period**: 14-day free trial from registration. Tracked via `Organization.trial_ends_at`.
- **Subscription Status**: `trial`, `active`, `past_due`, or `cancelled` — stored in `Organization.subscription_status`.
- **Organisation Status**: `active`, `trial`, or `suspended`.
- **Enforcement**: The `SessionEnforcementMiddleware` checks subscription status on every authenticated request. Suspended organisations or expired trials are redirected to `/billing`.
- **Enterprise Licence Keys**: Platform Admins can generate offline activation licence keys (`EnterpriseLicenceKey` model) which organisations can redeem to activate extended platform capabilities.
- **Setup-Complete Guard**: Until the initial system configuration is completed (`setup_complete` system setting), all users are redirected to `/setup`.
