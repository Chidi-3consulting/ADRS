# Prompt 00 — Local Development Environment Setup (Python)

## Pre-requisites: Windows PC, Python installed.

---

## Step 1 — Install Python

1. Download Python 3.10+ from **https://www.python.org/downloads/**
2. During install, check **"Add Python to PATH"**
3. Verify: open PowerShell → `python --version` → shows Python 3.10+

---

## Step 2 — Clone the project

```powershell
cd C:\Users\YourName\Documents
git clone <repository-url>
cd ADRS
```

---

## Step 3 — Install dependencies

```powershell
cd retention_py
pip install -r requirements.txt
```

---

## Step 4 — Start the development server

```powershell
.\dev-start.ps1
```

Or directly:
```powershell
python main.py
```

The app runs on **http://localhost:8200/** by default.

---

## Step 5 — First-time setup

1. Navigate to `http://localhost:8200/register`
2. Create your organisation (name, domain, admin email, password)
3. Log in with the credentials you just created

**Or**, if using the seeded demo database:
- Admin: `admin@3consult-ng.com` / `password`
- DPO: `dpo@3consult-ng.com` / `password`

---

## Step 6 — Database

The app uses **SQLite** by default for local development (`retention.db` file).

To use MySQL instead (optional):
```powershell
$env:DATABASE_URL = "mysql+pymysql://adrs_user:adrs_pass@localhost:3306/adrs_db"
python main.py
```

---

## Step 7 — Run tests

```powershell
cd retention_py
python -m pytest tests/ -v
```

---

## Step 8 — Email testing (optional)

For local email testing, install **Mailpit** (or similar):

1. Download from https://github.com/axllent/mailpit/releases
2. Run: `mailpit.exe`
3. Mailpit UI: `http://localhost:8025/`
4. Configure SMTP in ADRS Settings:
   - SMTP Host: `localhost`
   - SMTP Port: `1025`
   - Encryption: (none)

---

## Step 9 — Enterprise API testing (after activating Enterprise tier)

```bash
# Health check
curl -X GET "http://localhost:8200/api/v1/health" \
     -H "X-API-Key: adrs_YOUR_KEY_HERE"

# Ingest a record
curl -X POST "http://localhost:8200/api/v1/ingest" \
     -H "X-API-Key: adrs_YOUR_KEY_HERE" \
     -H "Content-Type: application/json" \
     -d '{"object_type":"customer","external_ref":"CUST-001","data":{"name":"Test Customer"}}'
```

---

## Project structure

```
retention_py/
├── main.py               ← FastAPI entry point (start here)
├── requirements.txt      ← Python dependencies
├── dev-start.ps1         ← PowerShell dev startup script
├── alembic.ini           ← Database migration config
├── alembic/              ← Migration files
├── app/
│   ├── config.py         ← Environment configuration
│   ├── database.py       ← SQLAlchemy engine + session
│   ├── models.py         ← ORM models
│   ├── auth.py           ← Authentication
│   ├── helpers.py        ← Utility functions
│   ├── engine.py         ← Retention engine
│   ├── enterprise.py     ← Enterprise features
│   ├── middleware.py      ← Security middleware
│   ├── backups.py        ← Backup utilities
│   ├── routes/           ← Route blueprints
│   ├── static/           ← CSS, JS, images
│   └── templates/        ← Jinja2 templates
├── tests/                ← Pytest test suite
└── storage/              ← Attachments, logs, backups
```
