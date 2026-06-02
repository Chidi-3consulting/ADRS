# ADRS Core — Milestone 1A: Foundation, Auth & Test Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the bedrock layer every other ADRS Core module reuses — environment config, the PDO singleton, the helper/auth libraries (aligned to the blueprint API and with the latent bugs fixed), the branded layout shell, login, and a no-Composer CLI test harness — ending with a user who can log in and see the dashboard shell.

**Architecture:** Pure PHP 8.2, no framework/Composer. `define()`-based config (with a gitignored `config.local.php` and a `config.test.php` for the disposable test DB). A `get_db()` PDO singleton sets `+01:00` on connect. Pure utility functions live in `helpers.php` and are unit-tested; auth lives in `auth.php`. A custom `tests/run.php` discovers and runs `*_test.php` files against a disposable test database.

**Tech Stack:** PHP 8.2, MySQL 8.0 (PDO), Bootstrap 5.3 + Bootstrap Icons (CDN), vanilla JS. Test harness: plain PHP CLI.

**Source of truth:** `ADRS_v2_MASTER_PACKAGE/01_BUILD_PACKAGE/.github/copilot-instructions.md` and `prompts/01-project-setup.md` + `prompts/02-auth-system.md`. Schema: `retention/sql/schema.sql` (unchanged).

**Conventions for this milestone:**
- All work on branch `adrs-core-rebuild`.
- Function/constant names follow the blueprint: `get_db()`, `get_setting()`, `sanitize()`, `csrf_token()/csrf_field()/csrf_verify()`, `flash()/get_flash()`, `redirect()`, `log_audit()`, `login_user()/require_login()/require_role()/has_role()/current_user()/is_logged_in()`.
- `system_settings` columns are `setting_key` / `setting_value` (NOT `key`/`value` — the existing build's `get_setting()` is wrong; we fix it here).
- Default seeded admin: `admin@3consult-ng.com` / `password`; DPO: `dpo@3consult-ng.com` / `password`.

---

## File Structure (this milestone)

| File | Responsibility |
|---|---|
| `retention/tests/run.php` | Test runner: discovers `tests/**/*_test.php`, prints results, exits non-zero on failure |
| `retention/tests/lib/assert.php` | `assert_true/equals/false/throws` + counters |
| `retention/tests/bootstrap.php` | Defines TEST DB constants, requires app config, resets test DB from schema |
| `retention/tests/unit/*_test.php` | Unit tests for helpers + auth |
| `retention/src/config/database.php` | `define()` all app constants; load `config.local.php` override |
| `retention/src/config/config.local.php` | Gitignored local dev secrets/paths |
| `retention/src/config/config.test.php` | Test DB name/paths (gitignored) |
| `retention/src/includes/db.php` | `get_db()` PDO singleton, `+01:00`, error handling |
| `retention/src/includes/helpers.php` | Pure utilities (fixed `get_setting`, date/retention, CSRF, flash, `log_audit`, labels, DSAR helpers) |
| `retention/src/includes/auth.php` | Sessions, login/logout, role gates, password-reset tokens |
| `retention/src/includes/layout_header.php` / `layout_footer.php` | Branded, role-aware shell |
| `retention/src/assets/css/app.css` | 3Consulting theme |
| `retention/src/pages/login.php` / `logout.php` / `dashboard.php` | Login + shell dashboard |
| `retention/index.php` | Front controller |
| `retention/404.php` / `500.php` | Branded error pages |

---

## Task 1: Commit the existing build as a baseline

**Files:** none created — version-control the current untracked tree so the rebuild is a visible diff.

- [ ] **Step 1: Confirm .gitignore protects secrets**

Run: `Get-Content retention/.gitignore` (PowerShell) or `cat retention/.gitignore`
Expected: it ignores `config.local.php` (and `.htaccess.local`, logs, storage). If `src/config/config.local.php` and `src/config/config.test.php` are NOT ignored, add these lines to `retention/.gitignore`:
```
src/config/config.local.php
src/config/config.test.php
storage/
*.log
```

- [ ] **Step 2: Stage and commit the baseline**

```bash
git add -A
git status   # verify config.local.php is NOT staged
git commit -m "chore: baseline — existing AI-generated build + master package

Snapshot before the Core rebuild so subsequent changes are a reviewable diff."
```
Expected: commit succeeds; `config.local.php` absent from the commit.

---

## Task 2: Test harness (no Composer)

**Files:**
- Create: `retention/tests/lib/assert.php`
- Create: `retention/tests/run.php`
- Create: `retention/tests/unit/harness_test.php`

- [ ] **Step 1: Write the assertion library**

Create `retention/tests/lib/assert.php`:
```php
<?php
/** Minimal no-Composer assertion library. */

$GLOBALS['__tests'] = ['passed' => 0, 'failed' => 0, 'failures' => []];

function _record_pass(): void { $GLOBALS['__tests']['passed']++; }

function _record_fail(string $msg): void {
    $GLOBALS['__tests']['failed']++;
    $GLOBALS['__tests']['failures'][] = $msg;
    echo "  \033[31mFAIL\033[0m $msg\n";
}

function assert_true($cond, string $msg = ''): void {
    if ($cond === true) { _record_pass(); } else { _record_fail($msg ?: 'expected true, got ' . var_export($cond, true)); }
}

function assert_false($cond, string $msg = ''): void {
    if ($cond === false) { _record_pass(); } else { _record_fail($msg ?: 'expected false, got ' . var_export($cond, true)); }
}

function assert_equals($expected, $actual, string $msg = ''): void {
    if ($expected === $actual) { _record_pass(); }
    else { _record_fail(($msg ?: 'not equal') . " — expected " . var_export($expected, true) . ", got " . var_export($actual, true)); }
}

function assert_throws(callable $fn, string $msg = ''): void {
    try { $fn(); _record_fail($msg ?: 'expected exception, none thrown'); }
    catch (Throwable $e) { _record_pass(); }
}
```

- [ ] **Step 2: Write the runner**

Create `retention/tests/run.php`:
```php
<?php
/** Usage: php tests/run.php  (run from retention/ root). Exit non-zero on any failure. */
error_reporting(E_ALL);
ini_set('display_errors', '1');

require __DIR__ . '/lib/assert.php';

$files = [];
$dir = new RecursiveDirectoryIterator(__DIR__, FilesystemIterator::SKIP_DOTS);
foreach (new RecursiveIteratorIterator($dir) as $f) {
    if (preg_match('/_test\.php$/', $f->getFilename())) { $files[] = $f->getPathname(); }
}
sort($files);

foreach ($files as $file) {
    echo "\n# " . substr($file, strlen(__DIR__) + 1) . "\n";
    require $file;
}

$t = $GLOBALS['__tests'];
echo "\n----------------------------------------\n";
echo "Passed: {$t['passed']}  Failed: {$t['failed']}\n";
exit($t['failed'] > 0 ? 1 : 0);
```

- [ ] **Step 3: Write a self-test proving the harness works**

Create `retention/tests/unit/harness_test.php`:
```php
<?php
assert_true(true, 'harness boolean true');
assert_equals(4, 2 + 2, 'harness arithmetic');
assert_throws(fn() => 1 / 0, 'harness catches errors');
```

- [ ] **Step 4: Run the harness**

Run: `php tests/run.php` (from `retention/`)
Expected: output lists `harness_test.php`, ends with `Passed: 3  Failed: 0`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add retention/tests/lib/assert.php retention/tests/run.php retention/tests/unit/harness_test.php
git commit -m "test: add no-Composer CLI test harness"
```

---

## Task 3: Environment config (constants + local/test overrides)

**Files:**
- Modify (rewrite): `retention/src/config/database.php`
- Create: `retention/src/config/config.local.php` (gitignored; local dev)
- Create: `retention/src/config/config.test.php` (gitignored; test DB)

- [ ] **Step 1: Rewrite `database.php` to define constants**

Replace the entire contents of `retention/src/config/database.php` with:
```php
<?php
/**
 * Application configuration. Loads config.local.php first (if present) so local/test
 * environments can pre-define constants; production falls back to the defaults below.
 * Secrets live in config.local.php (gitignored), NEVER here. SMTP lives in system_settings.
 */

$__local = __DIR__ . '/config.local.php';
if (is_file($__local)) { require $__local; }

// Environment
defined('APP_ENV')   || define('APP_ENV', 'production');     // 'production' | 'local' | 'test'
defined('APP_NAME')  || define('APP_NAME', 'ADRS — 3Consulting');
defined('APP_URL')   || define('APP_URL', 'https://retention.3consult-ng.com');
defined('TIMEZONE')  || define('TIMEZONE', 'Africa/Lagos');

// Database
defined('DB_HOST')    || define('DB_HOST', '127.0.0.1');
defined('DB_PORT')    || define('DB_PORT', '3306');
defined('DB_NAME')    || define('DB_NAME', 'adrs');
defined('DB_USER')    || define('DB_USER', 'root');
defined('DB_PASS')    || define('DB_PASS', '');
defined('DB_CHARSET') || define('DB_CHARSET', 'utf8mb4');

// Session / CSRF
defined('SESSION_NAME')       || define('SESSION_NAME', 'adrs_session');
defined('CSRF_TOKEN_LENGTH')  || define('CSRF_TOKEN_LENGTH', 32); // bytes -> 64 hex chars

// Paths (absolute, OUTSIDE public_html in production)
defined('UPLOAD_PATH') || define('UPLOAD_PATH', __DIR__ . '/../../storage/attachments/');
defined('LOG_PATH')    || define('LOG_PATH', __DIR__ . '/../../storage/logs/');

// Debug toggles
defined('SHOW_ERRORS') || define('SHOW_ERRORS', APP_ENV !== 'production');
defined('DEBUG_SQL')   || define('DEBUG_SQL', false);
```

- [ ] **Step 2: Create `config.local.php` for local dev**

Create `retention/src/config/config.local.php`:
```php
<?php
// Local development overrides — gitignored. Defined BEFORE database.php defaults.
define('APP_ENV', 'local');
define('APP_URL', 'http://localhost/retention');
define('DB_HOST', '127.0.0.1');
define('DB_PORT', '3306');
define('DB_NAME', 'adrs');
define('DB_USER', 'root');
define('DB_PASS', '');
define('UPLOAD_PATH', __DIR__ . '/../../storage/attachments/');
define('LOG_PATH', __DIR__ . '/../../storage/logs/');
```

- [ ] **Step 3: Create `config.test.php` (test DB constants, used by the test bootstrap)**

Create `retention/src/config/config.test.php`:
```php
<?php
// Test-database constants. Required by tests/bootstrap.php BEFORE database.php.
// Uses a SEPARATE database so tests never touch dev/prod data.
define('APP_ENV', 'test');
define('APP_URL', 'http://localhost/retention');
define('DB_HOST', '127.0.0.1');
define('DB_PORT', '3306');
define('DB_NAME', 'adrs_test');
define('DB_USER', 'root');
define('DB_PASS', '');
define('UPLOAD_PATH', __DIR__ . '/../../storage/attachments_test/');
define('LOG_PATH', __DIR__ . '/../../storage/logs_test/');
```

- [ ] **Step 4: Verify config loads without error**

Run: `php -r "define('APP_ENV','test'); require 'retention/src/config/database.php'; echo DB_NAME, PHP_EOL;"`
Expected: prints `adrs_test` (the pre-defined constant wins) and no errors.

- [ ] **Step 5: Commit**

```bash
git add retention/src/config/database.php retention/.gitignore
git commit -m "feat(config): constant-based environment config with local/test overrides"
```
(Note: `config.local.php` and `config.test.php` are gitignored and intentionally not committed.)

---

## Task 4: `get_db()` PDO singleton

**Files:**
- Modify (rewrite): `retention/src/includes/db.php`
- Create: `retention/tests/bootstrap.php`
- Create: `retention/tests/integration/db_test.php`

- [ ] **Step 1: Rewrite `db.php`**

Replace the entire contents of `retention/src/includes/db.php` with:
```php
<?php
require_once __DIR__ . '/../config/database.php';

/**
 * Returns a shared PDO connection. Sets MySQL session time zone to +01:00 (Lagos)
 * on connect — CRITICAL so all NOW()/CURDATE() math matches the app timezone.
 */
function get_db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $dsn = sprintf('mysql:host=%s;port=%s;dbname=%s;charset=%s', DB_HOST, DB_PORT, DB_NAME, DB_CHARSET);
    $options = [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES   => false,
    ];

    try {
        $pdo = new PDO($dsn, DB_USER, DB_PASS, $options);
        $pdo->exec("SET time_zone = '+01:00'");
        $pdo->exec("SET NAMES utf8mb4");
    } catch (PDOException $e) {
        if (!is_dir(LOG_PATH)) { @mkdir(LOG_PATH, 0755, true); }
        @file_put_contents(LOG_PATH . 'db_error.log', '[' . date('c') . '] ' . $e->getMessage() . PHP_EOL, FILE_APPEND);
        if (SHOW_ERRORS) { throw $e; }
        http_response_code(500);
        echo 'A database error occurred. Please try again later.';
        exit;
    }

    return $pdo;
}
```

- [ ] **Step 2: Write the test bootstrap that resets a disposable test DB**

Create `retention/tests/bootstrap.php`:
```php
<?php
/**
 * Test bootstrap: defines test-DB constants, connects, and re-imports schema.sql into a
 * FRESH adrs_test database before each test run. Requires the adrs_test DB to exist
 * (CREATE DATABASE adrs_test) and the configured user to have privileges on it.
 */
require __DIR__ . '/../src/config/config.test.php';
require_once __DIR__ . '/../src/includes/db.php';
require_once __DIR__ . '/../src/includes/helpers.php';
require_once __DIR__ . '/../src/includes/auth.php';

function reset_test_db(): PDO {
    // Connect without dbname to (re)create the schema container, then import.
    $dsn = sprintf('mysql:host=%s;port=%s;charset=%s', DB_HOST, DB_PORT, DB_CHARSET);
    $root = new PDO($dsn, DB_USER, DB_PASS, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $root->exec("DROP DATABASE IF EXISTS `" . DB_NAME . "`");
    $root->exec("CREATE DATABASE `" . DB_NAME . "` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo = get_db();
    $sql = file_get_contents(__DIR__ . '/../sql/schema.sql');
    $pdo->exec($sql);
    return $pdo;
}

// Reset once at the start of the whole run.
reset_test_db();
```

- [ ] **Step 3: Make the runner load the bootstrap first**

In `retention/tests/run.php`, add the bootstrap require immediately AFTER the assert.php require line:
```php
require __DIR__ . '/lib/assert.php';
require __DIR__ . '/bootstrap.php';   // <-- add this line
```

- [ ] **Step 4: Write an integration test for the DB connection + timezone**

Create `retention/tests/integration/db_test.php`:
```php
<?php
$pdo = get_db();
assert_true($pdo instanceof PDO, 'get_db returns PDO');

$tz = $pdo->query("SELECT @@session.time_zone AS tz")->fetch()['tz'];
assert_equals('+01:00', $tz, 'session time zone is +01:00');

// Schema imported: data_categories should be seeded (30 categories) by schema.sql.
$count = (int) $pdo->query("SELECT COUNT(*) c FROM data_categories")->fetch()['c'];
assert_true($count >= 30, "schema+seed loaded: $count categories");
```

- [ ] **Step 5: Create the test database, then run**

Run (one-time DB creation; adjust user if needed):
`mysql -uroot -e "CREATE DATABASE IF NOT EXISTS adrs_test"`
Then: `php tests/run.php`
Expected: `db_test.php` passes all 3 assertions; suite ends `Failed: 0`.

> If `schema.sql` does not also insert the 30 seed categories, change the assertion to `>= 0` and instead import `sql/seed_gdpr_ndpr.sql` inside `reset_test_db()` after the schema import.

- [ ] **Step 6: Commit**

```bash
git add retention/src/includes/db.php retention/tests/run.php retention/tests/integration/db_test.php
git commit -m "feat(db): get_db() singleton with +01:00 tz; test bootstrap resets adrs_test"
```

---

## Task 5: Helpers — pure date/retention functions (TDD)

**Files:**
- Modify (rewrite): `retention/src/includes/helpers.php`
- Create: `retention/tests/unit/helpers_dates_test.php`

- [ ] **Step 1: Write failing tests for date/retention helpers**

Create `retention/tests/unit/helpers_dates_test.php`:
```php
<?php
// retention_end_date(collection_date, days) = collection + N days (D4 fixed-days)
assert_equals('2025-01-31', retention_end_date('2025-01-01', 30), 'retention_end_date adds days');
assert_equals('2026-01-01', retention_end_date('2025-01-01', 365), 'retention_end_date 1 year');

// days_until is negative when the date is in the past
assert_true(days_until(date('Y-m-d', strtotime('-5 days'))) < 0, 'days_until past is negative');
assert_equals(0, days_until(date('Y-m-d')), 'days_until today is 0');

// calculate_retention_days converts units
assert_equals(30, calculate_retention_days(30, 'days'), 'days unit');
assert_equals(365, calculate_retention_days(1, 'years'), 'years unit');
assert_equals(90, calculate_retention_days(3, 'months'), 'months unit (30/mo)');

// format_date handles null
assert_equals('—', format_date(null), 'format_date null shows dash');
```

- [ ] **Step 2: Run to verify failure**

Run: `php tests/run.php`
Expected: FAIL — `Call to undefined function retention_end_date()` (or similar) for the new file.

- [ ] **Step 3: Write `helpers.php` with the date/retention functions**

Replace the entire contents of `retention/src/includes/helpers.php` with the following (this file is extended in Tasks 5b/5c — keep adding, do not remove):
```php
<?php
require_once __DIR__ . '/db.php';

/* ---------------- Date & retention (D4: fixed days) ---------------- */

/** Collection date + N days, as Y-m-d. */
function retention_end_date(string $collection_date, int $days): string {
    return date('Y-m-d', strtotime("+{$days} days", strtotime($collection_date)));
}

/** Whole days until $date (negative if past). */
function days_until(string $date): int {
    $today = new DateTimeImmutable('today');
    $target = new DateTimeImmutable($date);
    return (int) $today->diff($target)->format('%r%a');
}

/** Convert a number + unit (days/months/years) to whole days (30/mo, 365/yr). */
function calculate_retention_days(int $number, string $unit): int {
    return match ($unit) {
        'years'  => $number * 365,
        'months' => $number * 30,
        default  => $number,
    };
}

/** Human date; '—' for null/empty. */
function format_date(?string $date, string $format = 'd M Y'): string {
    if ($date === null || $date === '' || $date === '0000-00-00') { return '—'; }
    return date($format, strtotime($date));
}

/** Human datetime; '—' for null/empty. */
function format_datetime(?string $dt): string {
    if ($dt === null || $dt === '') { return '—'; }
    return date('d M Y H:i:s', strtotime($dt));
}
```

- [ ] **Step 4: Run to verify pass**

Run: `php tests/run.php`
Expected: the 8 date assertions PASS; suite `Failed: 0`.

- [ ] **Step 5: Commit**

```bash
git add retention/src/includes/helpers.php retention/tests/unit/helpers_dates_test.php
git commit -m "feat(helpers): date/retention helpers with tests (D4 fixed-days)"
```

---

## Task 5b: Helpers — settings, CSRF, flash, sanitize, IP

**Files:**
- Modify: `retention/src/includes/helpers.php` (append)
- Create: `retention/tests/integration/helpers_settings_test.php`

- [ ] **Step 1: Write failing test for `get_setting` (correct columns)**

Create `retention/tests/integration/helpers_settings_test.php`:
```php
<?php
$pdo = get_db();
// Seeded by schema.sql:
assert_equals('30', (string) get_setting($pdo, 'review_alert_days'), 'review_alert_days seeded = 30');
assert_equals('core', (string) get_setting($pdo, 'adrs_tier'), 'adrs_tier seeded = core');
// Unknown key returns the default:
assert_equals('fallback', get_setting($pdo, 'no_such_key_xyz', 'fallback'), 'unknown key uses default');
```

- [ ] **Step 2: Run to verify failure**

Run: `php tests/run.php`
Expected: FAIL — current `get_setting` (if still old) queries `key`/`value` and errors, OR function differs. (We are rewriting it next.)

- [ ] **Step 3: Append settings/CSRF/flash/sanitize/IP helpers**

Append to `retention/src/includes/helpers.php`:
```php

/* ---------------- Settings (system_settings: setting_key / setting_value) ---------------- */

/** Read a system setting with in-request static cache. Returns $default if absent. */
function get_setting(PDO $pdo, string $key, $default = null) {
    static $cache = [];
    if (array_key_exists($key, $cache)) { return $cache[$key]; }
    $stmt = $pdo->prepare('SELECT setting_value FROM system_settings WHERE setting_key = :k LIMIT 1');
    $stmt->execute(['k' => $key]);
    $row = $stmt->fetch();
    return $cache[$key] = ($row === false ? $default : $row['setting_value']);
}

/* ---------------- Output / input ---------------- */

/** Trim + htmlspecialchars (UTF-8, quotes). */
function sanitize(mixed $input): string {
    return htmlspecialchars(trim((string) $input), ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

/** Alias used in views for already-typed strings. */
function escape_html(string $value): string {
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

/** Header redirect + exit. */
function redirect(string $url): never {
    header('Location: ' . $url);
    exit;
}

/** Best-effort real client IP. */
function get_client_ip(): string {
    foreach (['HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'] as $k) {
        if (!empty($_SERVER[$k])) {
            $ip = trim(explode(',', $_SERVER[$k])[0]);
            if (filter_var($ip, FILTER_VALIDATE_IP)) { return $ip; }
        }
    }
    return '0.0.0.0';
}

/* ---------------- CSRF ---------------- */

function _session(): void { if (session_status() === PHP_SESSION_NONE) { session_start(); } }

/** Current CSRF token (64 hex chars), created on first use. */
function csrf_token(): string {
    _session();
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(CSRF_TOKEN_LENGTH));
    }
    return $_SESSION['csrf_token'];
}

/** Hidden input HTML for forms. */
function csrf_field(): string {
    return '<input type="hidden" name="csrf_token" value="' . escape_html(csrf_token()) . '">';
}

/** Verify POSTed token; 403 + exit on mismatch. */
function csrf_verify(): void {
    _session();
    $posted = $_POST['csrf_token'] ?? '';
    if (!hash_equals($_SESSION['csrf_token'] ?? '', $posted)) {
        http_response_code(403);
        exit('Invalid CSRF token.');
    }
}

/* ---------------- Flash messages ---------------- */

function flash(string $type, string $message): void {
    _session();
    $_SESSION['flash'][] = ['type' => $type, 'message' => $message];
}

function get_flash(): array {
    _session();
    $f = $_SESSION['flash'] ?? [];
    unset($_SESSION['flash']);
    return $f;
}

/** Bootstrap alert HTML for all pending flashes. */
function render_flash(): string {
    $map = ['success' => 'success', 'error' => 'danger', 'danger' => 'danger', 'info' => 'info', 'warning' => 'warning'];
    $html = '';
    foreach (get_flash() as $f) {
        $cls = $map[$f['type']] ?? 'info';
        $html .= '<div class="alert alert-' . $cls . ' alert-dismissible fade show" role="alert">'
              . escape_html($f['message'])
              . '<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>';
    }
    return $html;
}
```

- [ ] **Step 4: Run to verify pass**

Run: `php tests/run.php`
Expected: settings test passes (`30`, `core`, `fallback`); suite `Failed: 0`.

- [ ] **Step 5: Commit**

```bash
git add retention/src/includes/helpers.php retention/tests/integration/helpers_settings_test.php
git commit -m "feat(helpers): fixed get_setting columns + CSRF/flash/sanitize/IP"
```

---

## Task 5c: Helpers — audit logging, DSAR refs, UI label badges

**Files:**
- Modify: `retention/src/includes/helpers.php` (append)
- Create: `retention/tests/integration/helpers_audit_test.php`

- [ ] **Step 1: Write failing tests for `log_audit` + DSAR helpers**

Create `retention/tests/integration/helpers_audit_test.php`:
```php
<?php
$pdo = get_db();
$before = (int) $pdo->query("SELECT COUNT(*) c FROM audit_log")->fetch()['c'];

log_audit($pdo, 'user_login', 'user', 1, 1, ['note' => 'test'], '127.0.0.1');

$after = (int) $pdo->query("SELECT COUNT(*) c FROM audit_log")->fetch()['c'];
assert_equals($before + 1, $after, 'log_audit inserts one row');

$row = $pdo->query("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1")->fetch();
assert_equals('user_login', $row['action'], 'action stored');
assert_true(str_contains($row['details'], 'test'), 'details JSON stored');

// log_audit must never throw, even with a bad action (silently swallow).
log_audit($pdo, 'not_a_real_action_value', 'system', null, null, null, null);
assert_true(true, 'log_audit swallowed invalid enum without throwing');

// DSAR reference format DSAR-YYYY-0001
$ref = generate_dsar_reference($pdo);
assert_true((bool) preg_match('/^DSAR-\d{4}-\d{4}$/', $ref), "dsar ref format: $ref");
assert_equals(date('Y-m-d', strtotime('+30 days', strtotime('2025-01-01'))), calculate_dsar_due_date('2025-01-01'), 'dsar due +30');
```

- [ ] **Step 2: Run to verify failure**

Run: `php tests/run.php`
Expected: FAIL — undefined `log_audit` / `generate_dsar_reference` / `calculate_dsar_due_date`.

- [ ] **Step 3: Append audit/DSAR/label helpers**

Append to `retention/src/includes/helpers.php`:
```php

/* ---------------- Audit logging (append-only; never breaks main flow) ---------------- */

/** Insert an audit_log row. Silently swallows any error so logging never breaks a request. */
function log_audit(PDO $pdo, string $action, string $entity_type, ?int $entity_id, ?int $performed_by, ?array $details, ?string $ip): void {
    try {
        $stmt = $pdo->prepare(
            'INSERT INTO audit_log (action, entity_type, entity_id, performed_by, details, ip_address)
             VALUES (:a, :et, :eid, :pb, :d, :ip)'
        );
        $stmt->execute([
            'a'   => $action,
            'et'  => $entity_type,
            'eid' => $entity_id,
            'pb'  => $performed_by,
            'd'   => $details === null ? null : json_encode($details, JSON_UNESCAPED_UNICODE),
            'ip'  => $ip,
        ]);
    } catch (Throwable $e) {
        if (defined('LOG_PATH')) {
            if (!is_dir(LOG_PATH)) { @mkdir(LOG_PATH, 0755, true); }
            @file_put_contents(LOG_PATH . 'audit_error.log', '[' . date('c') . '] ' . $e->getMessage() . PHP_EOL, FILE_APPEND);
        }
    }
}

/* ---------------- DSAR (C1) ---------------- */

/** Next DSAR reference: DSAR-{year}-{4-digit sequence within that year}. */
function generate_dsar_reference(PDO $pdo): string {
    $year = date('Y');
    $stmt = $pdo->prepare("SELECT COUNT(*) c FROM dsar_requests WHERE YEAR(created_at) = :y");
    $stmt->execute(['y' => $year]);
    $seq = ((int) $stmt->fetch()['c']) + 1;
    return sprintf('DSAR-%s-%04d', $year, $seq);
}

/** DSAR statutory due date: received + 30 days. */
function calculate_dsar_due_date(string $received_date): string {
    return date('Y-m-d', strtotime('+30 days', strtotime($received_date)));
}

/* ---------------- UI label/badge helpers ---------------- */

function get_legal_basis_label(string $v): string {
    return [
        'legal_obligation' => 'Legal Obligation', 'contract' => 'Contract', 'consent' => 'Consent',
        'legitimate_interest' => 'Legitimate Interest', 'vital_interest' => 'Vital Interest', 'public_task' => 'Public Task',
    ][$v] ?? ucfirst(str_replace('_', ' ', $v));
}

function get_disposal_method_label(string $v): string {
    return ['delete' => 'Secure Delete', 'anonymise' => 'Anonymise', 'archive' => 'Archive'][$v] ?? ucfirst($v);
}

function get_status_badge(string $status): string {
    $map = [
        'active' => 'success', 'due_review' => 'warning', 'disposal_requested' => 'info',
        'legal_hold' => 'dark', 'disposed' => 'secondary',
    ];
    $cls = $map[$status] ?? 'secondary';
    return '<span class="badge bg-' . $cls . '">' . escape_html(ucwords(str_replace('_', ' ', $status))) . '</span>';
}

function get_role_badge(string $role): string {
    $label = ['admin' => 'Administrator', 'dpo' => 'DPO', 'data_owner' => 'Data Owner'][$role] ?? $role;
    return '<span class="badge bg-secondary">' . escape_html($label) . '</span>';
}

function get_framework_badge(string $f): string {
    $cls = ['GDPR' => 'badge-gdpr', 'NDPR' => 'badge-ndpr', 'BOTH' => 'badge-both'][$f] ?? 'bg-secondary';
    return '<span class="badge ' . $cls . '">' . escape_html($f) . '</span>';
}

/* ---------------- Notification bell (N2) ---------------- */

function get_unread_notification_count(PDO $pdo, int $user_id): int {
    $stmt = $pdo->prepare("SELECT COUNT(*) c FROM notifications WHERE recipient_id = :u AND read_at IS NULL AND status = 'sent'");
    $stmt->execute(['u' => $user_id]);
    return (int) $stmt->fetch()['c'];
}

function get_unread_notifications(PDO $pdo, int $user_id, int $limit = 10): array {
    $stmt = $pdo->prepare("SELECT * FROM notifications WHERE recipient_id = :u AND read_at IS NULL ORDER BY created_at DESC LIMIT :lim");
    $stmt->bindValue('u', $user_id, PDO::PARAM_INT);
    $stmt->bindValue('lim', $limit, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll();
}
```

- [ ] **Step 4: Run to verify pass**

Run: `php tests/run.php`
Expected: audit + DSAR assertions PASS; suite `Failed: 0`.

- [ ] **Step 5: Commit**

```bash
git add retention/src/includes/helpers.php retention/tests/integration/helpers_audit_test.php
git commit -m "feat(helpers): log_audit, DSAR references, UI label/badge + notification helpers"
```

---

## Task 6: Auth — login, role gates, password-reset tokens (TDD)

**Files:**
- Modify (rewrite): `retention/src/includes/auth.php`
- Create: `retention/tests/integration/auth_test.php`

- [ ] **Step 1: Write failing tests**

Create `retention/tests/integration/auth_test.php`:
```php
<?php
$pdo = get_db();

// Seed a known user with bcrypt of 'password'.
$hash = password_hash('password', PASSWORD_BCRYPT);
$pdo->prepare("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('T','t@x.io',:h,'admin',1)")
    ->execute(['h' => $hash]);

assert_true(login_user($pdo, 't@x.io', 'password'), 'login succeeds with correct password');
assert_false(login_user($pdo, 't@x.io', 'wrong'), 'login fails with wrong password');
assert_false(login_user($pdo, 'nobody@x.io', 'password'), 'login fails unknown email');

// Inactive users cannot log in.
$pdo->exec("UPDATE users SET is_active=0 WHERE email='t@x.io'");
assert_false(login_user($pdo, 't@x.io', 'password'), 'inactive user cannot log in');

// Password reset token lifecycle.
$pdo->exec("UPDATE users SET is_active=1 WHERE email='t@x.io'");
$raw = create_password_reset_token($pdo, 't@x.io');
assert_true(is_string($raw) && strlen($raw) === 64, 'reset token is 64 hex chars');
assert_true(validate_reset_token($pdo, 't@x.io', $raw), 'valid token validates');
assert_false(validate_reset_token($pdo, 't@x.io', 'deadbeef'), 'bad token rejected');
consume_reset_token($pdo, 't@x.io');
assert_false(validate_reset_token($pdo, 't@x.io', $raw), 'consumed token no longer valid');
```

- [ ] **Step 2: Run to verify failure**

Run: `php tests/run.php`
Expected: FAIL — undefined `create_password_reset_token` (and `login_user` semantics differ).

- [ ] **Step 3: Rewrite `auth.php`**

Replace the entire contents of `retention/src/includes/auth.php` with:
```php
<?php
require_once __DIR__ . '/helpers.php';

function _auth_session(): void { if (session_status() === PHP_SESSION_NONE) { session_start(); } }

function is_logged_in(): bool { _auth_session(); return !empty($_SESSION['user']); }

function current_user(): array { _auth_session(); return $_SESSION['user'] ?? []; }

function has_role(string ...$roles): bool {
    $u = current_user();
    return isset($u['role']) && in_array($u['role'], $roles, true);
}

function require_login(): void {
    if (!is_logged_in()) { redirect(APP_URL . '/src/pages/login.php'); }
}

function require_role(string ...$roles): void {
    require_login();
    if (!has_role(...$roles)) {
        http_response_code(403);
        exit('Forbidden — you do not have access to this page.');
    }
}

/**
 * Verify credentials and start an authenticated session.
 * Returns false (never revealing which field was wrong) on any failure.
 */
function login_user(PDO $pdo, string $email, string $password): bool {
    $stmt = $pdo->prepare("SELECT * FROM users WHERE email = :e AND is_active = 1 AND deleted_at IS NULL LIMIT 1");
    $stmt->execute(['e' => $email]);
    $user = $stmt->fetch();
    if (!$user || !password_verify($password, $user['password_hash'])) {
        return false;
    }
    _auth_session();
    session_regenerate_id(true);
    unset($user['password_hash']);
    $_SESSION['user'] = $user;
    $pdo->prepare("UPDATE users SET last_login_at = NOW() WHERE id = :id")->execute(['id' => $user['id']]);
    log_audit($pdo, 'user_login', 'user', (int) $user['id'], (int) $user['id'], null, get_client_ip());
    return true;
}

function logout_user(PDO $pdo): never {
    if (is_logged_in()) {
        $u = current_user();
        log_audit($pdo, 'user_logout', 'user', (int) $u['id'], (int) $u['id'], null, get_client_ip());
    }
    _auth_session();
    session_unset();
    session_destroy();
    redirect(APP_URL . '/src/pages/login.php');
}

/* ---------------- Password reset tokens (1-hour expiry, SHA-256 hashed) ---------------- */

function create_password_reset_token(PDO $pdo, string $email): ?string {
    $stmt = $pdo->prepare("SELECT id FROM users WHERE email = :e AND is_active = 1 AND deleted_at IS NULL LIMIT 1");
    $stmt->execute(['e' => $email]);
    if (!$stmt->fetch()) { return null; }

    $raw  = bin2hex(random_bytes(32)); // 64 hex chars
    $hash = hash('sha256', $raw);
    $pdo->prepare("INSERT INTO password_resets (email, token_hash, expires_at) VALUES (:e, :h, DATE_ADD(NOW(), INTERVAL 1 HOUR))")
        ->execute(['e' => $email, 'h' => $hash]);
    log_audit($pdo, 'password_reset_requested', 'user', null, null, ['email' => $email], get_client_ip());
    return $raw;
}

function validate_reset_token(PDO $pdo, string $email, string $token): bool {
    $hash = hash('sha256', $token);
    $stmt = $pdo->prepare(
        "SELECT id FROM password_resets
         WHERE email = :e AND token_hash = :h AND used = 0 AND expires_at > NOW()
         ORDER BY id DESC LIMIT 1"
    );
    $stmt->execute(['e' => $email, 'h' => $hash]);
    return (bool) $stmt->fetch();
}

function consume_reset_token(PDO $pdo, string $email): void {
    $pdo->prepare("UPDATE password_resets SET used = 1 WHERE email = :e AND used = 0")->execute(['e' => $email]);
}
```

- [ ] **Step 4: Run to verify pass**

Run: `php tests/run.php`
Expected: all auth assertions PASS; suite `Failed: 0`.

- [ ] **Step 5: Commit**

```bash
git add retention/src/includes/auth.php retention/tests/integration/auth_test.php
git commit -m "feat(auth): login/role gates + password-reset token lifecycle with tests"
```

---

## Task 7: Layout shell, theme, login, dashboard, front controller, error pages

**Files:**
- Create: `retention/src/assets/css/app.css`
- Create: `retention/src/includes/layout_header.php`
- Create: `retention/src/includes/layout_footer.php`
- Rewrite: `retention/src/pages/login.php`
- Create: `retention/src/pages/logout.php`
- Rewrite: `retention/src/pages/dashboard.php`
- Rewrite: `retention/index.php`
- Create: `retention/404.php`, `retention/500.php`

> View layer — verified by manual smoke test (Step 9), not unit tests.

- [ ] **Step 1: Theme CSS**

Create `retention/src/assets/css/app.css`:
```css
:root{
  --3c-orange:#C85C1A; --3c-teal:#1A6187; --3c-yellow:#E8A84C;
  --3c-light:#F7F7F7; --3c-dark:#1A1A2E;
}
body{ background:var(--3c-light); }
.wrapper{ min-height:100vh; }
.sidebar{ width:260px; min-height:100vh; background:var(--3c-dark); color:#fff; position:fixed; top:0; left:0; }
.sidebar .brand{ color:var(--3c-orange); font-weight:700; font-size:1.4rem; padding:1rem 1.25rem; }
.sidebar a{ color:#cfd2dc; text-decoration:none; display:block; padding:.6rem 1.25rem; border-left:4px solid transparent; }
.sidebar a:hover{ background:rgba(255,255,255,.06); color:#fff; }
.sidebar a.active{ border-left-color:var(--3c-orange); background:rgba(255,255,255,.08); color:#fff; }
.main-content{ margin-left:260px; }
.topbar{ background:#fff; border-bottom:1px solid #e5e5e5; padding:.75rem 1.5rem; }
.btn-primary{ background:var(--3c-orange); border-color:var(--3c-orange); }
.btn-primary:hover{ background:#a94c14; border-color:#a94c14; }
.card-header-teal{ background:var(--3c-teal); color:#fff; }
.card-header-orange{ background:var(--3c-orange); color:#fff; }
.badge-gdpr{ background:#003399; } .badge-ndpr{ background:#008751; } .badge-both{ background:#6f42c1; }
@media (max-width: 768px){ .sidebar{ position:static; width:100%; min-height:auto; } .main-content{ margin-left:0; } }
@media print{ .sidebar,.topbar,.btn{ display:none!important; } .main-content{ margin-left:0; } }
```

- [ ] **Step 2: Header (role-aware sidebar)**

Create `retention/src/includes/layout_header.php`:
```php
<?php
require_once __DIR__ . '/auth.php';
require_login();
$__pdo = get_db();
$__user = current_user();
$page_title = $page_title ?? 'Dashboard';
$active_nav = $active_nav ?? '';
$__unread = get_unread_notification_count($__pdo, (int) $__user['id']);
function navlink(string $key, string $active, string $href, string $icon, string $label): string {
    $cls = $key === $active ? 'active' : '';
    return '<a class="' . $cls . '" href="' . APP_URL . $href . '"><i class="bi ' . $icon . '"></i> ' . escape_html($label) . '</a>';
}
?>
<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= escape_html($page_title) ?> — <?= escape_html(APP_NAME) ?></title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
<link href="<?= APP_URL ?>/src/assets/css/app.css" rel="stylesheet">
</head><body>
<div class="wrapper">
  <nav class="sidebar">
    <div class="brand">ADRS</div>
    <?= navlink('dashboard', $active_nav, '/src/pages/dashboard.php', 'bi-house', 'Dashboard') ?>
    <?= navlink('categories', $active_nav, '/src/pages/categories/index.php', 'bi-collection', 'Data Categories') ?>
    <?= navlink('records', $active_nav, '/src/pages/records/index.php', 'bi-card-list', 'Retention Schedule') ?>
    <?php if (has_role('admin','dpo')): ?>
      <?= navlink('audit', $active_nav, '/src/pages/audit/index.php', 'bi-shield-check', 'Audit Log') ?>
      <?= navlink('dsar', $active_nav, '/src/pages/dsar/index.php', 'bi-envelope-paper', 'DSAR Requests') ?>
    <?php endif; ?>
    <?= navlink('notifications', $active_nav, '/src/pages/notifications/index.php', 'bi-bell', 'Notifications') ?>
    <?php if (has_role('admin')): ?>
      <?= navlink('users', $active_nav, '/src/pages/users/index.php', 'bi-people', 'Users') ?>
      <?= navlink('settings', $active_nav, '/src/pages/settings/index.php', 'bi-gear', 'Settings') ?>
    <?php endif; ?>
    <div class="mt-auto p-3 border-top border-secondary">
      <div class="small text-light"><?= escape_html($__user['name']) ?></div>
      <?= get_role_badge($__user['role']) ?>
      <a class="d-block mt-2 text-warning" href="<?= APP_URL ?>/src/pages/logout.php">Logout</a>
    </div>
  </nav>
  <div class="main-content">
    <div class="topbar d-flex justify-content-between align-items-center">
      <h1 class="h5 mb-0"><?= escape_html($page_title) ?></h1>
      <a class="position-relative" href="<?= APP_URL ?>/src/pages/notifications/index.php">
        <i class="bi bi-bell fs-5"></i>
        <?php if ($__unread > 0): ?><span class="badge bg-danger position-absolute top-0 start-100 translate-middle"><?= $__unread ?></span><?php endif; ?>
      </a>
    </div>
    <div class="content-area p-4">
      <?= render_flash() ?>
```

- [ ] **Step 3: Footer**

Create `retention/src/includes/layout_footer.php`:
```php
    </div><!-- /content-area -->
  </div><!-- /main-content -->
</div><!-- /wrapper -->
<footer class="text-center text-muted small py-3">
  &copy; <?= date('Y') ?> 3Consulting Limited · ADRS v3.0.0
</footer>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body></html>
```

- [ ] **Step 4: Login page**

Replace the entire contents of `retention/src/pages/login.php` with:
```php
<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
if (is_logged_in()) { redirect(APP_URL . '/src/pages/dashboard.php'); }

$error = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $pdo = get_db();
    $email = trim($_POST['email'] ?? '');
    $password = $_POST['password'] ?? '';
    if (login_user($pdo, $email, $password)) {
        redirect(APP_URL . '/src/pages/dashboard.php');
    }
    $error = 'Invalid email or password.';
}
?>
<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login — <?= escape_html(APP_NAME) ?></title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="<?= APP_URL ?>/src/assets/css/app.css" rel="stylesheet">
</head><body class="d-flex align-items-center" style="min-height:100vh;">
<div class="container" style="max-width:420px;">
  <div class="card shadow-sm">
    <div class="card-header card-header-orange text-center"><h1 class="h4 mb-0">ADRS</h1></div>
    <div class="card-body">
      <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
      <form method="post">
        <?= csrf_field() ?>
        <div class="mb-3"><label class="form-label">Email</label>
          <input type="email" name="email" class="form-control" required autofocus></div>
        <div class="mb-3"><label class="form-label">Password</label>
          <input type="password" name="password" class="form-control" required></div>
        <button class="btn btn-primary w-100">Sign in</button>
      </form>
    </div>
  </div>
  <p class="text-center text-muted small mt-3">3Consulting Limited</p>
</div></body></html>
```

- [ ] **Step 5: Logout**

Create `retention/src/pages/logout.php`:
```php
<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
logout_user(get_db());
```

- [ ] **Step 6: Dashboard shell**

Replace the entire contents of `retention/src/pages/dashboard.php` with:
```php
<?php
require_once __DIR__ . '/../config/database.php';
$page_title = 'Dashboard';
$active_nav = 'dashboard';
require __DIR__ . '/../includes/layout_header.php';
$pdo = $__pdo;

$totalCategories = (int) $pdo->query("SELECT COUNT(*) c FROM data_categories WHERE deleted_at IS NULL")->fetch()['c'];
$totalRecords    = (int) $pdo->query("SELECT COUNT(*) c FROM data_records WHERE deleted_at IS NULL")->fetch()['c'];
$dueReview       = (int) $pdo->query("SELECT COUNT(*) c FROM data_records WHERE status='due_review'")->fetch()['c'];
?>
<div class="row g-3">
  <div class="col-md-4"><div class="card shadow-sm"><div class="card-body">
    <h5 class="card-title text-muted">Categories</h5><p class="display-6 mb-0"><?= $totalCategories ?></p></div></div></div>
  <div class="col-md-4"><div class="card shadow-sm"><div class="card-body">
    <h5 class="card-title text-muted">Records</h5><p class="display-6 mb-0"><?= $totalRecords ?></p></div></div></div>
  <div class="col-md-4"><div class="card shadow-sm"><div class="card-body">
    <h5 class="card-title text-muted">Due for review</h5><p class="display-6 mb-0"><?= $dueReview ?></p></div></div></div>
</div>
<div class="card shadow-sm mt-3"><div class="card-body">
  <h2 class="h5">Welcome, <?= escape_html($__user['name']) ?></h2>
  <p class="text-muted mb-0">ADRS Core foundation is live. Modules will appear in the sidebar as they are built.</p>
</div></div>
<?php require __DIR__ . '/../includes/layout_footer.php'; ?>
```

- [ ] **Step 7: Front controller**

Replace the entire contents of `retention/index.php` with:
```php
<?php
require_once __DIR__ . '/src/config/database.php';
date_default_timezone_set(TIMEZONE);
ini_set('display_errors', SHOW_ERRORS ? '1' : '0');
session_name(SESSION_NAME);
session_set_cookie_params([
    'lifetime' => 0, 'path' => '/',
    'secure' => (APP_ENV === 'production'), 'httponly' => true, 'samesite' => 'Strict',
]);
require_once __DIR__ . '/src/includes/auth.php';
redirect(APP_URL . (is_logged_in() ? '/src/pages/dashboard.php' : '/src/pages/login.php'));
```

- [ ] **Step 8: Error pages**

Create `retention/404.php`:
```php
<?php http_response_code(404); ?>
<!doctype html><html><head><meta charset="utf-8"><title>Not Found</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
<body class="text-center p-5"><h1 class="display-4">404</h1><p>Page not found.</p>
<a class="btn btn-primary" href="/retention/">Back to ADRS</a></body></html>
```
Create `retention/500.php`:
```php
<?php http_response_code(500); ?>
<!doctype html><html><head><meta charset="utf-8"><title>Error</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
<body class="text-center p-5"><h1 class="display-4">Something went wrong</h1>
<p>Please try again later or contact support@3consult-ng.com.</p></body></html>
```

- [ ] **Step 9: Manual smoke test**

Run (from `retention/`): `php -S localhost:8080`
Then in a browser:
1. Visit `http://localhost:8080/index.php` → redirects to login.
2. Log in with `admin@3consult-ng.com` / `password` → lands on the dashboard shell with sidebar + counts.
3. Confirm the sidebar shows Users + Settings (admin-only) links.
4. Click Logout → returns to login; visiting `dashboard.php` directly now redirects to login.

> Requires the `adrs` dev DB imported with `schema.sql` + `seed_gdpr_ndpr.sql` and a valid `config.local.php`. If login fails, confirm the seeded admin hash corresponds to `password` (re-hash and UPDATE if the seed hash differs).

- [ ] **Step 10: Run the full suite once more, then commit**

Run: `php tests/run.php`
Expected: `Failed: 0`.
```bash
git add retention/src/assets/css/app.css retention/src/includes/layout_header.php retention/src/includes/layout_footer.php retention/src/pages/login.php retention/src/pages/logout.php retention/src/pages/dashboard.php retention/index.php retention/404.php retention/500.php
git commit -m "feat(ui): branded layout shell, login, dashboard shell, front controller, error pages"
```

---

## Milestone 1A — Definition of Done

- [ ] `php tests/run.php` exits 0 with all assertions passing (harness, db, helpers ×3, auth).
- [ ] Manual: log in as admin → dashboard shell; role-aware sidebar; logout works; protected pages redirect when logged out.
- [ ] `get_setting()` uses `setting_key/setting_value` (bug fixed); `get_db()` + constants in place (blueprint-aligned).
- [ ] Secrets (`config.local.php`, `config.test.php`) are gitignored and uncommitted.
- [ ] All work committed on `adrs-core-rebuild` in small commits.

**Next milestone (1B):** Categories CRUD (full fields incl. `requires_dual_approval`, `disposal_trigger`, `legal_basis`, `owner_id`) + Records lifecycle (capturing purpose/lawful basis/owner; `get_category.php` AJAX). Plan written after 1A is green.

---

## Self-Review

**Spec coverage (vs design §6, §7.2 item 1–2):** Foundation (config/db/helpers/auth/layout/front controller/error pages) ✔; auth & login ✔; test harness (design §10) ✔; `get_setting` bug fix ✔; blueprint API alignment (`get_db`, constants) ✔. Users CRUD and forgot/reset *pages* are deferred to 1B/auth-pages (token *functions* done here) — noted, not a gap for 1A.

**Placeholder scan:** No TBD/TODO; every code step contains full code; commands have expected output. ✔

**Type/name consistency:** `get_db()`, `get_setting($pdo,$key,$default)`, `csrf_verify()`, `csrf_field()`, `flash()/get_flash()/render_flash()`, `log_audit($pdo,$action,$entity_type,$entity_id,$performed_by,$details,$ip)`, `login_user($pdo,$email,$password)`, `require_role(...$roles)`, `has_role(...)`, `create_password_reset_token/validate_reset_token/consume_reset_token` — names are consistent across tasks and match the header conventions. Layout uses `$__pdo`/`$__user`; dashboard reads `$__pdo`. ✔
