<?php
/**
 * Application configuration. Loads config.local.php first (if present) so local/test
 * environments can pre-define constants; production falls back to the defaults below.
 * Secrets live in config.local.php (gitignored), NEVER here. SMTP lives in system_settings.
 */

// Load local overrides only when no profile (e.g. the test profile) has already been
// loaded — avoids double-defining constants when tests/bootstrap.php loads config.test.php.
$__local = __DIR__ . '/config.local.php';
if (!defined('APP_ENV') && is_file($__local)) { require $__local; }

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
