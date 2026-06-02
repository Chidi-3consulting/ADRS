<?php
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/helpers.php';
require_once __DIR__ . '/../includes/enterprise_dispatch.php';

$pdo = get_pdo();
$pdo->beginTransaction();

try {
    $today = new DateTimeImmutable('now', new DateTimeZone('+01:00'));
    $reviewWindow = $today->modify('+30 days')->format('Y-m-d');

    // Flag date-based records approaching retention end date.
    $stmt = $pdo->prepare(
        'UPDATE data_records SET status = "due_review", review_flagged_at = NOW()
         WHERE status = "active"
           AND disposal_requested_at IS NULL
           AND legal_hold = 0
           AND disposal_requested_at IS NULL
           AND consent_withdrawn_at IS NULL
           AND retention_end_date IS NOT NULL
           AND retention_end_date <= :review_window'
    );
    $stmt->execute(['review_window' => $reviewWindow]);
    $flagged = $stmt->rowCount();

    if ($flagged > 0) {
        $stmtLog = $pdo->prepare('INSERT INTO audit_log (action, entity_type, entity_id, performed_by, details, ip_address) VALUES ("record_flagged_review", "data_record", NULL, NULL, :details, :ip)');
        $stmtLog->execute(['details' => json_encode(['count' => $flagged]), 'ip' => '127.0.0.1']);
    }

    // Consent-withdrawal based disposal support (Enterprise only if table exists)
    $stmt = $pdo->prepare(
        'UPDATE data_records SET status = "due_review"
         WHERE consent_withdrawn_at IS NOT NULL
           AND status != "disposed"
           AND consent_withdrawn_at <= :consent_threshold'
    );
    $stmt->execute(['consent_threshold' => $today->modify('-30 days')->format('Y-m-d H:i:s')]);
    $consentFlagged = $stmt->rowCount();

    if ($consentFlagged > 0) {
        $stmtLog = $pdo->prepare('INSERT INTO audit_log (action, entity_type, entity_id, performed_by, details, ip_address) VALUES ("consent_withdrawn", "data_record", NULL, NULL, :details, :ip)');
        $stmtLog->execute(['details' => json_encode(['count' => $consentFlagged]), 'ip' => '127.0.0.1']);
    }

    // Auto-dispose review records past retention end date.
    $stmt = $pdo->prepare(
        'SELECT dr.id, dr.category_id, dc.disposal_method
         FROM data_records dr
         JOIN data_categories dc ON dr.category_id = dc.id
         WHERE dr.status = "due_review"
           AND dr.legal_hold = 0
           AND dr.retention_end_date IS NOT NULL
           AND dr.retention_end_date < :today'
    );
    $stmt->execute(['today' => $today->format('Y-m-d')]);
    $records = $stmt->fetchAll();

    foreach ($records as $record) {
        $disposalMethod = $record['disposal_method'];
        $action = 'record_disposed_' . $disposalMethod;

        $update = $pdo->prepare('UPDATE data_records SET status = "disposed", disposed_at = NOW(), disposed_by = NULL WHERE id = :id');
        $update->execute(['id' => $record['id']]);

        $stmtLog = $pdo->prepare('INSERT INTO audit_log (action, entity_type, entity_id, performed_by, details, ip_address) VALUES (:action, "data_record", :entity_id, NULL, :details, :ip)');
        $stmtLog->execute(['action' => $action, 'entity_id' => $record['id'], 'details' => json_encode(['method' => $disposalMethod]), 'ip' => '127.0.0.1']);

        if (get_setting($pdo, 'adrs_tier', 'core') === 'enterprise') {
            queue_disposal_dispatch($pdo, (int)$record['id'], $disposalMethod);
        }
    }

    $pdo->commit();
} catch (Exception $e) {
    $pdo->rollBack();
    file_put_contents(__DIR__ . '/../../cron_error.log', '[' . date('c') . '] ' . $e->getMessage() . PHP_EOL, FILE_APPEND);
    http_response_code(500);
    echo 'Cron failed.';
    exit;
}

echo 'Retention cron completed successfully.';
