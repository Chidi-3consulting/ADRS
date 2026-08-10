# ADRS — Automated Data Retention System

A compliance-first, **GDPR/NDPR** data-lifecycle management platform by 3Consulting. ADRS
governs personal data from collection to compliant disposal: a documented retention register,
an automated enforcement engine, immutable evidence, and data-subject-rights workflows.

Built with **Python (Flask) + SQLite/SQLAlchemy** — lightweight, portable, and easy to deploy.
The application lives in [`retention_py/`](retention_py/).

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
lifecycle · secure attachments · two-pass bulk import ·
role-based access (Admin / DPO / Data Owner) · email notifications · NDPR annual report.

**Enterprise:** REST API v1 (`X-API-Key` + SHA-256, rate-limited) · async intake queue +
auto-categorisation · consent-signal matching · outbound disposal webhooks · integration
management UI.

**Advanced:** tamper-evident **hash-chained audit log** + verifier · **2FA (TOTP)** ·
analytics & board reporting · white-label theming ·
ops webhooks · automated DB backups.

## Layout

```
retention_py/
├── main.py                Flask application entry point
├── requirements.txt       Python dependencies
├── alembic/               Database migrations (Alembic)
├── alembic.ini            Alembic configuration
├── app/
│   ├── config.py          Application configuration
│   ├── database.py        SQLAlchemy database setup
│   ├── models.py          ORM models
│   ├── auth.py            Sessions, login/logout, role gates
│   ├── helpers.py         Utilities (audit, categories, email, CSRF, etc.)
│   ├── engine.py          Retention engine, housekeeping, quarterly review
│   ├── enterprise.py      Enterprise features (API keys, intake, dispatch)
│   ├── middleware.py       Security headers, CSRF, auth middleware
│   ├── backups.py         Automated backup utilities
│   ├── routes/            Route blueprints (admin, records, reports, etc.)
│   ├── static/            CSS, JS, images
│   └── templates/         Jinja2 templates
├── tests/                 Pytest test suite
└── storage/               Attachments, logs, backups (gitignored)
```

## Develop & test

```bash
cd retention_py
pip install -r requirements.txt
python -m pytest tests/          # run the full test suite
```

To start the development server:

```bash
cd retention_py
.\dev-start.ps1                  # Windows (PowerShell)
# or
python main.py                   # direct
```

## Deploy

Configure environment variables or a `.env` file for production settings (database URL,
SMTP credentials, secret key). Run database migrations with Alembic:

```bash
alembic upgrade head
```

**SaaS (default):** run migrations, start the server — customers land on the marketing
page, pick **Core** or **Enterprise**, and register their organisation (14-day trial).

## Security

OWASP Top 10 controls, RBAC, 2FA (TOTP), login throttle, CSP/headers, SRI, hash-chained audit,
session timeouts. Report issues to `security@3consult-ng.com` (`/.well-known/security.txt`).

## Design docs

Specs and plans live under [`docs/superpowers/`](docs/superpowers/).
