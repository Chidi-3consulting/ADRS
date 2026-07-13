<?php
/** POST /api/v1/records/disposed — outbound disposal confirmation webhook callback. */
api_require_permission($apiKey, 'ingest');

$body = api_body();
$externalRef = trim((string) ($body['external_ref'] ?? ''));
if ($externalRef === '') {
    api_response(422, ['error' => 'validation_error', 'message' => 'external_ref is required.']);
}

$orgId = (int) ($apiKey['organization_id'] ?? 1);

// Find matching records
$stmt = $pdo->prepare(
    "SELECT id, status FROM data_records
     WHERE record_reference = :ref AND organization_id = :oid AND deleted_at IS NULL"
);
$stmt->execute(['ref' => $externalRef, 'oid' => $orgId]);
$rows = $stmt->fetchAll();

if (empty($rows)) {
    api_response(404, ['error' => 'not_found', 'message' => 'No active record matched this reference.']);
}

require_once __DIR__ . '/../../../engine/engine_lib.php';

$disposed = 0;
foreach ($rows as $row) {
    if (execute_disposal($pdo, $row)) {
        $disposed++;
    }
}

api_response(200, [
    'status' => 'processed',
    'external_ref' => $externalRef,
    'matched_count' => count($rows),
    'disposed_count' => $disposed
]);
