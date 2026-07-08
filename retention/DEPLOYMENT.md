# ADRS — Deployment & Go-Live Runbook

Automated Data Retention System (3Consulting). PHP 8.2+ / MySQL 8.0, no framework, no
Composer. Target: cPanel shared hosting (also runs on any LAMP host). This runbook covers a
**fresh install** and an **upgrade** of an existing install.

> Quick facts: app lives under `retention/`. Front controller: `retention/index.php`.
> Tests: `cd retention && php tests/run.php` (227 assertions). Default login after seeding:
> `admin@3consult-ng.com` / `password` — **change immediately**.

---

## 1. Requirements

- PHP **8.2+** with extensions: `pdo_mysql`, `mbstring`, `openssl`, `curl`, `fileinfo`.
- MySQL **8.0** (or MariaDB 10.5+).
- Ability to set **cron jobs** and to place files **outside** `public_html` (for logs,
  uploads, backups).
- HTTPS (SSL) on the domain/subdomain.

---

## 2. Fresh install

### 2.1 Upload
Upload the `retention/` directory into the web root, e.g.
`/home/USER/public_html/retention/` (or map a subdomain `retention.example.com` to it).

### 2.2 Create the database (cPanel → MySQL Databases)
1. Create DB `USER_adrs` and user `USER_adrsapp` with a strong password.
2. Grant the user **ALL PRIVILEGES** on the DB (you'll tighten `audit_log` in step 5).

### 2.3 Import schema (phpMyAdmin → Import)
1. Import `retention/sql/schema.sql` — creates all tables, multi-tenant `organizations`
   structure, and platform settings (`deployment_mode=saas` by default).

**SaaS go-live (recommended for selling ADRS):** stop here. Publish the site — visitors see
the product landing page, choose **Core** or **Enterprise**, and **register** their
organisation at `/register` (14-day trial, isolated tenant, 30-category library auto-provisioned).

**Private single-tenant install:** set `deployment_mode` to `single` in `system_settings`
(or import the seed below which does this). Use `/setup` for the one-time admin wizard.

**Dev / demo shortcut:** also import `retention/sql/seed_gdpr_ndpr.sql` — pre-loads categories
and seeded users `admin@3consult-ng.com` / `dpo@3consult-ng.com` (password `password`, forced
change on first login; switches to single-tenant mode).

> Because `schema.sql` already contains the Phase-3 tables and column additions, a **fresh**
> install does **not** need migration files in `sql/migrations/`. Upgrades do — see §6.

### 2.4 Configuration — create `retention/src/config/config.local.php`
This file is gitignored. It pre-defines constants the app reads (DB, URLs, paths):

```php
<?php
define('APP_ENV', 'production');
define('APP_URL', 'https://retention.example.com');   // no trailing slash; subdir: https://example.com/retention
define('DB_HOST', '127.0.0.1');
define('DB_PORT', '3306');
define('DB_NAME', 'USER_adrs');
define('DB_USER', 'USER_adrsapp');
define('DB_PASS', 'your-strong-password');
define('UPLOAD_PATH', '/home/USER/adrs_storage/attachments/'); // OUTSIDE public_html
define('LOG_PATH',    '/home/USER/adrs_storage/logs/');        // OUTSIDE public_html
```
Create those storage dirs (and `/home/USER/adrs_storage/backups/`), writable by PHP.

SMTP is **not** set here — it lives in the database (System Settings page) after first login.

### 2.5 `.htaccess`
`retention/.htaccess` ships configured for a subdirectory (`RewriteBase /retention/`) and
already routes `/api/v1/*` to the Enterprise API and everything else to `index.php`. If you
deploy at a **subdomain root**, change `RewriteBase /retention/` to `RewriteBase /`.

### 2.6 First visit & hardening

**Production path (schema only):**
1. Visit the site → public **landing page** with product overview.
2. You are redirected to **`/setup`** — enter organisation name, admin name/email, and a strong password.
3. Optionally tick **Import the 30-category GDPR/NDPR library** (recommended).
4. You land on the dashboard as the new administrator.

**Dev shortcut (schema + seed):**
1. Visit the site → **Sign in** with `admin@3consult-ng.com` / `password`.
2. You are forced to **My profile** to set a new password before continuing.

**Then (all installs):**
1. System Settings → configure **SMTP** (host, port, username, password, from address).
2. (Optional) Settings → **white-label** (name, primary colour, logo URL, footer).
3. (Optional) Settings → set `allow_public_signup` to `1` if you want a public **Create account** page (off by default; new users get the Data Owner role).
4. (Optional, recommended) Settings → **Two-Factor Auth** → enable TOTP for admins.
5. Add team members under **Users** (admin-managed; temporary passwords require change on first login).

---

## 3. Cron jobs (cPanel → Cron Jobs)

Use the absolute PHP CLI path (find it with `which php`, often `/usr/local/bin/php`).
ADRS Core needs the first two; **Enterprise** adds the next two; backups is recommended for all.

```cron
# Core — daily retention engine (01:00)
0 1 * * * /usr/local/bin/php /home/USER/public_html/retention/src/engine/retention_cron.php >> /home/USER/adrs_storage/logs/retention_cron.log 2>&1

# Core — quarterly review email (08:00 on 1 Jan/Apr/Jul/Oct)
0 8 1 1,4,7,10 * /usr/local/bin/php /home/USER/public_html/retention/src/engine/retention_cron.php --task=quarterly_review >> /home/USER/adrs_storage/logs/quarterly.log 2>&1

# Enterprise — intake queue processor (every 5 minutes)
*/5 * * * * /usr/local/bin/php /home/USER/public_html/retention/src/engine/intake_queue_processor.php >> /home/USER/adrs_storage/logs/intake.log 2>&1

# Enterprise — outbound disposal dispatch (every 10 minutes)
*/10 * * * * /usr/local/bin/php /home/USER/public_html/retention/src/engine/disposal_dispatch_cron.php >> /home/USER/adrs_storage/logs/dispatch.log 2>&1

# All tiers — automated DB backup (daily 03:00)
0 3 * * * /usr/local/bin/php /home/USER/public_html/retention/src/engine/backup_cron.php >> /home/USER/adrs_storage/logs/backup.log 2>&1
```

The Enterprise crons self-skip when `adrs_tier` is `core`, so they're harmless to install early.

---

## 4. Enabling the Enterprise tier (optional)

1. Settings → **Tier & Licence** → enter the licence key → activates `adrs_tier=enterprise`
   and the REST API. (Downgrade is intentionally not offered — protects cross-system data.)
2. **Integrations** appears in the sidebar: register connected systems, create API keys
   (raw key shown **once**), define auto-categorisation rules and field mappings.
3. External systems call `https://your-host/retention/api/v1/...` with header
   `X-API-Key: adrs_xx…`. Endpoints: `GET /health`, `GET /categories`, `POST /ingest`,
   `POST /ingest/batch`, `POST /consent/withdraw`, `GET /records/{ref}/status`.
4. For outbound disposal dispatch, set each connected system's **Base URL**; ADRS POSTs
   disposal instructions to `{base_url}/adrs/disposal`.

---

## 5. Security hardening (do all of these)

- [ ] Changed the default admin password; created real users; removed/disabled demo accounts.
- [ ] SMTP configured and a test email sent (Settings).
- [ ] **Audit log made append-only at the DB level** (defence-in-depth on top of the hash
      chain). In phpMyAdmin run as the DB **owner/root**:
      ```sql
      REVOKE UPDATE, DELETE ON USER_adrs.audit_log FROM 'USER_adrsapp'@'localhost';
      ```
      ADRS never updates/deletes audit rows; the app-level hash chain detects tampering, and
      this REVOKE prevents it via the app credentials entirely.
- [ ] `config.local.php` present and **not** world-readable; secrets only there (never in git).
- [ ] `UPLOAD_PATH`, `LOG_PATH`, backups dir are **outside** `public_html`.
- [ ] HTTPS enforced; `APP_ENV=production` (hides verbose errors).
- [ ] 2FA enabled for Administrator accounts.
- [ ] Confirm `https://your-host/retention/src/config/config.local.php` is **not** directly
      fetchable (the `.htaccess` blocks `config`/`includes`/`engine`/`sql`).
- [ ] After a few days, verify cron logs show activity and Audit Log → **Verify integrity**
      reports the chain intact.

---

## 6. Upgrading an existing install

1. **Back up first**: run `php src/engine/backup_cron.php` (or export via phpMyAdmin).
2. Replace the application files (keep your `config.local.php`).
3. Apply any **additive migrations** that post-date your install, in order, from
   `retention/sql/migrations/`. Run each once:
   ```
   mysql -u USER_adrsapp -p USER_adrs < retention/sql/migrations/2026-06-04-phase3-advanced.sql
   mysql -u USER_adrsapp -p USER_adrs < retention/sql/migrations/2026-06-06-hardening.sql
   ```
   - `2026-06-04-phase3-advanced.sql` — `audit_log` hash columns, `users` 2FA columns, and the
     webhook/backup tables + settings.
   - `2026-06-06-hardening.sql` — the `login_attempts` table (brute-force throttle) and a
     performance index on `data_records.record_reference`.

   Tables use `IF NOT EXISTS`; run the `ALTER`s only once.
4. Re-apply the `audit_log` REVOKE if you recreated the user.
5. Smoke test: log in, open the dashboard, run `php tests/run.php` against a **test** DB.

---

## 7. Operations

| Task | How |
|---|---|
| Verify audit integrity | Audit Log → **Verify integrity** (or Settings link) |
| Export NDPR annual report | Audit Log → **NDPR Annual Report** |
| Management/board report | **Analytics & Reports** → Export CSV / Print |
| Restore a backup | Import the latest `adrs_storage/backups/adrs_backup_*.sql` via phpMyAdmin |
| Check engine health | Tail `adrs_storage/logs/retention_cron.log` |

---

## 8. Deferred (not in this build)

- **SSO / SAML** — bolt-on per enterprise customer; no rework required.
- **Multi-tenant / multi-organisation** — current model is one install per organisation
  (white-label per deployment).
