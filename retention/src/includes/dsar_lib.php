<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/notifications_lib.php';

/** DSAR (Data Subject Access Request) lifecycle (C1). */

/**
 * Create a DSAR. $in: request_type, compliance_framework, data_subject_name, data_subject_email,
 * data_subject_phone, data_subject_type, received_date, description, assigned_to.
 * Auto-generates reference and a +30-day due date. Returns ['id'=>, 'reference'=>].
 */
function create_dsar(PDO $pdo, array $in, int $actor_id): array {
    $received = ($in['received_date'] ?? '') !== '' ? $in['received_date'] : date('Y-m-d');
    $reference = generate_dsar_reference($pdo);
    $due = calculate_dsar_due_date($received);

    $stmt = $pdo->prepare(
        "INSERT INTO dsar_requests
           (reference, request_type, compliance_framework, data_subject_name, data_subject_email,
            data_subject_phone, data_subject_type, received_date, due_date, status, assigned_to, description, created_by)
         VALUES (:ref,:rt,:fw,:name,:email,:phone,:dst,:recv,:due,'open',:assigned,:descr,:by)"
    );
    $stmt->execute([
        'ref' => $reference, 'rt' => $in['request_type'] ?? 'access', 'fw' => $in['compliance_framework'] ?? 'GDPR',
        'name' => $in['data_subject_name'] ?? '', 'email' => ($in['data_subject_email'] ?? '') ?: null,
        'phone' => ($in['data_subject_phone'] ?? '') ?: null, 'dst' => ($in['data_subject_type'] ?? '') ?: null,
        'recv' => $received, 'due' => $due, 'assigned' => ($in['assigned_to'] ?? '') ?: null,
        'descr' => ($in['description'] ?? '') ?: null, 'by' => $actor_id,
    ]);
    $id = (int) $pdo->lastInsertId();
    log_audit($pdo, 'dsar_created', 'dsar', $id, $actor_id, ['reference' => $reference, 'type' => $in['request_type'] ?? 'access'], get_client_ip());
    notify_role($pdo, ['dpo', 'admin'], 'dsar_received', "New DSAR: $reference", "A new DSAR ($reference) is due by $due.");
    return ['id' => $id, 'reference' => $reference];
}

function fetch_dsar(PDO $pdo, int $id): ?array {
    $stmt = $pdo->prepare("SELECT * FROM dsar_requests WHERE id=:id LIMIT 1");
    $stmt->execute(['id' => $id]);
    $row = $stmt->fetch();
    return $row === false ? null : $row;
}

/** Update DSAR status. Stamps completed_at when moving to completed; audits transitions. */
function update_dsar_status(PDO $pdo, int $id, string $status, int $actor_id, ?string $note = null): void {
    $valid = ['open','identity_check','in_progress','completed','rejected','extended'];
    if (!in_array($status, $valid, true)) { throw new InvalidArgumentException('Invalid DSAR status.'); }
    $completed = $status === 'completed' ? 'completed_at = NOW(),' : '';
    $pdo->prepare("UPDATE dsar_requests SET status=:s, {$completed} response_notes = COALESCE(:n, response_notes) WHERE id=:id")
        ->execute(['s' => $status, 'n' => $note, 'id' => $id]);
    $action = $status === 'completed' ? 'dsar_completed' : 'dsar_updated';
    log_audit($pdo, $action, 'dsar', $id, $actor_id, ['status' => $status], get_client_ip());
}

/** Mark the data subject's identity as verified. */
function verify_dsar_identity(PDO $pdo, int $id, int $actor_id): void {
    $pdo->prepare("UPDATE dsar_requests SET identity_verified=1, identity_verified_at=NOW(), identity_verified_by=:by WHERE id=:id")
        ->execute(['by' => $actor_id, 'id' => $id]);
    log_audit($pdo, 'dsar_updated', 'dsar', $id, $actor_id, ['identity_verified' => true], get_client_ip());
}
