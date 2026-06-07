# ADRS — Security & Production-Readiness Controls

This document is an **honest map** of what the ADRS *software* provides versus what the
**operating organisation** must run, plus what is genuinely **not applicable**. Production
readiness for a compliance system is a shared responsibility: the application can be
secure-by-design, but certification, monitoring, incident response, and legal obligations are
operational and organisational — they cannot be "coded in".

## 0. Scope & threat model

- **What ADRS is:** a single-tenant (one install per organisation), server-rendered
  **PHP 8.2 + MySQL 8.0** data-retention/compliance portal, deployable on cPanel shared hosting.
- **What ADRS is *not*:** it contains **no AI/LLM** (so prompt-injection / agentic-AI / model
  abuse are **N/A**), it **does not store or process payment-card data** (PCI DSS **N/A**), and
  it **does not move money** (so financial transaction-limit/settlement controls are **N/A**).
- **Primary assets to protect:** personal-data *metadata* (categories, references, lawful basis,
  retention dates), the immutable audit trail, user credentials, and configuration secrets.
- **Primary adversaries:** unauthenticated attackers, authenticated users exceeding their role,
  brute-force/credential-stuffing, tampering with audit evidence, and CDN/supply-chain compromise.

---

## 1. Controls implemented IN THE SOFTWARE (✅)

### Application security (maps to OWASP Top 10)
| Risk | Control in ADRS |
|---|---|
| Injection (A03) | **PDO prepared statements everywhere**; the only string-interpolated SQL uses `(int)` casts or server-generated values (reviewed). |
| Broken access control (A01) | `require_login` + `require_role(...)` enforced **server-side** on every protected page and every sensitive action handler (dispose/approve/legal-hold/consent/users/settings/integrations) — not just hidden in the UI. Data-Owner row scoping (B4). |
| Identification & auth failures (A07) | bcrypt password hashing; **2FA (TOTP, RFC 6238)** with recovery codes; **login brute-force throttle** (5 fails / 15 min per email *or* IP); session fixation prevention (`session_regenerate_id`); **idle (30 min) + absolute (8 h) session timeouts**. |
| Cryptographic failures (A02) | Secrets never in code (gitignored `config.local.php`); SMTP creds in DB, not source; HTTPS enforced (operator); HSTS header in production. |
| Security misconfiguration (A05) | **Security headers**: CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `COOP`, HSTS. `.htaccess` blocks `config`/`includes`/`engine`/`sql`/`storage`/`tests`/dotfiles + disables directory listing. `APP_ENV=production` hides verbose errors. |
| Vulnerable & outdated components (A06) | **No Composer/runtime dependencies** beyond a vendored PHPMailer; CDN assets pinned + **Subresource Integrity (SRI)** so a CDN compromise can't inject code. See SBOM below. |
| Software & data integrity (A08) | **Tamper-evident, hash-chained audit log** + a verifier that pinpoints any altered/deleted row; DB-level `REVOKE UPDATE/DELETE` on `audit_log` (operator step). |
| SSRF / XSS / CSRF | Output escaped via `escape_html` (reviewed, no raw user-data echo); **CSRF token on every state-changing POST**; CSP `frame-ancestors 'none'` + `form-action 'self'`. |
| Rate limiting | Enterprise REST API: per-key/minute rate limit; login throttle as above. |

### Business-logic security
- **Risk-tiered disposal (B5):** sensitive categories require **two-person approval**, and the
  **same user cannot be both approvers** (validated live + regression-tested) — the control that
  prevents a single actor from destroying children's/health/biometric records.
- **Idempotency & race guards** in the retention engine (re-checks legal hold + already-disposed
  inside the disposal transaction).
- **B2 recalculation queue:** retention-period changes never silently mutate record dates.

### Auditability & forensics
- Append-only, hash-chained `audit_log` with full attribution (who/what/when/IP) for every action,
  human or automated; NDPR annual-report export; integrity verifier.

### Privacy-by-design (GDPR/NDPR)
- Retention schedules + automated disposal (storage limitation); legal basis recorded per category;
  consent-withdrawal lifecycle (30-day erasure countdown); DSAR module (30-day clock); legal hold;
  RoPA/Article 30 register; DPIA workflow; breach register (Art. 33 **72-hour** tracking);
  consent receipts; disposal methods (delete / anonymise / archive).

### Resilience & operations (software side)
- Self-contained **automated DB backups** (cron) + rotation; idempotent crons (safe to re-run);
  daily **housekeeping** prunes `login_attempts` / expired reset tokens / old read notifications;
  structured logs to a path outside the web root.

### Supply chain / SBOM
- **Runtime:** PHP 8.2, MySQL 8.0. **Bundled:** PHPMailer (3 files, vendored). **CDN (pinned + SRI):**
  Bootstrap 5.3.3, Bootstrap Icons 1.11.3, Chart.js 4.4.1, qrcode 1.5.1. No package manager, no
  build step → minimal supply-chain surface.

### Responsible disclosure
- `/.well-known/security.txt` (RFC 9116) with a security contact.

---

## 2. Controls the OPERATING ORGANISATION must run (🛠)

These are **not** application code — they are infrastructure, process, or governance, and are the
client/operator's responsibility:

- **Transport security:** valid TLS certificate + force HTTPS; keep TLS config current.
- **Patching:** OS, PHP, MySQL, and web-server patching cadence.
- **Audit-log REVOKE:** run the `REVOKE UPDATE, DELETE ON ….audit_log` step from `DEPLOYMENT.md`.
- **Backups:** verify the backup cron, store copies **off-server/off-site**, and **test restores**.
- **SMTP:** configure real SMTP (the dashboard warns admins until you do).
- **Monitoring & detection (SIEM/log aggregation), alerting, and on-call.**
- **Incident response** plan, breach-notification procedures (regulator + data subjects), runbooks.
- **Penetration testing** and periodic vulnerability scanning by a qualified third party.
- **Access governance:** least-privilege OS/DB accounts, periodic access reviews, segregation of duties.
- **Business continuity / DR:** RTO/RPO targets, failover, capacity planning.
- **Vendor/third-party risk** management; **data-processing agreements** with sub-processors.
- **Legal/contractual:** Terms of Service, privacy notice, records-of-processing accuracy.
- **Certifications** (if pursued): SOC 2, ISO 27001, etc. — evidence collection & external audit.

---

## 3. Not applicable to ADRS (with reasons)

| Area | Why N/A |
|---|---|
| AI/LLM security (prompt injection, jailbreaking, agentic-AI, model/data poisoning) | ADRS contains no AI/ML/LLM component. |
| PCI DSS / cardholder-data protection | ADRS never collects or stores payment-card data. |
| Financial transaction controls (velocity, settlement, AML transaction monitoring) | ADRS does not move money or process transactions; it governs *data retention*. (It *does* help evidence KYC/record-retention obligations.) |
| Multi-tenant isolation | Deployment model is **one install per organisation** (deferred by design); not a shared SaaS. |

---

## 4. Framework cross-reference (how ADRS features support each)

- **NIST CSF** — *Identify:* data register/RoPA, audit trail. *Protect:* RBAC, MFA, encryption-in-
  transit, secure config, throttle. *Detect:* audit log + integrity verifier, ops webhooks, login
  monitoring. *Respond:* breach register (72h), DSAR, legal hold. *Recover:* automated backups.
- **ISO 27001 (Annex A)** — access control (A.9), cryptography (A.10), operations security/logging
  (A.12), comms security/headers (A.13), supplier/SRI (A.15), incident mgmt evidence (A.16). The
  *ISMS* itself is organisational.
- **SOC 2 (Trust Services)** — *Security/Confidentiality:* the controls in §1. *Availability/
  Processing Integrity:* backups + idempotent engine + hash-chained audit. Certification requires an
  external auditor over a period — operator responsibility.
- **GDPR / NDPR** — Art. 5 (storage limitation via retention engine), Art. 6 (lawful basis), Art. 17
  (erasure via consent countdown + disposal), Art. 30 (RoPA), Art. 32 (security of processing), Art.
  33/34 (breach register, 72h), Art. 12–22 (DSAR module).
- **OWASP Top 10** — see §1 table.

---

## 5. Production-readiness sign-off (recommended)

Before go-live, obtain sign-off from: **Engineering, QA, Security, Compliance/DPO, Privacy/Legal,
Operations/SRE, and the Business owner.** Resolve or formally risk-accept all critical findings.
The software controls in §1 are in place and tested (254 automated tests, live end-to-end
validation, security review); §2/§5 are the operator's to complete for *organisational* readiness.

*Report security issues to security@3consult-ng.com.*
