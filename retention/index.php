<?php
// Under PHP's built-in server (local dev/testing), serve existing static files directly
// so CSS/JS/images and src/api/*.php resolve instead of being swallowed by the router.
if (PHP_SAPI === 'cli-server') {
    $reqFile = __DIR__ . parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
    if (is_file($reqFile)) { return false; }
}

require __DIR__ . '/src/includes/db.php';
require __DIR__ . '/src/includes/helpers.php';
require __DIR__ . '/src/includes/auth.php';

send_security_headers();

$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$base = dirname($_SERVER['SCRIPT_NAME']);
$trimmed = '/' . trim(substr($path, strlen($base)), '/');

if ($trimmed === '/healthz' || $trimmed === '/health') {
    require __DIR__ . '/src/pages/healthz.php';
    exit;
}

if ($trimmed === '/login' || $trimmed === '/login.php') {
    require __DIR__ . '/src/pages/login.php';
    exit;
}

if ($trimmed === '/logout' || $trimmed === '/logout.php') {
    require __DIR__ . '/src/pages/logout.php';
    exit;
}

if ($trimmed === '/login/2fa') {
    require __DIR__ . '/src/pages/twofa_challenge.php';
    exit;
}

if ($trimmed === '/settings/2fa') {
    require_login();
    require __DIR__ . '/src/pages/settings/twofa.php';
    exit;
}

if ($trimmed === '/forgot_password' || $trimmed === '/forgot_password.php') {
    require __DIR__ . '/src/pages/forgot_password.php';
    exit;
}

if ($trimmed === '/reset_password' || $trimmed === '/reset_password.php') {
    require __DIR__ . '/src/pages/reset_password.php';
    exit;
}

if ($trimmed === '/help' || $trimmed === '/help.php') {
    require_login();
    require __DIR__ . '/src/pages/help.php';
    exit;
}

if ($trimmed === '/categories' || $trimmed === '/categories/index.php') {
    require_login();
    require __DIR__ . '/src/pages/categories/index.php';
    exit;
}

if ($trimmed === '/categories/create' || $trimmed === '/categories/create.php') {
    require_login();
    require __DIR__ . '/src/pages/categories/create.php';
    exit;
}

if ($trimmed === '/categories/edit' || $trimmed === '/categories/edit.php') {
    require_login();
    require __DIR__ . '/src/pages/categories/edit.php';
    exit;
}

if ($trimmed === '/categories/view' || $trimmed === '/categories/view.php') {
    require_login();
    require __DIR__ . '/src/pages/categories/view.php';
    exit;
}

if ($trimmed === '/categories/delete' || $trimmed === '/categories/delete.php') {
    require_login();
    require __DIR__ . '/src/pages/categories/delete.php';
    exit;
}

if ($trimmed === '/records' || $trimmed === '/records/index.php') {
    require_login();
    require __DIR__ . '/src/pages/records/index.php';
    exit;
}

if ($trimmed === '/records/create' || $trimmed === '/records/create.php') {
    require_login();
    require __DIR__ . '/src/pages/records/create.php';
    exit;
}

if ($trimmed === '/records/edit' || $trimmed === '/records/edit.php') {
    require_login();
    require __DIR__ . '/src/pages/records/edit.php';
    exit;
}

if ($trimmed === '/records/view' || $trimmed === '/records/view.php') {
    require_login();
    require __DIR__ . '/src/pages/records/view.php';
    exit;
}

if ($trimmed === '/records/reassign' || $trimmed === '/records/reassign.php') {
    require_login();
    require __DIR__ . '/src/pages/records/reassign.php';
    exit;
}

foreach (['dispose','approve','legal_hold','consent'] as $__act) {
    if ($trimmed === '/records/' . $__act || $trimmed === '/records/' . $__act . '.php') {
        require_login();
        require __DIR__ . '/src/pages/records/' . $__act . '.php';
        exit;
    }
}

if ($trimmed === '/dsar' || $trimmed === '/dsar/index.php') {
    require_login();
    require __DIR__ . '/src/pages/dsar/index.php';
    exit;
}

if ($trimmed === '/dsar/create' || $trimmed === '/dsar/create.php') {
    require_login();
    require __DIR__ . '/src/pages/dsar/create.php';
    exit;
}

if ($trimmed === '/dsar/view' || $trimmed === '/dsar/view.php') {
    require_login();
    require __DIR__ . '/src/pages/dsar/view.php';
    exit;
}

if ($trimmed === '/notifications' || $trimmed === '/notifications/index.php') {
    require_login();
    require __DIR__ . '/src/pages/notifications/index.php';
    exit;
}

if ($trimmed === '/attachments/upload' || $trimmed === '/attachments/upload.php') {
    require_login();
    require __DIR__ . '/src/pages/attachments/upload.php';
    exit;
}

if ($trimmed === '/attachments/download' || $trimmed === '/attachments/download.php') {
    require_login();
    require __DIR__ . '/src/pages/attachments/download.php';
    exit;
}

if ($trimmed === '/attachments' || $trimmed === '/attachments/index.php') {
    require_login();
    require __DIR__ . '/src/pages/attachments/index.php';
    exit;
}


if ($trimmed === '/audit' || $trimmed === '/audit/index.php') {
    require_login();
    require __DIR__ . '/src/pages/audit/index.php';
    exit;
}

if ($trimmed === '/audit/export' || $trimmed === '/audit/export.php') {
    require_login();
    require __DIR__ . '/src/pages/audit/export.php';
    exit;
}

if ($trimmed === '/settings' || $trimmed === '/settings/index.php') {
    require_login();
    require __DIR__ . '/src/pages/settings/index.php';
    exit;
}

if ($trimmed === '/webhooks' || $trimmed === '/webhooks/index.php') {
    require_login();
    require __DIR__ . '/src/pages/webhooks/index.php';
    exit;
}

if ($trimmed === '/users' || $trimmed === '/users/index.php') {
    require_login();
    require __DIR__ . '/src/pages/users/index.php';
    exit;
}

if ($trimmed === '/users/create' || $trimmed === '/users/create.php') {
    require_login();
    require __DIR__ . '/src/pages/users/create.php';
    exit;
}

if ($trimmed === '/users/edit' || $trimmed === '/users/edit.php') {
    require_login();
    require __DIR__ . '/src/pages/users/edit.php';
    exit;
}

if ($trimmed === '/recalculations' || $trimmed === '/recalculations/index.php') {
    require_login();
    require __DIR__ . '/src/pages/recalculations/index.php';
    exit;
}

if ($trimmed === '/import' || $trimmed === '/import/index.php') {
    require_login();
    require __DIR__ . '/src/pages/import/index.php';
    exit;
}

if ($trimmed === '/notifications/mark_read' || $trimmed === '/notifications/mark_read.php') {
    require_login();
    require __DIR__ . '/src/pages/notifications/mark_read.php';
    exit;
}

// --- Enterprise integration management (Phase 2) ---
$integrationRoutes = [
    '/integrations'                 => 'integrations/index.php',
    '/integrations/systems'         => 'integrations/systems/index.php',
    '/integrations/systems/create'  => 'integrations/systems/create.php',
    '/integrations/systems/edit'    => 'integrations/systems/edit.php',
    '/integrations/keys'            => 'integrations/keys/index.php',
    '/integrations/keys/create'     => 'integrations/keys/create.php',
    '/integrations/keys/revoke'     => 'integrations/keys/revoke.php',
    '/integrations/rules'           => 'integrations/rules/index.php',
    '/integrations/rules/create'    => 'integrations/rules/create.php',
    '/integrations/rules/delete'    => 'integrations/rules/delete.php',
    '/integrations/mappings'        => 'integrations/mappings/index.php',
    '/integrations/mappings/create' => 'integrations/mappings/create.php',
    '/integrations/mappings/delete' => 'integrations/mappings/delete.php',
    '/integrations/logs'            => 'integrations/logs/index.php',
    '/integrations/queue'           => 'integrations/queue/index.php',
    '/integrations/dispatch'        => 'integrations/dispatch/index.php',
    '/integrations/tier'            => 'integrations/tier.php',
];
if (isset($integrationRoutes[$trimmed])) {
    require_login();
    require __DIR__ . '/src/pages/' . $integrationRoutes[$trimmed];
    exit;
}

// --- Phase 3 compliance modules ---
$complianceRoutes = [
    '/ropa'                    => 'ropa/index.php',
    '/ropa/create'             => 'ropa/create.php',
    '/dpia'                    => 'dpia/index.php',
    '/dpia/create'             => 'dpia/create.php',
    '/breaches'                => 'breaches/index.php',
    '/breaches/create'         => 'breaches/create.php',
    '/consent-receipts'        => 'consent_receipts/index.php',
    '/consent-receipts/create' => 'consent_receipts/create.php',
    '/reports'                 => 'reports/index.php',
];
if (isset($complianceRoutes[$trimmed])) {
    require_login();
    require __DIR__ . '/src/pages/' . $complianceRoutes[$trimmed];
    exit;
}

if ($trimmed === '/dashboard' || $trimmed === '/dashboard.php' || $trimmed === '/') {
    require_login();
    require __DIR__ . '/src/pages/dashboard.php';
    exit;
}

http_response_code(404);
require __DIR__ . '/404.php';
