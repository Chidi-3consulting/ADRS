<?php
/** POST /api/v1/ingest — capture a single record from an external system. */
api_require_permission($apiKey, 'ingest');

$body = api_body();
$objectType  = trim((string) ($body['object_type'] ?? ''));
$externalRef = trim((string) ($body['external_ref'] ?? ''));
if ($objectType === '' || $externalRef === '') {
    api_response(422, ['error' => 'validation_error', 'message' => 'object_type and external_ref are required.']);
}

$collectionDate = (string) ($body['collection_date'] ?? date('Y-m-d'));
if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $collectionDate) || strtotime($collectionDate) > strtotime('today 23:59:59')) {
    api_response(422, ['error' => 'invalid_collection_date', 'message' => 'collection_date must be YYYY-MM-DD and not in the future.']);
}

$categoryId = auto_categorize($pdo, (int) $apiKey['system_id'], $objectType, $body['metadata'] ?? []);
if (!$categoryId) {
    api_response(422, ['error' => 'no_matching_rule', 'message' => 'No auto-categorisation rule matched this object_type.']);
}
if (intake_is_duplicate($pdo, $externalRef, (int) $categoryId)) {
    api_response(409, ['error' => 'duplicate_record', 'message' => 'A record with this reference already exists in the resolved category.']);
}
$category = fetch_category($pdo, (int) $categoryId);

$queueId = enqueue_intake($pdo, (int) $apiKey['system_id'], (int) $apiKey['id'], null, $body);

if (get_setting($pdo, 'intake_queue_enabled', '1') === '1') {
    api_response(202, ['status' => 'queued', 'queue_id' => $queueId, 'estimated_category' => $category['name'], 'message' => 'Record accepted for processing.']);
}

// Sync mode: process immediately.
$item = $pdo->query("SELECT * FROM intake_queue WHERE id = " . (int) $queueId)->fetch();
$res = process_intake_item($pdo, $item);
if ($res['status'] === 'completed') {
    $rec = $pdo->query("SELECT retention_end_date FROM data_records WHERE id = " . (int) $res['record_id'])->fetch();
    api_response(201, ['status' => 'created', 'record_id' => $res['record_id'], 'retention_end_date' => $rec['retention_end_date'], 'category' => $category['name']]);
}
api_response(422, ['error' => $res['error'] ?? 'processing_failed']);
