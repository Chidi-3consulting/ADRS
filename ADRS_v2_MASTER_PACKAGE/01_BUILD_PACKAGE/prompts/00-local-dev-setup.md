# Prompt 00 — Local Development Environment Setup v4 (BUG-07/09 FIXED)

## Pre-requisites: Windows PC, nothing installed yet.

---

## Step 1 — Install Laragon Full
1. Download from **https://laragon.org/download/** (Laragon Full — includes PHP + MySQL)
2. Install to `C:\laragon\` (keep default path)
3. Start Laragon → tray icon → **Start All**
4. Verify: browser → `http://localhost` → Laragon welcome page

---

## Step 2 — Set PHP to 8.2
1. Laragon tray → **PHP → Version** → select `php-8.2.x`
2. If not listed: download PHP 8.2 Win64 NTS from https://windows.php.net/downloads/releases/
   → extract to `C:\laragon\bin\php\php-8.2.x\` → switch in Laragon
3. Restart Laragon (Stop All → Start All)
4. Verify: open CMD → `php -v` → shows PHP 8.2.x

---

## Step 3 — Place the project
Create folder: `C:\laragon\www\data-retention\`
Copy the entire project into it.
App accessible at: `http://localhost/data-retention/`

---

## Step 4 — Create the local database
1. Laragon tray → **Database** → HeidiSQL
2. Session: Host=`127.0.0.1`, User=`root`, Password=*(blank)*, Port=`3306` → Open
3. Right-click → New Database → name: `data_retention_local`, Collation: `utf8mb4_unicode_ci`
4. Select database → File → Run SQL file → `sql/schema.sql`
5. Run again → `sql/seed_gdpr_ndpr.sql`
6. Verify: run the verification query at the bottom of seed_gdpr_ndpr.sql

---

## Step 5 — Install Mailpit (local email catcher)
1. Download from https://github.com/axllent/mailpit/releases/latest
   → `mailpit-windows-amd64.zip` → extract `mailpit.exe` to `C:\laragon\bin\mailpit\`
2. Start: open CMD in that folder → `mailpit.exe`
3. Mailpit runs on SMTP: `localhost:1025` | Web inbox: `http://localhost:8025`

To auto-start with Laragon: create `C:\laragon\etc\apps\mailpit.conf`:
```
[program:mailpit]
command=C:\laragon\bin\mailpit\mailpit.exe
autostart=true
autorestart=true
```

---

## Step 6 — Create config.local.php (gitignored)
Create `src/config/config.local.php`:
```php
<?php
// LOCAL DEV ONLY — gitignored, never deployed
define('DB_HOST',     'localhost');
define('DB_PORT',     '3306');
define('DB_NAME',     'data_retention_local');
define('DB_USER',     'root');
define('DB_PASS',     '');
define('DB_CHARSET',  'utf8mb4');
define('APP_NAME',    '3Consulting DRS [LOCAL]');
define('APP_URL',     'http://localhost/data-retention');
define('APP_ENV',     'local');
define('TIMEZONE',    'Africa/Lagos');
define('SESSION_NAME','3c_drs_local');
define('CSRF_TOKEN_LENGTH', 64);
define('UPLOAD_PATH', 'C:\\laragon\\retention_uploads\\');
define('LOG_PATH',    'C:\\laragon\\logs\\');
define('SHOW_ERRORS', true);
define('DEBUG_SQL',   false);
```

Also create the upload and log directories:
```
C:\laragon\retention_uploads\   (create manually)
C:\laragon\logs\                (create manually)
```

---

## Step 7 — BUG-07/09 FIX: Two .htaccess files strategy

The production `.htaccess` uses `RewriteBase /` (subdomain root).
Local dev needs `RewriteBase /data-retention/`.
**These two values conflict — you need different files per environment.**

**Solution: Two files, one gitignored.**

**`.htaccess`** (committed to Git — for production):
```apache
Options -Indexes
DirectoryIndex index.php

<FilesMatch "\.(sql|log|md|env|json|lock|local)$">
    Require all denied
</FilesMatch>

<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteBase /

    # Force HTTPS on production
    RewriteCond %{HTTPS} off
    RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]

    # Route through front controller
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^(.*)$ index.php [QSA,L]
</IfModule>

<IfModule mod_headers.c>
    Header always set X-Frame-Options "DENY"
    Header always set X-Content-Type-Options "nosniff"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
    Header always set X-XSS-Protection "1; mode=block"
</IfModule>

<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/html text/css application/javascript
</IfModule>

# Block sensitive directories
<IfModule mod_authz_core.c>
    <DirectoryMatch "/(config|includes|engine|sql|logs|api)/">
        Require all denied
    </DirectoryMatch>
</IfModule>
```

**`.htaccess.local`** (in .gitignore — developer copies to .htaccess locally):
```apache
Options -Indexes
DirectoryIndex index.php

<FilesMatch "\.(sql|log|md|env|json|lock|local)$">
    Require all denied
</FilesMatch>

<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteBase /data-retention/

    # NO HTTPS redirect on localhost

    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^(.*)$ index.php [QSA,L]
</IfModule>

<IfModule mod_headers.c>
    Header always set X-Frame-Options "DENY"
    Header always set X-Content-Type-Options "nosniff"
</IfModule>
```

**Developer setup instructions:**
```bash
# After cloning the repo, copy the local htaccess:
copy .htaccess.local .htaccess
# (This overwrites the production one locally — that's intentional)
# Never git commit .htaccess after this point (add to .gitignore or use:)
git update-index --assume-unchanged .htaccess
```

Add to `.gitignore`:
```
.htaccess.local
src/config/config.local.php
```

---

## Step 8 — Update system_settings for local Mailpit SMTP
After logging in locally at http://localhost/data-retention/,
navigate to Settings → and set:
- SMTP Host: `localhost`
- SMTP Port: `1025`
- SMTP Username: *(leave blank)*
- SMTP Password: *(leave blank)*
- SMTP Encryption: *(leave blank)*

Or run this SQL directly in HeidiSQL:
```sql
UPDATE system_settings SET setting_value = 'localhost'  WHERE setting_key = 'smtp_host';
UPDATE system_settings SET setting_value = '1025'       WHERE setting_key = 'smtp_port';
UPDATE system_settings SET setting_value = ''           WHERE setting_key = 'smtp_user';
UPDATE system_settings SET setting_value = ''           WHERE setting_key = 'smtp_pass';
UPDATE system_settings SET setting_value = ''           WHERE setting_key = 'smtp_encryption';
```

---

## Step 9 — Create log files
Open CMD:
```cmd
echo. > C:\laragon\logs\retention_cron.log
echo. > C:\laragon\logs\cron_errors.log
echo. > C:\laragon\logs\mail_errors.log
echo. > C:\laragon\logs\db_error.log
```

---

## Step 10 — Verify everything works
1. Browser → `http://localhost/data-retention/` → login page appears
2. Login: `admin@3consult-ng.com` / `password`
3. Test forgot password: logout → Forgot Password → enter admin email
4. Open `http://localhost:8025` → reset email should appear in Mailpit
5. Test cron manually: CMD → `cd C:\laragon\www\data-retention` → `php src\engine\retention_cron.php`
6. Check `C:\laragon\logs\retention_cron.log` → should show "=== Engine COMPLETE ==="

---

## Local → Production Checklist
| Item | Action |
|---|---|
| `.htaccess` | Restore production version: `git checkout .htaccess` |
| `config.local.php` | Must NOT be on server |
| `database.php` | Fill in production DB credentials + APP_URL + UPLOAD_PATH + LOG_PATH |
| SMTP settings | Configure via Settings page after deploy |
| cPanel cron | Add daily + quarterly cron jobs |
| File permissions | `/home/username/retention_uploads/` chmod 750 |

---

## Troubleshooting
| Problem | Fix |
|---|---|
| 404 at http://localhost/data-retention/ | .htaccess.local not copied to .htaccess locally |
| "RewriteBase / does not work" on local | You're using the production .htaccess — copy .htaccess.local |
| Emails not in Mailpit inbox | Mailpit not running / SMTP port not 1025 in system_settings |
| DB connection error | Check config.local.php DB_NAME matches HeidiSQL database |
| CSRF errors after any save | Clear cookies and try again |
| Cron shows no output | Run: `php src\engine\retention_cron.php` in CMD from project root |

---

## Enterprise Local Development Additions

### Testing the Enterprise API with Mailpit and curl

After completing Steps 1–10, if deploying Enterprise tier:

**Step 11 — Activate Enterprise tier locally:**
In HeidiSQL, run:
```sql
UPDATE system_settings SET setting_value = 'enterprise' WHERE setting_key = 'adrs_tier';
UPDATE system_settings SET setting_value = '1' WHERE setting_key = 'enterprise_api_enabled';
```

**Step 12 — Register a test connected system:**
Login → Integrations → Add Connected System → "Local Test System"

**Step 13 — Create an API key:**
Integrations → [System] → API Keys → Create → copy the raw key

**Step 14 — Test the API from terminal:**
```powershell
# Health check
curl -X GET "http://localhost/data-retention/api/v1/health" `
  -H "X-API-Key: YOUR_KEY_HERE"

# Send a test record
curl -X POST "http://localhost/data-retention/api/v1/ingest" `
  -H "X-API-Key: YOUR_KEY_HERE" `
  -H "Content-Type: application/json" `
  -d '{"object_type":"customer_kyc","external_ref":"TEST-001","collection_date":"2025-08-01"}'
```

**Step 15 — Add intake queue cron locally (Task Scheduler):**
- Program: `C:\laragon\bin\php\php-8.2.x\php.exe`
- Arguments: `C:\laragon\www\data-retention\src\engine\intake_queue_processor.php`
- Trigger: Every 5 minutes
- Or run manually: `php src\engine\intake_queue_processor.php`

**Step 16 — Add disposal dispatch cron locally:**
- Same setup, points to `disposal_dispatch_cron.php`
- Run manually: `php src\engine\disposal_dispatch_cron.php`

### Local .htaccess: Add API route

In `.htaccess.local`, add BEFORE the main RewriteRule:
```apache
# Enterprise API routing (local)
RewriteRule ^data-retention/api/v1/(.*)$ data-retention/src/api/v1/router.php?_route=$1 [QSA,L]
```

### Enterprise Troubleshooting

| Problem | Fix |
|---------|-----|
| API returns 403 "enterprise_tier_required" | Run Step 11 SQL above |
| API returns 401 "invalid_api_key" | Key was not copied correctly — create a new one |
| Intake queue items stay "pending" | Run intake_queue_processor.php manually |
| Disposal dispatch stays "pending" | Run disposal_dispatch_cron.php manually |
| Consent signal stays "unmatched" | No data_record with that external_ref exists yet |
