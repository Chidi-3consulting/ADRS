<?php
/** POST /api/v1/ingest/batch — capture up to 500 records in one call. */
api_require_permission($apiKey, 'batch');

$body = api_body();
$records = $body['records'] ?? null;
if (!is_array($records)) {
    api_response(422, ['error' => 'validation_error', 'message' => '"records" array is required.']);
}
if (count($records) > 500) {
    api_response(422, ['error' => 'batch_too_large', 'message' => 'A batch may contain at most 500 records.']);
}

$batchId  = uniqid('batch_', true);
$accepted = 0;
$failed   = [];

foreach ($records as $i => $rec) {
    $objectType  = trim((string) ($rec['object_type'] ?? ''));
    $externalRef = trim((string) ($rec['external_ref'] ?? ''));
    if ($externalRef === '') { $failed[] = ['index' => $i, 'external_ref' => null, 'error' => 'external_ref_required']; continue; }
    if ($objectType === '')  { $failed[] = ['index' => $i, 'external_ref' => $externalRef, 'error' => 'object_type_required']; continue; }

    $categoryId = auto_categorize($pdo, (int) $apiKey['system_id'], $objectType, $rec['metadata'] ?? []);
    if (!$categoryId) { $failed[] = ['index' => $i, 'external_ref' => $externalRef, 'error' => 'no_matching_rule']; continue; }
    if (intake_is_duplicate($pdo, $externalRef, (int) $categoryId)) { $failed[] = ['index' => $i, 'external_ref' => $externalRef, 'error' => 'duplicate_record']; continue; }

    enqueue_intake($pdo, (int) $apiKey['system_id'], (int) $apiKey['id'], $batchId, $rec);
    $accepted++;
}

api_response(202, [
    'status'   => 'queued',
    'batch_id' => $batchId,
    'accepted' => $accepted,
    'rejected' => count($failed),
    'failed'   => $failed,
]);
