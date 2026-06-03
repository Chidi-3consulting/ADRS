<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/records_lib.php';
require_once __DIR__ . '/../engine/engine_lib.php';

/**
 * Record lifecycle actions performed by humans via the UI: legal hold (set/lift),
 * consent withdrawal (B1), and the risk-tiered disposal workflow (B5) — single-approver
 * for standard categories, two-person approval for sensitive (requires_dual_approval).
 */

/** Place a record on legal hold (suspends all disposal). Requires a documented reason. */
function set_legal_hold(PDO $pdo, int $record_id, string $reason, int $actor_id): void {
    if (trim($reason) === '') { throw new InvalidArgumentException('A documented reason is required for legal hold.'); }
    $pdo->prepare(
        "UPDATE data_records
            SET legal_hold=1, legal_hold_reason=:r, legal_hold_by=:by, legal_hold_at=NOW(), legal_hold_lifted_at=NULL
          WHERE id=:id AND deleted_at IS NULL"
    )->execute(['r' => $reason, 'by' => $actor_id, 'id' => $record_id]);
    log_audit($pdo, 'legal_hold_set', 'data_record', $record_id, $actor_id, ['reason' => $reason], get_client_ip());
}

/** Lift a legal hold. */
function lift_legal_hold(PDO $pdo, int $record_id, int $actor_id): void {
    $pdo->prepare("UPDATE data_records SET legal_hold=0, legal_hold_lifted_at=NOW() WHERE id=:id")->execute(['id' => $record_id]);
    log_audit($pdo, 'legal_hold_lifted', 'data_record', $record_id, $actor_id, null, get_client_ip());
}

/**
 * B1: log a consent withdrawal. Sets consent_withdrawn_at now and the retention end date to
 * now + consent_disposal_days (default 30). Returns the new retention end date.
 */
function log_consent_withdrawal(PDO $pdo, int $record_id, int $actor_id): string {
    $days = (int) get_setting($pdo, 'consent_disposal_days', '30');
    $end = date('Y-m-d', strtotime("+{$days} days"));
    $pdo->prepare(
        "UPDATE data_records SET consent_withdrawn_at=NOW(), consent_withdrawn_by=:by, retention_end_date=:end
          WHERE id=:id AND deleted_at IS NULL"
    )->execute(['by' => $actor_id, 'end' => $end, 'id' => $record_id]);
    log_audit($pdo, 'consent_withdrawn', 'data_record', $record_id, $actor_id, ['disposal_due' => $end], get_client_ip());
    return $end;
}

/**
 * Start a disposal. For standard categories (single approver) this disposes immediately.
 * For sensitive categories (requires_dual_approval) it records a disposal request that a
 * SECOND, DIFFERENT user must approve. Returns one of: 'disposed' | 'pending_second_approval'.
 */
function request_disposal(PDO $pdo, int $record_id, int $actor_id): string {
    $rec = fetch_record($pdo, $record_id);
    if ($rec === null) { throw new InvalidArgumentException('Record not found.'); }
    if ((int) $rec['legal_hold'] === 1) { throw new RuntimeException('Record is on legal hold.'); }
    if ($rec['status'] === 'disposed') { throw new RuntimeException('Record already disposed.'); }

    if ((int) $rec['requires_dual_approval'] === 1) {
        $pdo->prepare(
            "UPDATE data_records SET status='disposal_requested', disposal_requested_at=NOW(), disposal_requested_by=:by WHERE id=:id"
        )->execute(['by' => $actor_id, 'id' => $record_id]);
        log_audit($pdo, 'disposal_requested', 'data_record', $record_id, $actor_id, null, get_client_ip());
        return 'pending_second_approval';
    }

    execute_disposal($pdo, ['id' => $record_id], $actor_id);
    log_audit($pdo, 'disposal_request_approved', 'data_record', $record_id, $actor_id, ['single_approver' => true], get_client_ip());
    return 'disposed';
}

/**
 * B5 second approval. The approver MUST be different from the requester. On success the
 * record is disposed. Throws if not pending, or if same user attempts both steps.
 */
function approve_disposal(PDO $pdo, int $record_id, int $actor_id): void {
    $rec = fetch_record($pdo, $record_id);
    if ($rec === null) { throw new InvalidArgumentException('Record not found.'); }
    if ($rec['status'] !== 'disposal_requested') { throw new RuntimeException('No pending disposal request for this record.'); }
    if ((int) $rec['disposal_requested_by'] === $actor_id) {
        throw new RuntimeException('Dual approval requires a different user to confirm the disposal.');
    }
    if ((int) $rec['legal_hold'] === 1) { throw new RuntimeException('Record is on legal hold.'); }

    execute_disposal($pdo, ['id' => $record_id], $actor_id);
    log_audit($pdo, 'disposal_request_approved', 'data_record', $record_id, $actor_id, ['dual_approval' => true], get_client_ip());
}

/** Reject a pending disposal request, returning the record to active review. */
function reject_disposal(PDO $pdo, int $record_id, int $actor_id, string $reason): void {
    $pdo->prepare(
        "UPDATE data_records SET status='due_review', disposal_requested_at=NULL, disposal_requested_by=NULL
          WHERE id=:id AND status='disposal_requested'"
    )->execute(['id' => $record_id]);
    log_audit($pdo, 'disposal_request_rejected', 'data_record', $record_id, $actor_id, ['reason' => $reason], get_client_ip());
}
