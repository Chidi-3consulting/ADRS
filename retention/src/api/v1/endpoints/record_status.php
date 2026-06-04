<?php
$pdo = get_pdo();
verify_enterprise_tier($pdo);
require_enterprise_api_enabled($pdo);
$apiKey = require_api_key($pdo);
require_permission($apiKey, 'ingest');

$payload = json_decode(file_get_contents('php://input'), true);
if (!is_array($payload) || empty($payload['record_id']) || empty($payload['status'])) {
    send_json_logged($pdo, ['error' => 'record_id and status are required'], 400, $apiKey);
}

$allowed = ['active', 'due_review', 'disposal_requested', 'legal_hold', 'disposed'];
if (!in_array($payload['status'], $allowed, true)) {
    send_json_logged($pdo, ['error' => 'Invalid status value'], 400, $apiKey);
}

$stmt = $pdo->prepare('SELECT status FROM data_records WHERE id = :id AND deleted_at IS NULL LIMIT 1');
$stmt->execute(['id' => $payload['record_id']]);
$existing = $stmt->fetch(PDO::FETCH_ASSOC);
if ($existing === false) {
    send_json_logged($pdo, ['error' => 'Record not found'], 404, $apiKey);
}

$update = $pdo->prepare('UPDATE data_records SET status = :status' . ($payload['status'] === 'disposed' ? ', disposed_at = NOW(), disposed_by = NULL' : '') . ' WHERE id = :id');
$update->execute(['status' => $payload['status'], 'id' => $payload['record_id']]);

if ($payload['status'] === 'disposed' && get_setting($pdo, 'adrs_tier', 'core') === 'enterprise') {
    require_once __DIR__ . '/../../../../src/includes/enterprise_dispatch.php';
    queue_disposal_dispatch($pdo, (int)$payload['record_id'], 'delete');
}

send_json_logged($pdo, ['status' => 'ok'], 200, $apiKey);
