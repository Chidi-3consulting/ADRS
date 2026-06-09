# ADRS — Automated Data Retention System

A compliance-first, **GDPR/NDPR** data-lifecycle management platform by 3Consulting. ADRS
governs personal data from collection to compliant disposal: a documented retention register,
an automated enforcement engine, immutable evidence, and data-subject-rights workflows.

Built as **pure PHP 8.2 + MySQL 8.0** — no framework, no Composer — to deploy on ordinary
cPanel shared hosting. The application lives in [`retention/`](retention/).

## Two tiers

- **ADRS Core** — standalone compliance portal. Your team registers records; the engine then
  flags reviews, escalates, and disposes automatically.
- **ADRS Enterprise** — everything in Core **plus** a REST API for automatic data capture from
  connected systems (CRM, core banking, HR…), real-time governance, inbound consent signals,
  and outbound disposal dispatch. Toggle via licence key (Settings → Tier & Licence).

## Capabilities

**Core:** 30-category GDPR/NDPR library · retention register with lawful basis & ownership ·
automated retention engine with a **dual-approval safeguard** (sensitive data is never
auto-disposed) · `delete`/`anonymise`/`archive` disposal · legal hold · consent-withdrawal
lifecycle · DSAR tracking (30-day deadlines) · secure attachments · two-pass bulk import ·
role-based access (Admin / DPO / Data Owner) · email notifications · NDPR annual report.

**Enterprise:** REST API v1 (`X-API-Key` + SHA-256, rate-limited) · async intake queue +
auto-categorisation · consent-signal matching · outbound disposal webhooks · integration
management UI.

**Advanced:** tamper-evident **hash-chained audit log** + verifier · **2FA (TOTP)** ·
**RoPA / Article 30** register · **DPIA** risk scoring · **breach register** with 72-hour
notification tracking · consent receipts · analytics & board reporting · white-label theming ·
ops webhooks · automated DB backups.

## Layout

```
retention/
├── index.php              front controller (clean URLs) + /api/v1 routing
├── sql/                   schema.sql, seed_gdpr_ndpr.sql, migrations/
├── src/
│   ├── api/v1/            Enterprise REST API
│   ├── config/            database.php (+ gitignored config.local.php)
│   ├── includes/          db, auth, helpers, libs (records, engine, enterprise, compliance,
│   │                      analytics, twofa, webhooks, backups…), mailer, layout
│   ├── engine/            retention_cron, intake_queue_processor, disposal_dispatch_cron, backup_cron
│   └── pages/             UI (categories, records, dsar, audit, integrations, ropa, dpia,
│                          breaches, consent_receipts, reports, settings, …)
├── tests/                 no-Composer CLI harness (run.php) + integration/unit tests
└── DEPLOYMENT.md          cPanel go-live runbook
```

## Develop & test

```bash
cd retention
php tests/run.php          # 254 assertions (needs a MySQL test DB)
```

Tests run against a disposable `adrs_test` database (auto-imported from `schema.sql` each run).
Configure DB access in `src/config/config.test.php` (gitignored); see the harness in
[`tests/run.php`](retention/tests/run.php). Pure-logic tests run without a DB; DB-backed tests
skip cleanly when none is reachable.

## Deploy

See **[retention/DEPLOYMENT.md](retention/DEPLOYMENT.md)** — fresh install, the five cron jobs,
the `audit_log` append-only REVOKE, Enterprise activation, security hardening, and upgrades
(including the additive `sql/migrations/` files).

**SaaS (default):** import `schema.sql`, publish the site — customers land on the marketing
page, pick **Core** or **Enterprise**, and register their organisation (14-day trial).
**Dev shortcut:** also import `seed_gdpr_ndpr.sql` → `admin@3consult-ng.com` / `password`
(single-tenant demo mode; forced password change on first login).

## Security

See **[retention/SECURITY.md](retention/SECURITY.md)** — the controls the software implements
(OWASP Top 10, RBAC, 2FA, login throttle, CSP/headers, SRI, hash-chained audit, session
timeouts), what the operating organisation must run (TLS, patching, SIEM, IR, pen-test, backups
off-site, certifications), and what is genuinely N/A (no AI/LLM, no card data). Report issues to
`security@3consult-ng.com` (`/.well-known/security.txt`).

## Design docs

Specs and plans live under [`docs/superpowers/`](docs/superpowers/).
