<?php
/** POST /api/v1/records/terminate — trigger retention clock on account closure / relationship termination. */
api_require_permission($apiKey, 'ingest');

$body = api_body();
$externalRef = trim((string) ($body['external_ref'] ?? ''));
if ($externalRef === '') {
    api_response(422, ['error' => 'validation_error', 'message' => 'external_ref is required.']);
}

$terminationDate = (string) ($body['termination_date'] ?? date('Y-m-d'));
if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $terminationDate)) {
    api_response(422, ['error' => 'invalid_termination_date', 'message' => 'termination_date must be YYYY-MM-DD.']);
}

$orgId = (int) ($apiKey['organization_id'] ?? 1);

// Find active records under account_closure categories that don't have an end date yet
$stmt = $pdo->prepare(
    "SELECT dr.id, dc.name AS category_name, dc.retention_period_days, crr.retention_period_days AS rule_period_days
     FROM data_records dr
     JOIN data_categories dc ON dc.id = dr.category_id
     LEFT JOIN category_retention_rules crr ON crr.id = dr.retention_rule_id
     WHERE dr.record_reference = :ref
       AND dr.organization_id = :oid
       AND COALESCE(crr.disposal_trigger, dc.disposal_trigger) = 'account_closure'
       AND dr.retention_end_date IS NULL
       AND dr.deleted_at IS NULL
       AND dr.status != 'disposed'"
);
$stmt->execute(['ref' => $externalRef, 'oid' => $orgId]);
$rows = $stmt->fetchAll();

$updated = [];
$upStmt = $pdo->prepare("UPDATE data_records SET retention_end_date = :rend WHERE id = :id");

foreach ($rows as $row) {
    $days = $row['rule_period_days'] !== null ? (int)$row['rule_period_days'] : (int)$row['retention_period_days'];
    $rend = date('Y-m-d', strtotime($terminationDate . " + $days days"));
    
    $upStmt->execute(['rend' => $rend, 'id' => (int) $row['id']]);
    
    log_audit($pdo, 'account_terminated', 'data_record', (int) $row['id'], null, [
        'source' => 'enterprise_api',
        'external_ref' => $externalRef,
        'termination_date' => $terminationDate,
        'retention_end_date' => $rend
    ], null);
    
    $updated[] = [
        'record_id' => (int) $row['id'],
        'category' => $row['category_name'],
        'retention_end_date' => $rend
    ];
}

api_response(200, [
    'status' => 'processed',
    'external_ref' => $externalRef,
    'matched_count' => count($rows),
    'updated_records' => $updated
]);
