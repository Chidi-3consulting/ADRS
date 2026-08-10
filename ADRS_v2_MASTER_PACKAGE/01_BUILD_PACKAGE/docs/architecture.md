# 3Consulting Data Retention System — Architecture & Deployment Guide

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                  Deployment Server                       │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  Browser UI  │    │  APScheduler │                   │
│  │ (Bootstrap5) │    │  (Background │                   │
│  │   + Jinja2   │    │   Tasks)     │                   │
│  └──────┬───────┘    └──────┬───────┘                   │
│         │                   │                            │
│         ▼                   ▼                            │
│  ┌──────────────────────────────────────┐               │
│  │     FastAPI + Uvicorn (Python)      │               │
│  │                                      │               │
│  │  routes/     engine.py   app/       │               │
│  │  ├ public     retention   ├ config  │               │
│  │  ├ dashboard  engine      ├ auth    │               │
│  │  ├ categories enterprise  ├ helpers │               │
│  │  ├ records    backups     ├ models  │               │
│  │  ├ app_pages              └ middle  │               │
│  │  └ api_v1                  ware     │               │
│  └──────────────────┬───────────────────┘               │
│                     │                                    │
│         ┌───────────▼────────────┐                      │
│         │  SQLAlchemy ORM        │                      │
│         │  ┌─────────────────┐  │                      │
│         │  │ SQLite (dev)    │  │                      │
│         │  │ MySQL (prod)    │  │                      │
│         │  │                 │  │                      │
│         │  │ organizations   │  │                      │
│         │  │ users           │  │                      │
│         │  │ data_categories │  │                      │
│         │  │ data_records    │  │                      │
│         │  │ audit_log       │  │                      │
│         │  │ notifications   │  │                      │
│         │  │ system_settings │  │                      │
│         │  └─────────────────┘  │                      │
│         └────────────────────────┘                      │
│                                                          │
│  ┌─────────────────────────────────────┐                │
│  │     SMTP (smtplib)                  │                │
│  │     Mailer → Notification emails    │                │
│  └─────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────┘
```

---

## Local Development Setup

### Prerequisites
- Python 3.10 or later
- pip (Python package manager)

### Step 1: Install dependencies
```bash
cd retention_py
pip install -r requirements.txt
```

### Step 2: Start the development server
```powershell
# Windows (PowerShell) — auto-detects LAN IP, runs on port 8200
.\dev-start.ps1

# Or directly:
python main.py
```

The application uses SQLite by default for local development (`retention.db`).

### Step 3: Register your organisation
Navigate to `http://localhost:8200/register` and create your first organisation.
Default seeded credentials (if using seed data): `admin@3consult-ng.com` / `password`.

---

## Production Deployment

### Step 1: Provision the server
Any Linux/Windows server with Python 3.10+ and pip. Examples:
- Ubuntu VPS (DigitalOcean, AWS, Azure)
- Docker container
- PaaS (Railway, Render, Fly.io)

### Step 2: Install dependencies
```bash
cd retention_py
pip install -r requirements.txt
```

### Step 3: Configure environment variables
Set the following environment variables (or use a `.env` file):

```bash
APP_ENV=production
APP_URL=https://retention.3consult-ng.com
SECRET_KEY=your_strong_random_secret_key_here
DATABASE_URL=mysql+pymysql://user:pass@host:3306/adrs_db
ALLOWED_HOSTS=retention.3consult-ng.com
```

### Step 4: Run database migrations
```bash
alembic upgrade head
```

### Step 5: Start the application
```bash
# Production — use a process manager (systemd, supervisor, or Docker)
uvicorn main:app --host 0.0.0.0 --port 8200 --workers 4
```

For MySQL production, restrict the audit_log table:
```sql
REVOKE UPDATE, DELETE ON adrs_db.audit_log FROM 'adrs_user'@'%';
```

### Step 6: Reverse proxy (recommended)
Put Nginx or Caddy in front of Uvicorn for TLS termination:

```nginx
server {
    listen 443 ssl;
    server_name retention.3consult-ng.com;

    location / {
        proxy_pass http://127.0.0.1:8200;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Step 7: First login
- URL: `https://retention.3consult-ng.com/`
- Register a new organisation, or use seeded credentials
- Go to Settings → Configure SMTP email
- **Change default passwords immediately**

---

## Security Checklist (post-deployment)

- [ ] Changed default admin password
- [ ] Configured SMTP with a real email account
- [ ] Set `APP_ENV=production` in environment
- [ ] Set a strong, random `SECRET_KEY`
- [ ] Confirmed background tasks are running (check logs)
- [ ] Revoked UPDATE/DELETE on `audit_log` table for app DB user
- [ ] SSL certificate active on domain (HTTPS enforced)
- [ ] Logs directory is outside public web root
- [ ] `DATABASE_URL` uses MySQL/PostgreSQL (not SQLite) in production

---

## Maintenance

| Task | Frequency | How |
|---|---|---|
| Check application logs | Weekly | View `storage/logs/` directory |
| Review audit log | Monthly | Dashboard → Audit Log |
| Quarterly retention review | Every 3 months | Triggered automatically by scheduler |
| Export NDPR Annual Report | Annually (January) | Audit Log → Export NDPR Annual Report |
| Update retention periods | As regulations change | Categories → Edit |
| Backup database | Daily (automated) | Runs via APScheduler at 02:00 AM |
| Apply migrations | On updates | `alembic upgrade head` |
