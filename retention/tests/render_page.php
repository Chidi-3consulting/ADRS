<?php
/**
 * Render a protected page in isolation (own subprocess) with a faked admin session,
 * against the adrs_test database (which the last `php tests/run.php` populated with
 * schema + seed). Prints the HTML then a ---RENDER_OK--- marker, or RENDER_ERR + exit 2.
 *
 * Usage: php tests/render_page.php <relative-page-path> [id]
 */
require __DIR__ . '/../src/config/config.test.php';
require_once __DIR__ . '/../src/includes/db.php';
require_once __DIR__ . '/../src/includes/helpers.php';
require_once __DIR__ . '/../src/includes/auth.php';

$_SESSION = ['user' => ['id' => 1, 'name' => 'Smoke Admin', 'role' => 'admin']];
$_SERVER['REQUEST_METHOD'] = 'GET';
if (isset($argv[2])) { $_GET['id'] = $argv[2]; }

$page = __DIR__ . '/../' . $argv[1];
ob_start();
try {
    include $page;
} catch (Throwable $e) {
    ob_end_clean();
    fwrite(STDERR, 'RENDER_ERR: ' . $e->getMessage() . "\n");
    exit(2);
}
$html = ob_get_clean();
echo $html;
echo "\n---RENDER_OK---\n";
