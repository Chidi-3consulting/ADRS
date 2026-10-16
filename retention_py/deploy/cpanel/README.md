# SafeData on cPanel shared hosting (InMotion)

The same FastAPI app that runs on Render, hosted by cPanel's **Setup Python App**
(Phusion Passenger). Nothing is cut down: landing site, sign-up, dashboard, retention
engine, DSAR, RoPA, DPIA, breach register, audit ledger, API and integrations.

| Piece | Render | cPanel |
|---|---|---|
| Web | gunicorn + uvicorn | Passenger → `passenger_wsgi.py` (a2wsgi bridge) |
| Database | Render PostgreSQL | cPanel **PostgreSQL Databases** |
| Files | S3 / R2 | local disk outside the web root (`STORAGE_LOCAL_PERSISTENT=1`) |
| Worker | `python -m app.worker` service | cron every 5 min → `deploy/cpanel/cron.sh` (`--once`) |
| Migrations | `preDeployCommand` | automatic on app start (`SAFEDATA_AUTO_MIGRATE=1`) |

Python 3.10 or newer (3.11/3.12 recommended).

## Steps

1. **Empty the subdomain folder.** File Manager → `safedata.3consult-ng.com` →
   delete everything except `cgi-bin` and `.well-known` (the old PHP build).
2. **PostgreSQL.** cPanel → PostgreSQL Databases: create database `safedata`,
   user `sdapp` (generated password), add the user to the database with ALL privileges.
3. **Upload the app.** File Manager → Home → create `safedata_app` → upload the release zip
   → Extract. `passenger_wsgi.py` must sit directly in `/home/USER/safedata_app/`.
   Create `/home/USER/safedata_storage/logs`.
4. **Settings.** Copy `deploy/cpanel/env.example` to `/home/USER/safedata_app/.env`,
   fill it in, set permissions to `600`.
5. **Create the Python app.** cPanel → Setup Python App → Create Application:
   - Python version: newest available (3.11+)
   - Application root: `safedata_app`
   - Application URL: `safedata.3consult-ng.com`
   - Application startup file: `passenger_wsgi.py`
   - Application Entry point: `application`
   Create → under *Configuration files* add `requirements-cpanel.txt` → **Run Pip Install**
   → **Restart**.
6. **Cron.** cPanel → Cron Jobs → every 5 minutes:
   `/bin/bash /home/USER/safedata_app/deploy/cpanel/cron.sh >> /home/USER/safedata_storage/logs/cron.log 2>&1`
7. Open `https://safedata.3consult-ng.com`, start a trial with an email on your
   organisation's domain, and verify the email.

## Updating

Upload the new release over `safedata_app` (keep `.env`), then **Restart** in Setup
Python App. Migrations run on restart.
