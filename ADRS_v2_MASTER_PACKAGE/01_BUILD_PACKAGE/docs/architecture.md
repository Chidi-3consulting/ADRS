# 3Consulting Data Retention System — Architecture & Deployment Guide

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│              InMotion Shared Hosting (cPanel)            │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  Browser UI  │    │  cPanel Cron │                   │
│  │ (Bootstrap5) │    │  (Daily 1AM) │                   │
│  └──────┬───────┘    └──────┬───────┘                   │
│         │                   │                            │
│         ▼                   ▼                            │
│  ┌──────────────────────────────────────┐               │
│  │         Pure PHP 8.2 Layer           │               │
│  │                                      │               │
│  │  pages/     engine/    includes/     │               │
│  │  ├ login    retention  ├ db.php      │               │
│  │  ├ dashboard _cron.php ├ auth.php    │               │
│  │  ├ categories          ├ helpers.php │               │
│  │  ├ schedule            ├ mailer.php  │               │
│  │  ├ audit               └ templates  │               │
│  │  └ notifications                     │               │
│  └──────────────────┬───────────────────┘               │
│                     │                                    │
│         ┌───────────▼────────────┐                      │
│         │     MySQL 8.0          │                      │
│         │  ┌─────────────────┐  │                      │
│         │  │ users           │  │                      │
│         │  │ data_categories │  │                      │
│         │  │ data_records    │  │                      │
│         │  │ audit_log       │  │                      │
│         │  │ notifications   │  │                      │
│         │  │ schedule_reviews│  │                      │
│         │  │ system_settings │  │                      │
│         │  └─────────────────┘  │                      │
│         └────────────────────────┘                      │
│                                                          │
│  ┌─────────────────────────────────────┐                │
│  │     cPanel Email (SMTP/SSL :465)    │                │
│  │     PHPMailer → Notification emails │                │
│  └─────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────┘
```

---

## Deployment Steps (InMotion Shared Hosting)

### Step 1: Upload files
```bash
# Via cPanel File Manager or FTP:
# Upload project to: /home/username/public_html/data-retention/
```

### Step 2: Create MySQL database in cPanel
1. Login to cPanel → MySQL Databases
2. Create database: `username_retention`
3. Create user: `username_retapp` with strong password
4. Add user to database with ALL PRIVILEGES (except GRANT OPTION)
5. Then in phpMyAdmin, restrict audit_log:
```sql
REVOKE UPDATE, DELETE ON username_retention.audit_log FROM 'username_retapp'@'localhost';
```

### Step 3: Import schema and seed data
Via phpMyAdmin:
1. Select your database
2. Import `sql/schema.sql`
3. Import `sql/seed_gdpr_ndpr.sql`

### Step 4: Configure the application
Edit `src/config/database.php`:
```php
define('DB_HOST', 'localhost');
define('DB_NAME', 'username_retention');
define('DB_USER', 'username_retapp');
define('DB_PASS', 'your_strong_password');
define('APP_URL', 'https://yourdomain.com/data-retention');
define('APP_ENV', 'production');
```

Update SMTP settings via the application's admin panel (system settings page) after first login.

### Step 5: Set up cPanel Cron Jobs
Navigate to cPanel → Cron Jobs:

```
# Daily retention engine (01:00 AM)
Minute: 0  Hour: 1  Day: *  Month: *  Weekday: *
Command: /usr/local/bin/php /home/username/public_html/data-retention/src/engine/retention_cron.php >> /home/username/logs/retention_cron.log 2>&1

# Quarterly review emails (08:00 AM on 1st of Jan, Apr, Jul, Oct)
Minute: 0  Hour: 8  Day: 1  Month: 1,4,7,10  Weekday: *
Command: /usr/local/bin/php /home/username/public_html/data-retention/src/engine/retention_cron.php --task=quarterly_review >> /home/username/logs/quarterly_review.log 2>&1
```

> To find your PHP path on InMotion: run `which php` in cPanel Terminal, or use `/usr/local/bin/php`

### Step 6: Create log directories
Via cPanel File Manager:
```
/home/username/logs/retention_cron.log    (create empty file, chmod 644)
/home/username/logs/quarterly_review.log  (create empty file, chmod 644)
/home/username/logs/cron_errors.log       (create empty file, chmod 644)
/home/username/logs/mail_errors.log       (create empty file, chmod 644)
/home/username/logs/db_error.log          (create empty file, chmod 644)
```

> ⚠️ Logs are stored OUTSIDE public_html for security

### Step 7: Set file permissions
```
chmod 755 src/engine/retention_cron.php
chmod 644 src/config/database.php
chmod 644 .htaccess
```

### Step 8: First login
- URL: `https://yourdomain.com/data-retention/`
- Email: `admin@3consult-ng.com`
- Password: `password` ← **CHANGE IMMEDIATELY**
- Go to Users → Edit Admin → Set new secure password
- Go to System Settings → Configure SMTP email

---

## Security Checklist (post-deployment)

- [ ] Changed default admin password
- [ ] Configured SMTP with a real email account
- [ ] Verified `.htaccess` blocks direct access to `src/config/`
- [ ] Confirmed cron jobs are running (check log files after 01:00 AM)
- [ ] Revoked UPDATE/DELETE on `audit_log` table for app DB user
- [ ] SSL certificate active on domain (HTTPS enforced)
- [ ] Logs directory is outside `public_html`
- [ ] `APP_ENV` set to `production` in config

---

## Maintenance

| Task | Frequency | How |
|---|---|---|
| Check cron logs | Weekly | View `/home/username/logs/retention_cron.log` |
| Review audit log | Monthly | Dashboard → Audit Log |
| Quarterly retention review | Every 3 months | Dashboard → Run Schedule Review |
| Export NDPR Annual Report | Annually (January) | Audit Log → Export NDPR Annual Report |
| Update retention periods | As regulations change | Categories → Edit |
| Backup database | Weekly | cPanel → Backup Wizard |
