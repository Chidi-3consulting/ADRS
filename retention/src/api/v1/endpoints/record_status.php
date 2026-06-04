<?php
/** GET /api/v1/records/{external_ref}/status — check a record's lifecycle status. */
api_require_permission($apiKey, 'ingest');

$parts = explode('/', $route);            // records/{ref}/status  OR  records/{ref}
$idOrRef = $parts[1] ?? '';
if ($idOrRef === '') {
    api_response(422, ['error' => 'validation_error', 'message' => 'A record id or external_ref is required.']);
}

if (ctype_digit($idOrRef)) {
    $stmt = $pdo->prepare(
        "SELECT dr.*, dc.name AS category_name FROM data_records dr JOIN data_categories dc ON dc.id = dr.category_id
         WHERE dr.id = :v AND dr.deleted_at IS NULL LIMIT 1"
    );
} else {
    $stmt = $pdo->prepare(
        "SELECT dr.*, dc.name AS category_name FROM data_records dr JOIN data_categories dc ON dc.id = dr.category_id
         WHERE dr.record_reference = :v AND dr.deleted_at IS NULL ORDER BY dr.id DESC LIMIT 1"
    );
}
$stmt->execute(['v' => $idOrRef]);
$rec = $stmt->fetch();
if (!$rec) {
    api_response(404, ['error' => 'not_found', 'message' => 'No record matches that identifier.']);
}

api_response(200, [
    'record_id'          => (int) $rec['id'],
    'external_ref'       => $rec['record_reference'],
    'category'           => $rec['category_name'],
    'status'             => $rec['status'],
    'retention_end_date' => $rec['retention_end_date'],
    'legal_hold'         => (bool) $rec['legal_hold'],
    'consent_withdrawn'  => $rec['consent_withdrawn_at'] !== null,
]);
