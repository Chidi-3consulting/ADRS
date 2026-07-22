<?php
// Shared bootstrap for the Enterprise REST API. Key-based auth, never sessions.
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/db.php';
require_once __DIR__ . '/../../includes/helpers.php';
require_once __DIR__ . '/../../includes/enterprise_lib.php';
require_once __DIR__ . '/../../includes/records_lib.php';

date_default_timezone_set(TIMEZONE);
header('Content-Type: application/json');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store, no-cache');
header('X-API-Version: 1.0');

/** Send a JSON response and stop. */
function api_response(int $status, array $data): never {
    http_response_code($status);
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

/** Decode the JSON request body (object). Returns [] when empty/invalid. */
function api_body(): array {
    $raw = file_get_contents('php://input');
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

/** Enterprise-only SaaS: API is always available. Retained for backward compatibility. */
function require_enterprise_tier(PDO $pdo): void {
    // No-op: every ADRS deployment is enterprise.
    return;
}

/** Enterprise-only SaaS: REST API is always enabled. Retained for backward compatibility. */
function require_api_enabled(PDO $pdo): void {
    // No-op: Enterprise API is always active in SaaS mode.
    return;
}
