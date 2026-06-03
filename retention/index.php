<?php
require __DIR__ . '/src/includes/db.php';
require __DIR__ . '/src/includes/helpers.php';
require __DIR__ . '/src/includes/auth.php';

$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$base = dirname($_SERVER['SCRIPT_NAME']);
$trimmed = '/' . trim(substr($path, strlen($base)), '/');

if ($trimmed === '/login' || $trimmed === '/login.php') {
    require __DIR__ . '/src/pages/login.php';
    exit;
}

if ($trimmed === '/logout' || $trimmed === '/logout.php') {
    require __DIR__ . '/src/pages/logout.php';
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

if ($trimmed === '/integration-logs' || $trimmed === '/integration-logs/index.php') {
    require_login();
    require __DIR__ . '/src/pages/integration_logs/index.php';
    exit;
}

if ($trimmed === '/connected-systems' || $trimmed === '/connected-systems/index.php') {
    require_login();
    require __DIR__ . '/src/pages/connected_systems/index.php';
    exit;
}

if ($trimmed === '/connected-systems/create' || $trimmed === '/connected-systems/create.php') {
    require_login();
    require __DIR__ . '/src/pages/connected_systems/create.php';
    exit;
}

if ($trimmed === '/connected-systems/edit' || $trimmed === '/connected-systems/edit.php') {
    require_login();
    require __DIR__ . '/src/pages/connected_systems/edit.php';
    exit;
}

if ($trimmed === '/api-keys' || $trimmed === '/api-keys/index.php') {
    require_login();
    require __DIR__ . '/src/pages/api_keys/index.php';
    exit;
}

if ($trimmed === '/api-keys/create' || $trimmed === '/api-keys/create.php') {
    require_login();
    require __DIR__ . '/src/pages/api_keys/create.php';
    exit;
}

if ($trimmed === '/api-keys/edit' || $trimmed === '/api-keys/edit.php') {
    require_login();
    require __DIR__ . '/src/pages/api_keys/edit.php';
    exit;
}

if ($trimmed === '/intake-queue' || $trimmed === '/intake-queue/index.php') {
    require_login();
    require __DIR__ . '/src/pages/intake_queue/index.php';
    exit;
}

if ($trimmed === '/disposal-dispatch' || $trimmed === '/disposal-dispatch/index.php') {
    require_login();
    require __DIR__ . '/src/pages/disposal_dispatch/index.php';
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

if ($trimmed === '/dashboard' || $trimmed === '/dashboard.php' || $trimmed === '/') {
    require_login();
    require __DIR__ . '/src/pages/dashboard.php';
    exit;
}

http_response_code(404);
require __DIR__ . '/404.php';
