# Prompt 01 — Project Setup, Config, Helpers & Layout (v3)


> **Implementation Note:** This specification was originally written with PHP code examples.
> The ADRS codebase has been fully implemented in **Python (FastAPI + SQLAlchemy + Jinja2)**.
> The business logic, rules, and requirements documented below remain the authoritative
> specification. See `retention_py/` for the Python implementation.

---
## Pre-requisites
- Laragon running on Windows, PHP 8.2 active
- Database `data_retention_local` created with schema.sql + seed imported
- Mailpit running on localhost:1025 / localhost:8025
- Read `.github/copilot-instructions.md` fully before writing any code

---

## 1. `src/config/database.php` — Environment-aware config

Checks for `config.local.php` first (local dev), falls back to production constants.
Full implementation is in `prompts/00-local-dev-setup.md`. Use it exactly.

Key constants required in BOTH environments:
`DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS, DB_CHARSET`
`APP_NAME, APP_URL, APP_ENV, TIMEZONE`
`SESSION_NAME, CSRF_TOKEN_LENGTH`
`SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM_EMAIL, SMTP_FROM_NAME, SMTP_ENCRYPTION`
`SHOW_ERRORS, DEBUG_SQL, SMTP_DEBUG`
`UPLOAD_PATH` — absolute path OUTSIDE public_html e.g. `/home/username/retention_uploads/`
`LOG_PATH` — absolute path OUTSIDE public_html e.g. `/home/username/logs/`

Local values: `UPLOAD_PATH = C:\laragon\retention_uploads\`, `LOG_PATH = C:\laragon\logs\`

---

## 2. `src/includes/db.php` — PDO singleton

```php
function get_db(): PDO
```
- Singleton pattern using static variable
- On connect: immediately run `$pdo->exec("SET time_zone = '+01:00'")`  ← D3 CRITICAL
- Error mode: ERRMODE_EXCEPTION
- Fetch mode: FETCH_ASSOC
- ATTR_EMULATE_PREPARES: false
- On failure: write to LOG_PATH/db_error.log, show friendly error page, exit
- If DEBUG_SQL = true: wrap PDO in a query-logging proxy that appends every
  query + execution time to LOG_PATH/query.log

---

## 3. `src/includes/helpers.php` — All utility functions

### CSRF
- `csrf_token(): string` — generate 64-char token, store in `$_SESSION['csrf_token']`
- `csrf_field(): string` — returns full `<input type="hidden">` HTML
- `csrf_verify(): void` — compare POST token vs session, `http_response_code(403); exit` on mismatch

### Flash messages
- `flash(string $type, string $message): void` — store in `$_SESSION['flash'][]`
- `get_flash(): array` — return and clear all flash messages
- `render_flash(): string` — return full Bootstrap alert HTML for all pending flashes,
  auto-dismiss via CSS animation at 4 seconds

### Output & input
- `sanitize(mixed $input): string` — trim + htmlspecialchars ENT_QUOTES UTF-8
- `redirect(string $path): never` — header Location + exit
- `get_client_ip(): string` — handle HTTP_X_FORWARDED_FOR safely, return real IP

### Date & retention
- `format_date(?string $date, string $format = 'd M Y'): string`
- `format_datetime(?string $dt): string` — returns 'd M Y H:i:s'
- `days_until(string $date): int` — negative if past
- `retention_end_date(string $collection_date, int $days): string`
  → `date('Y-m-d', strtotime("+{$days} days", strtotime($collection_date)))` ← D4
- `relative_time(string $datetime): string` — "2 hours ago", "3 days ago"
- `days_remaining_badge(int $days, bool $html = true): string`
  → >90: green, 31-90: amber, 1-30: red, 0: dark red "TODAY",
    negative: dark red "OVERDUE ({abs} days)", disposed: grey strikethrough

### Pagination
- `paginate(int $total, int $per_page, int $current_page): array`
  → returns [total_pages, offset, has_prev, has_next, page_links_html]

### Audit logging
- `log_audit(PDO $pdo, string $action, string $entity_type, ?int $entity_id, ?int $performed_by, ?array $details, ?string $ip): void`
  → JSON-encodes details, inserts to audit_log, silently catches exceptions (never break main flow)

### Label helpers (for UI badges)
- `get_legal_basis_label(string $value): string`
- `get_disposal_method_label(string $value): string`
- `get_disposal_icon(string $method): string` — Bootstrap Icon HTML
- `get_framework_badge(string $framework): string` — Bootstrap badge HTML
- `get_status_badge(string $status): string` — Bootstrap badge with correct colour
- `get_role_badge(string $role): string`
- `calculate_retention_days(int $number, string $unit): int` — unit: days/months/years
- `get_audit_action_label(string $action): string` — human-readable label map

### Notification bell (N2)
- `get_unread_notification_count(PDO $pdo, int $user_id): int`
  → `SELECT COUNT(*) FROM notifications WHERE recipient_id = ? AND read_at IS NULL AND status = 'sent'`
- `get_unread_notifications(PDO $pdo, int $user_id, int $limit = 10): array`

### DSAR
- `generate_dsar_reference(PDO $pdo): string`
  → format: `DSAR-{YEAR}-{zero-padded 4-digit sequence}` e.g. DSAR-2025-0042
- `calculate_dsar_due_date(string $received_date): string` — +30 days

---

## 4. `src/includes/auth.php` — Authentication functions

- `login_user(PDO $pdo, string $email, string $password): bool`
  - Fetch user by email, verify `password_hash`
  - Check `is_active = 1` and `deleted_at IS NULL`
  - On success: `session_regenerate_id(true)`, set session vars, update `last_login_at`
  - Log `user_login` to audit_log
  - Return true/false — NEVER specify which field was wrong
- `logout_user(PDO $pdo): never`
  - Log `user_logout`, destroy session, redirect to login
- `require_login(): void` — redirects to login if no valid session
- `require_role(string ...$roles): void` — 403 redirect if role not in list
- `current_user(): array` — returns session user data
- `has_role(string ...$roles): bool`
- `is_logged_in(): bool`

**Password reset (S1 — advanced):**
- `create_password_reset_token(PDO $pdo, string $email): ?string`
  - Generate 64-char cryptographically random token via `bin2hex(random_bytes(32))`
  - Hash it: `hash('sha256', $token)`
  - Insert to `password_resets` table: `{email, token_hash, expires_at = NOW()+1hr}`
  - Return raw (unhashed) token for email
- `validate_reset_token(PDO $pdo, string $email, string $token): bool`
  - Fetch token where email matches, not expired, not used
  - Verify `hash('sha256', $token)` matches stored hash
- `consume_reset_token(PDO $pdo, string $email): void` — mark used

Add to schema (create separately or add to schema.sql):
```sql
CREATE TABLE IF NOT EXISTS `password_resets` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `email`      VARCHAR(255) NOT NULL,
  `token_hash` VARCHAR(64)  NOT NULL,
  `expires_at` TIMESTAMP    NOT NULL,
  `used`       TINYINT(1)   NOT NULL DEFAULT 0,
  `created_at` TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_resets_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## 5. Layout components

### `src/includes/layout_header.php`
Parameters accepted via `$page_title` and `$active_nav` variables set before include.

CDN links (in order):
1. Bootstrap 5.3 CSS
2. Bootstrap Icons 1.11 CSS
3. `assets/css/app.css`

HTML structure:
```
<html>
  <head>...</head>
  <body>
    <div class="wrapper d-flex">
      [SIDEBAR]
      <div class="main-content flex-grow-1">
        <div class="topbar">...</div>
        <div class="content-area p-4">
          [render_flash()]
```

**Sidebar** (always visible on authenticated pages):
- 3Consulting logo at top
- Nav links with Bootstrap Icons:
  - 🏠 Dashboard (`/`)
  - 📋 Data Categories (`/categories/`)
  - 📅 Retention Schedule (`/schedule/`)
  - ⬆️ Bulk Import (`/import/`) — Admin/DPO only
  - 📊 Audit Log (`/audit/`) — Admin/DPO only
  - 🔔 Notifications (`/notifications/`) + **unread badge** (N2)
    → badge HTML: `<span class="badge bg-danger"><?= $unread_count ?></span>`
    → `$unread_count` fetched via `get_unread_notification_count($pdo, current_user()['id'])`
  - 📨 DSAR Requests (`/dsar/`) — Admin/DPO only
  - ⏳ Recalculations (`/recalculations/`) — badge if pending (Admin/DPO)
  - 👥 Users (`/users/`) — Admin only
  - ⚙️ Settings (`/settings/`) — Admin only
  - ❓ Help (`/help.php`)
- Bottom of sidebar: current user name, role badge, "My Profile" link, Logout button

**Topbar:**
- Page title (from `$page_title`)
- Right: notification bell icon with count (same as sidebar — always in sync)
- Bell click opens Bootstrap dropdown with last 10 unread notifications inline
- "Mark all read" button in dropdown → POST to `notifications/mark_read.php`

### `src/includes/layout_footer.php`
- Closes all divs
- Footer bar: copyright, version `v3.0.0`, 3Consulting branding
- **Cron health indicator** (Admin/DPO only):
  - Query: last `created_at` from `audit_log` where `action` IN (cron actions) and `performed_by IS NULL`
  - If > 25 hours ago OR no cron entry ever: `⚠️ Automated engine last run: [time] — check cron job`
  - If healthy: `✅ Engine last run: [relative time]`
- Bootstrap 5.3 JS bundle (CDN)
- Custom JS: flash auto-dismiss, CSRF headers for fetch calls

---

## 6. `src/assets/css/app.css`

```css
:root {
  --3c-orange: #C85C1A;
  --3c-teal:   #1A6187;
  --3c-yellow: #E8A84C;
  --3c-light:  #F7F7F7;
  --3c-dark:   #1A1A2E;
}
```

Style rules:
- Sidebar: `var(--3c-dark)` bg, white text, `var(--3c-orange)` active left border (4px)
- `.btn-primary`: `var(--3c-orange)` bg
- `.card-header.card-header-teal`: `var(--3c-teal)` bg, white text
- `.card-header.card-header-orange`: `var(--3c-orange)` bg, white text
- `.badge-gdpr`: `#003399` bg (EU blue)
- `.badge-ndpr`: `#008751` bg (Nigerian green)
- `.badge-both`: `#6f42c1` bg (purple)
- `.days-pill.green / .amber / .red / .overdue / .disposed`: colour-coded pills
- Flash alerts: keyframe `fadeOutAlert` at 4 seconds
- Sidebar width: 260px, fixed left, full height
- Main content: `margin-left: 260px`
- Mobile: sidebar collapses to hamburger toggle at `<768px`
- `.attachment-drop-zone`: dashed border, hover state for drag-and-drop
- `.notification-dropdown`: max-height 400px, overflow-y scroll
- Print styles: hide sidebar, topbar, buttons — show table only

---

## 7. `index.php` — Front controller

```php
<?php
require_once __DIR__ . '/src/config/database.php';
date_default_timezone_set(TIMEZONE);
ini_set('display_errors', SHOW_ERRORS ? '1' : '0');

session_name(SESSION_NAME);
session_set_cookie_params([
    'lifetime' => 0,
    'path'     => '/',
    'secure'   => (APP_ENV === 'production'),
    'httponly' => true,
    'samesite' => 'Strict',
]);
session_start();

require_once __DIR__ . '/src/includes/auth.php';

if (is_logged_in()) {
    redirect(APP_URL . '/src/pages/dashboard.php');
} else {
    redirect(APP_URL . '/src/pages/login.php');
}
```

---

## 8. `.htaccess` — Environment-aware (production + local)

Full implementation in `prompts/00-local-dev-setup.md`. Key rules:
- HTTPS redirect skips localhost/127.0.0.1
- `RewriteBase /` (production subdomain — not /data-retention/)
- Block: `config/`, `includes/`, `engine/`, `sql/`, `logs/`, `*.log`, `*.md`, `*.sql`
- ErrorDocument: `ErrorDocument 404 /404.php`, `ErrorDocument 500 /500.php`
- Security headers: X-Frame-Options DENY, X-Content-Type-Options nosniff,
  Referrer-Policy strict-origin-when-cross-origin
- GZIP for html/css/js

---

## 9. Error pages

### `404.php` (project root)
- Full branded page (no sidebar — pre-auth layout reused)
- "Page Not Found" with 3Consulting logo
- Link back to dashboard or login
- HTTP 404 status code set

### `500.php` (project root)
- "Something went wrong" — no technical details visible
- Contact email: `support@3consult-ng.com`
- HTTP 500 status code set

### `maintenance.php` (project root)
- "System under maintenance" with estimated return time
- HTTP 503 status + Retry-After header
- Toggle via `.htaccess`: uncomment `RewriteRule ^ /maintenance.php [L]` during deploys

---

## 10. `src/pages/profile.php` — My Profile (all roles)

Every authenticated user can:
- Update their own name and email (email uniqueness validated)
- Change password: current password required, new password + confirm, min 10 chars
  with uppercase + number + special char validation
- View their own last login timestamp
- Log `user_updated` to audit_log on any change
- CSRF protected

---

## Expected output
20 files minimum. Write all files in full. No TODOs. No placeholders.
Every function must have a PHPDoc comment.
