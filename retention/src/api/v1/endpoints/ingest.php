<?php
$pdo = get_pdo();
verify_enterprise_tier($pdo);
require_enterprise_api_enabled($pdo);
$apiKey = require_api_key($pdo);
require_permission($apiKey, 'ingest');

$payload = json_decode(file_get_contents('php://input'), true);
if (!is_array($payload)) {
    send_json_logged($pdo, ['error' => 'Invalid JSON payload'], 400, $apiKey);
}

if (empty($payload['record_reference']) || empty($payload['collection_date'])) {
    send_json_logged($pdo, ['error' => 'record_reference and collection_date are required'], 400, $apiKey);
}

$batchId = trim($payload['batch_id'] ?? '');
$queueEnabled = get_setting($pdo, 'intake_queue_enabled', '1') === '1';

if ($queueEnabled) {
    $stmt = $pdo->prepare(
        'INSERT INTO intake_queue (system_id, api_key_id, batch_id, payload, status, created_at)
         VALUES (:system_id, :api_key_id, :batch_id, :payload, "pending", NOW())'
    );
    $stmt->execute([
        'system_id' => $apiKey['system_id'],
        'api_key_id' => $apiKey['id'],
        'batch_id' => $batchId !== '' ? $batchId : null,
        'payload' => json_encode($payload, JSON_UNESCAPED_UNICODE),
    ]);

    send_json_logged($pdo, ['status' => 'ok', 'queued' => true, 'queue_id' => (int)$pdo->lastInsertId()], 200, $apiKey);
}

if (empty($payload['category_id'])) {
    send_json_logged($pdo, ['error' => 'category_id is required for immediate ingest'], 400, $apiKey);
}

$stmt = $pdo->prepare(
    'INSERT INTO data_records (category_id, original_category_id, record_reference, data_subject_type, collection_date, retention_end_date, status, created_by)
     VALUES (:category_id, :category_id, :reference, :subject_type, :collection_date, :retention_end_date, "active", NULL)'
);
$stmt->execute([
    'category_id' => $payload['category_id'],
    'reference' => $payload['record_reference'],
    'subject_type' => $payload['data_subject_type'] ?? null,
    'collection_date' => $payload['collection_date'],
    'retention_end_date' => $payload['retention_end_date'] ?? null,
]);

send_json_logged($pdo, ['status' => 'ok', 'record_id' => (int)$pdo->lastInsertId()], 200, $apiKey);
