# SafeData — Technical Architecture & Deployment Manual

This document details the system design, database architecture, middleware security stack, background task execution model, and production deployment procedures for the **SafeData — Data Retention & Governance Platform** (Python Edition).

---

## 1. System Architecture & Components

SafeData is built as a unified Python web application using FastAPI, SQLAlchemy ORM, and Jinja2 templates, structured to run cleanly on virtual machines, Docker containers, or cloud app services.

```
                               ┌────────────────────────────────┐
                               │     Web Browsers (HTTPS)       │
                               │  Admin / DPO / Data Owners     │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Nginx / Caddy Reverse Proxy (TLS 1.3)                    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                       ┌───────────────┴───────────────┐
                       │    External Systems (REST)    │
                       │ CRM · Core Banking · HR · ERP │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Uvicorn ASGI Server (Port 8200)                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    FastAPI Application (main.py)                      │  │
│  │                                                                       │  │
│  │ ┌────────────────────┐ ┌──────────────────┐ ┌───────────────────────┐ │  │
│  │ │ Security Middleware │ │  Route Handlers  │ │ AsyncIO Background   │ │  │
│  │ │  Stack (3 layers)  │ │  (Jinja2 / API)  │ │ Tasks (Lifespan)     │ │  │
│  │ └────────────────────┘ └────────┬─────────┘ └──────────┬────────────┘ │  │
│  └──────────────────────────────────┼──────────────────────┼──────────────┘  │
└─────────────────────────────────────┼──────────────────────┼─────────────────┘
                                      │                      │
                                      ▼                      ▼
                      ┌─────────────────────────────┐  ┌─────────────────┐
                      │   SQLAlchemy 2.0 ORM        │  │ Disk Storage    │
                      │ (SQLite / MySQL / Postgres)  │  │ storage/        │
                      └─────────────────────────────┘  │ ├ attachments/  │
                                                       │ ├ logs/         │
                                                       │ └ backups/      │
                                                       └─────────────────┘
```

### Component Breakdown

1. **ASGI Server**: Uvicorn serving the FastAPI application on port `8200` (default). Production deployments use `--workers 4`.
2. **Web Framework**: FastAPI handling route dispatch, OpenAPI validation (Pydantic), and Dependency Injection (`get_db`).
3. **Database Engine**: SQLAlchemy 2.0 mapping 27+ Python data models to relational tables.
4. **Background Task Scheduler**: Native Python `asyncio.create_task()` within FastAPI's `@asynccontextmanager` lifespan. Tasks run as infinite `while True: await asyncio.sleep(N)` loops inside the application process — **no external schedulers** (no APScheduler, no cron daemons).
5. **Security Middleware Stack**: Three Starlette `BaseHTTPMiddleware` layers applied in order: `SecurityHeadersMiddleware` → `CSRFMiddleware` → `SessionEnforcementMiddleware`.
6. **Storage Layer**: Managed directory structure under `storage/` for file attachments, application logs, and automated database backups.

---

## 2. Security Middleware Stack

SafeData applies three middleware layers to every request. Middleware is added in reverse order in `main.py` (last added = outermost):

```python
# main.py — Middleware registration order
app.add_middleware(SessionEnforcementMiddleware)  # Innermost
app.add_middleware(CSRFMiddleware)                 # Middle
app.add_middleware(SecurityHeadersMiddleware)      # Outermost
```

**Execution order per request**: `SecurityHeadersMiddleware` → `CSRFMiddleware` → `SessionEnforcementMiddleware` → Route Handler → Response.

### 2.1 SecurityHeadersMiddleware

Injects hardening headers on every response:

| Header | Value |
| :--- | :--- |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=(), payment=(), usb=()` |
| `Cross-Origin-Opener-Policy` | `same-origin` |
| `X-Permitted-Cross-Domain-Policies` | `none` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` (production only) |
| `Content-Security-Policy` | Nonce-based `script-src` (per-request `secrets.token_urlsafe(16)`) |

**CSP Policy**:
```
default-src 'self';
script-src 'self' 'nonce-{csp_nonce}' https://cdn.jsdelivr.net;
style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline';
img-src 'self' data:;
font-src 'self' https://cdn.jsdelivr.net;
connect-src 'self';
frame-ancestors 'none';
base-uri 'self';
form-action 'self'
```

### 2.2 CSRFMiddleware

- **Token Generation**: 64-hex-char token (`secrets.token_hex(32)`) stored in session.
- **Validation**: On mutating methods (POST/PUT/PATCH/DELETE), compares submitted `csrf_token` form field against session token using **constant-time comparison** (`secrets.compare_digest()`).
- **Exempt Routes**: API endpoints (`/api/*`), health checks, static files, webhooks, and OpenAPI docs.
- **Body Re-injection**: Reads raw body bytes for CSRF extraction, then re-injects via custom `_receive()` callable to avoid consuming the request stream.

### 2.3 SessionEnforcementMiddleware

Enforces multiple security policies on authenticated users:

| Policy | Behaviour |
| :--- | :--- |
| **Idle Timeout** | 30-minute inactivity → redirect to `/login?expired=1`, session cleared |
| **Absolute Timeout** | 8-hour hard cap → redirect to `/login?expired=1`, session cleared |
| **Password Change** | Users with `must_change_password = True` → redirect to `/profile?required=1` |
| **Email Verification** | Unverified users → redirect to `/verify_email` |
| **2FA Enforcement** | Required roles without 2FA → redirect to `/settings?tab=twofa` |
| **Subscription Status** | Suspended orgs → redirect to `/billing?suspended=1` |
| **Trial Expiry** | Expired trial → redirect to `/billing?trial_expired=1` |
| **Setup Guard** | System not yet configured → redirect to `/setup` |

---

## 3. Background Scheduled Tasks

Background tasks are launched as `asyncio.create_task()` calls within the FastAPI lifespan context manager. They run as infinite loops with `asyncio.sleep()` intervals.

```python
# main.py — Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    task1 = asyncio.create_task(retention_scheduler_task())
    task2 = asyncio.create_task(housekeeping_scheduler_task())
    task3 = asyncio.create_task(backup_scheduler_task())
    task4 = asyncio.create_task(disposal_dispatch_scheduler_task())
    task5 = asyncio.create_task(intake_queue_scheduler_task())
    yield
    task1.cancel()
    task2.cancel()
    task3.cancel()
    task4.cancel()
    task5.cancel()
```

| Task | Frequency | Target Function | Source Module | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Retention Engine** | Every **10 minutes** (`sleep(600)`) | `run_retention_checks()` | `app.engine` | Iterates all organisations. Flags `due_review`, processes consent withdrawals, auto-disposes non-dual-approval records, sends escalations and follow-ups. |
| **Housekeeping** | Every **1 hour** (`sleep(3600)`) | `run_housekeeping()` | `app.engine` | Prunes: login attempts older than 7 days, expired password resets older than 7 days, read notifications older than 180 days. |
| **Database Backup** | Every **24 hours** (`sleep(86400)`) | `backup_database()` | `app.backups` | Dumps the full database to `storage/backups/SafeData_backup_{timestamp}.sql`. Prunes backups older than 30 days. |
| **Disposal Dispatch** | Every **10 minutes** (`sleep(600)`) | `process_disposal_dispatches()` | `app.enterprise` | Enterprise only. Sends outbound webhook disposal instructions to connected external systems. |
| **Intake Queue** | Every **5 minutes** (`sleep(300)`) | `process_intake_queue()` | `app.enterprise` | Enterprise only. Processes inbound API intake buffer records with auto-categorisation. |

> **Note**: Tasks 4 and 5 (disposal dispatch and intake queue) are gated behind the `SafeData_tier = "enterprise"` system setting. They execute as no-ops for Core tier organisations.

### Housekeeping Detail

The `run_housekeeping()` function prunes the following data:

| Target Table | Condition | Retention |
| :--- | :--- | :--- |
| `login_attempts` | `created_at < 7 days ago` | 7 days |
| `password_resets` | `expires_at < 7 days ago` | 7 days past expiry |
| `notifications` | `read_at IS NOT NULL AND created_at < 180 days ago` | 180 days after read |

---

## 4. Database Architecture

### 4.1 Supported Engines

| Environment | Engine | Connection String |
| :--- | :--- | :--- |
| Local / Dev | SQLite | `sqlite:///retention.db` |
| Production | MySQL 8.0+ | `mysql+pymysql://user:pass@host:3306/SafeData_production` |
| Production | PostgreSQL 14+ | `postgresql://user:pass@host:5432/SafeData_production` |

### 4.2 Schema Management

SafeData uses a dual approach to schema management:

1. **Alembic Migrations**: Standard migration framework configured in `alembic.ini`. Run `alembic upgrade head` to apply pending migrations.
2. **Auto-Schema Patching**: The `ensure_schema_columns()` function in `main.py` runs on startup and adds missing columns to existing tables (e.g., `trial_ends_at`, `follow_up_sent_at`, `role_type`). This handles live deployments where Alembic migrations may lag behind code changes.

### 4.3 Session & Connection Management

```python
# app/database.py
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- For SQLite: `check_same_thread = False` is set to support multi-threaded access.
- All route handlers receive a database session via FastAPI's `Depends(get_db)`.

---

## 5. Application Dependencies

All dependencies are specified in `requirements.txt`:

| Package | Purpose |
| :--- | :--- |
| `fastapi>=0.100.0` | ASGI web framework with OpenAPI/Pydantic validation |
| `uvicorn>=0.22.0` | ASGI server for running FastAPI |
| `sqlalchemy>=2.0.0` | ORM for declarative database models |
| `jinja2>=3.1.0` | HTML template engine for web UI |
| `pytest>=7.0.0` | Automated test framework |
| `httpx>=0.24.0` | Async HTTP client for outbound webhook dispatch |
| `passlib[bcrypt]>=1.7.4` | Bcrypt password hashing (used via raw `bcrypt` module) |
| `itsdangerous>=2.1.0` | Signed cookie session serialization (`URLSafeSerializer`) |
| `python-multipart>=0.0.6` | Multipart form data parsing (file uploads) |
| `pymysql>=1.0.0` | Pure-Python MySQL driver for production |
| `cryptography>=41.0.0` | Cryptographic primitives (PyMySQL SSL, token generation) |
| `alembic>=1.12.0` | Database schema migration framework |

> **Note**: While `passlib[bcrypt]` is listed in `requirements.txt`, the application's `auth.py` module uses the raw `bcrypt` library directly (`bcrypt.hashpw()`, `bcrypt.checkpw()`) rather than Passlib's wrapper classes.

---

## 6. Environment Variables Reference

| Variable | Default | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `local` | Environment mode: `production`, `local`, or `test` |
| `APP_NAME` | `SafeData — 3Consulting Python` | Application display name |
| `APP_URL` | `http://127.0.0.1:8200` | Base URL for generated links |
| `SECRET_KEY` | *(dev default)* | Session signing key (must be random in production) |
| `DATABASE_URL` | `sqlite:///retention.db` | SQLAlchemy connection string |
| `ALLOWED_HOSTS` | `*` | Comma-separated allowed hostnames (restrict in production) |
| `TRUSTED_PROXIES` | *(empty)* | Comma-separated proxy IPs for `X-Forwarded-For` |

### Security Constants (app/config.py)

| Constant | Value | Description |
| :--- | :--- | :--- |
| `SESSION_IDLE_TIMEOUT` | `1800` (30 min) | Idle timeout before session expiry |
| `SESSION_ABSOLUTE_TIMEOUT` | `28800` (8 hr) | Maximum session lifespan |
| `CSRF_TOKEN_LENGTH` | `32` bytes (64 hex chars) | CSRF token size |
| `LOGIN_MAX_ATTEMPTS` | `5` | Failed login attempts before lockout |
| `LOGIN_WINDOW_MINUTES` | `15` | Lockout rolling window |
| `PASSWORD_MIN_LENGTH` | `10` | Minimum password length |
| `COOKIE_SECURE` | `True` in production | HTTPS-only session cookies |
| `COOKIE_SAMESITE` | `lax` | SameSite cookie attribute |

---

## 7. Local Development Setup

### 7.1 Prerequisites
- Python 3.10+
- Git

### 7.2 Quick Launch (Windows PowerShell)
```powershell
cd retention_py
.\dev-start.ps1
```
This script checks dependencies, auto-installs missing packages from `requirements.txt`, determines your local LAN IP address, sets `$env:APP_ENV = "local"`, and launches Uvicorn on `http://localhost:8200`.

### 7.3 Manual Launch (Cross-Platform)
```bash
cd retention_py
pip install -r requirements.txt
python main.py
```

The application starts on **port 8200** (`uvicorn main:app --host 0.0.0.0 --port 8200 --reload`).

---

## 8. Production Deployment Guide

### 8.1 Server Requirements
- Linux VM (Ubuntu 22.04 LTS or 24.04 LTS recommended)
- 2 CPU Cores, 4 GB RAM, 40 GB SSD
- MySQL 8.0+ or PostgreSQL 14+ database instance

### 8.2 Environment Configuration
Create a `.env` file in `retention_py/` or export environment variables:

```bash
APP_ENV=production
APP_NAME="SafeData — 3Consulting"
APP_URL=https://retention.3consult-ng.com
SECRET_KEY="GENERATE_VERY_LONG_RANDOM_SECRET_KEY_HERE"
DATABASE_URL="mysql+pymysql://SafeData_prod_user:SecurePass123!@localhost:3306/SafeData_production"
ALLOWED_HOSTS="retention.3consult-ng.com"
```

### 8.3 Database Migration Execution
```bash
cd retention_py
alembic upgrade head
```

### 8.4 Database Security Hardening (REVOKE UPDATE/DELETE)
To guarantee compliance immutability for regulatory audits, revoke edit privileges on the `audit_log` table for the operational database user:

```sql
-- MySQL / MariaDB
REVOKE UPDATE, DELETE ON SafeData_production.audit_log FROM 'SafeData_prod_user'@'localhost';
FLUSH PRIVILEGES;

-- PostgreSQL
REVOKE UPDATE, DELETE ON TABLE audit_log FROM SafeData_prod_user;
```

### 8.5 Systemd Service Configuration
Create `/etc/systemd/system/SafeData.service`:

```ini
[Unit]
Description=SafeData FastAPI Application
After=network.target mysql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/SafeData/retention_py
EnvironmentFile=/var/www/SafeData/retention_py/.env
ExecStart=/var/www/SafeData/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8200 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable SafeData
sudo systemctl start SafeData
```

### 8.6 Nginx Reverse Proxy & SSL Setup
Create `/etc/nginx/sites-available/SafeData`:

```nginx
server {
    listen 80;
    server_name retention.3consult-ng.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name retention.3consult-ng.com;

    ssl_certificate /etc/letsencrypt/live/retention.3consult-ng.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/retention.3consult-ng.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8200;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/SafeData/retention_py/app/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }
}
```

Activate Nginx site:
```bash
sudo ln -s /etc/nginx/sites-available/SafeData /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 9. Backup & Recovery

### 9.1 Automated Backups
The `backup_scheduler_task()` runs every 24 hours and calls `backup_database()` from `app/backups.py`:

- **SQLite**: Uses Python's built-in `sqlite3.iterdump()` for a complete SQL dump.
- **MySQL**: Table-by-table `SELECT` + `INSERT` dump matching the legacy approach.
- **Output**: `storage/backups/SafeData_backup_{YYYYMMDD_HHMMSS}.sql`
- **Pruning**: Backup files older than 30 days are automatically deleted.
- **Logging**: Every backup (success or failure) is recorded in the `backup_log` table.

### 9.2 Manual Backup
Trigger a backup from the Platform Admin dashboard or call `backup_database()` directly:

```python
from app.backups import backup_database
from app.database import SessionLocal
from app.config import BACKUP_PATH

db = SessionLocal()
result = backup_database(db, BACKUP_PATH)
print(result)  # {'file': '...', 'size': 12345, 'status': 'success', 'message': None}
```

### 9.3 Recovery
Restore from a SQL dump:
```bash
# SQLite
sqlite3 retention.db < storage/backups/SafeData_backup_20260817_020000.sql

# MySQL
mysql -u SafeData_prod_user -p SafeData_production < storage/backups/SafeData_backup_20260817_020000.sql
```
