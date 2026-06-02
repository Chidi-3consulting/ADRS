<?php
$pdo = get_pdo();
verify_enterprise_tier($pdo);
require_enterprise_api_enabled($pdo);
$apiKey = require_api_key($pdo);
require_permission($apiKey, 'consent');

$payload = json_decode(file_get_contents('php://input'), true);
if (!is_array($payload)) {
    send_json_logged($pdo, ['error' => 'Invalid JSON payload'], 400, $apiKey);
}

$recordId = !empty($payload['record_id']) ? (int)$payload['record_id'] : null;
$externalRef = trim($payload['external_ref'] ?? '');

if ($recordId === null && $externalRef === '') {
    send_json_logged($pdo, ['error' => 'record_id or external_ref is required'], 400, $apiKey);
}

if ($recordId !== null) {
    $stmt = $pdo->prepare('SELECT * FROM data_records WHERE id = :id AND deleted_at IS NULL LIMIT 1');
    $stmt->execute(['id' => $recordId]);
    $record = $stmt->fetch(PDO::FETCH_ASSOC);
} else {
    $stmt = $pdo->prepare('SELECT * FROM data_records WHERE record_reference = :reference AND deleted_at IS NULL LIMIT 1');
    $stmt->execute(['reference' => $externalRef]);
    $record = $stmt->fetch(PDO::FETCH_ASSOC);
}

if ($record === false) {
    send_json_logged($pdo, ['error' => 'Record not found'], 404, $apiKey);
}

$update = $pdo->prepare('UPDATE data_records SET consent_withdrawn_at = NOW(), consent_withdrawn_by = NULL, status = "due_review" WHERE id = :id');
$update->execute(['id' => $record['id']]);

$signal = $pdo->prepare(
    'INSERT INTO consent_signals (system_id, external_ref, signal_type, category_id, record_id, raw_payload, status, processed_at, created_at)
     VALUES (:system_id, :external_ref, :signal_type, :category_id, :record_id, :raw_payload, "processed", NOW(), NOW())'
);
$signal->execute([
    'system_id' => $apiKey['system_id'],
    'external_ref' => $externalRef !== '' ? $externalRef : $record['record_reference'],
    'signal_type' => 'withdrawal',
    'category_id' => $record['category_id'],
    'record_id' => $record['id'],
    'raw_payload' => json_encode($payload, JSON_UNESCAPED_UNICODE),
]);

send_json_logged($pdo, ['status' => 'ok'], 200, $apiKey);
