<?php
function queue_disposal_dispatch(PDO $pdo, int $recordId, string $disposalMethod): void
{
    $recordStmt = $pdo->prepare('SELECT record_reference FROM data_records WHERE id = :id LIMIT 1');
    $recordStmt->execute(['id' => $recordId]);
    $record = $recordStmt->fetch(PDO::FETCH_ASSOC);
    if ($record === false) {
        return;
    }

    $systemStmt = $pdo->prepare('SELECT id, base_url FROM connected_systems WHERE is_active = 1 ORDER BY id ASC LIMIT 1');
    $systemStmt->execute();
    $system = $systemStmt->fetch(PDO::FETCH_ASSOC);
    if ($system === false) {
        return;
    }

    $endpoint = null;
    if (!empty($system['base_url'])) {
        $endpoint = rtrim($system['base_url'], '/') . '/disposal';
    }

    $payload = json_encode([
        'record_id' => $recordId,
        'record_reference' => $record['record_reference'],
        'dispatch_type' => $disposalMethod,
    ], JSON_UNESCAPED_UNICODE);

    $stmt = $pdo->prepare(
        'INSERT INTO disposal_dispatches (record_id, system_id, dispatch_type, external_ref, endpoint_url, payload, status, created_at)
         VALUES (:record_id, :system_id, :dispatch_type, :external_ref, :endpoint_url, :payload, "pending", NOW())'
    );
    $stmt->execute([
        'record_id' => $recordId,
        'system_id' => $system['id'],
        'dispatch_type' => $disposalMethod,
        'external_ref' => $record['record_reference'],
        'endpoint_url' => $endpoint,
        'payload' => $payload,
    ]);
}
