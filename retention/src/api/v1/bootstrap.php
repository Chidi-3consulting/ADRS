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

/** 403 unless the deployment is on the Enterprise tier. */
function require_enterprise_tier(PDO $pdo): void {
    $tier = get_setting($pdo, 'adrs_tier', 'core');
    if ($tier !== 'enterprise') {
        api_response(403, ['error' => 'enterprise_tier_required', 'message' => 'This endpoint requires ADRS Enterprise. Current tier: ' . $tier]);
    }
}

/** 403 unless the Enterprise REST API is switched on in settings. */
function require_api_enabled(PDO $pdo): void {
    if (get_setting($pdo, 'enterprise_api_enabled', '0') !== '1') {
        api_response(403, ['error' => 'api_disabled', 'message' => 'The Enterprise REST API is disabled.']);
    }
}
