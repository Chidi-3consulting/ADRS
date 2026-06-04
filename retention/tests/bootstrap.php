<?php
/**
 * Test bootstrap: defines test-DB constants, then attempts to (re)create the adrs_test
 * database from schema.sql + seed. If no MySQL server is reachable, sets
 * $GLOBALS['DB_AVAILABLE'] = false so DB-dependent test files skip cleanly instead of
 * erroring. The SAME `php tests/run.php` command runs everything once MySQL is up.
 */
require __DIR__ . '/../src/config/config.test.php';
require_once __DIR__ . '/../src/includes/db.php';
require_once __DIR__ . '/../src/includes/helpers.php';
require_once __DIR__ . '/../src/includes/auth.php';

$GLOBALS['DB_AVAILABLE'] = false;

/** Drop/recreate the test DB and import schema (+ seed). Returns the PDO handle. */
function reset_test_db(): PDO {
    $dsn = sprintf('mysql:host=%s;port=%s;charset=%s', DB_HOST, DB_PORT, DB_CHARSET);
    $root = new PDO($dsn, DB_USER, DB_PASS, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $root->exec("DROP DATABASE IF EXISTS `" . DB_NAME . "`");
    $root->exec("CREATE DATABASE `" . DB_NAME . "` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $pdo = get_db();
    $pdo->exec(file_get_contents(__DIR__ . '/../sql/schema.sql'));
    $seed = __DIR__ . '/../sql/seed_gdpr_ndpr.sql';
    if (is_file($seed)) { $pdo->exec(file_get_contents($seed)); }
    return $pdo;
}

try {
    reset_test_db();
    $GLOBALS['DB_AVAILABLE'] = true;
} catch (Throwable $e) {
    echo "\n\033[33m[bootstrap] No MySQL reachable (" . $e->getMessage() . ").\033[0m\n";
    echo "\033[33m[bootstrap] DB-backed tests will be SKIPPED. Start MySQL on "
       . DB_HOST . ":" . DB_PORT . " and re-run `php tests/run.php` for full verification.\033[0m\n";
}

/** Helper used at the top of DB-dependent test files. */
function require_db(string $label): bool {
    if (empty($GLOBALS['DB_AVAILABLE'])) {
        test_skip("$label — no database available");
        return false;
    }
    return true;
}
