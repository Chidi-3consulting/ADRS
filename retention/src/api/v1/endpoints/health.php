<?php
$pdo = get_pdo();
verify_enterprise_tier($pdo);
require_enterprise_api_enabled($pdo);
$apiKey = require_api_key($pdo);
require_permission($apiKey, 'health');

try {
    $stmt = $pdo->query('SELECT 1');
    $stmt->fetch();
    send_json_logged($pdo, ['status' => 'ok', 'tier' => get_setting($pdo, 'adrs_tier', 'core')], 200, $apiKey);
} catch (Exception $e) {
    send_json_logged($pdo, ['status' => 'error', 'message' => $e->getMessage()], 500, $apiKey);
}
