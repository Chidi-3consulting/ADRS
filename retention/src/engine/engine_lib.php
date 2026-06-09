<?php
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/helpers.php';
require_once __DIR__ . '/../includes/tenant_lib.php';
require_once __DIR__ . '/../includes/notifications_lib.php';

/** Organisation scope for engine queries (cron sets $__cron_org_id). */
function engine_org_id(): int { return current_org_id() ?? 1; }

/**
 * Retention engine business logic (callable + testable). The CLI cron (retention_cron.php)
 * is a thin wrapper around run_retention_engine(). Every step is idempotent and safe to
 * re-run. Automated actions use performed_by = NULL in the audit log.
 *
 * THE CRITICAL SAFEGUARD (B5): records whose category requires_dual_approval are NEVER
 * auto-disposed by the engine. They are flagged for review and must be disposed by two
 * humans via the UI dual-approval workflow. There is a regression test for this.
 */

/**
 * Execute disposal of a single record. Transactional, idempotent, legal-hold-safe.
 * $record needs at least 'id'. Method/flags are re-read fresh inside to avoid races.
 * Returns true if disposed now, false if skipped (already disposed / on hold / not found).
 */
function execute_disposal(PDO $pdo, array $record, ?int $actor_id = null): bool {
    $id = (int) $record['id'];
    $pdo->beginTransaction();
    try {
        // Re-read fresh under the transaction (idempotency + race guard).
        $stmt = $pdo->prepare(
            "SELECT dr.id, dr.status, dr.legal_hold, dc.disposal_method
             FROM data_records dr JOIN data_categories dc ON dc.id = dr.category_id
             WHERE dr.id = :id FOR UPDATE"
        );
        $stmt->execute(['id' => $id]);
        $fresh = $stmt->fetch();

        if (!$fresh || $fresh['status'] === 'disposed' || (int) $fresh['legal_hold'] === 1) {
            $pdo->commit();
            return false;
        }

        $method = $fresh['disposal_method'];
        if ($method === 'anonymise') {
            $pdo->prepare(
                "UPDATE data_records
                    SET status='disposed', disposed_at=NOW(), disposed_by=:by,
                        record_reference=CONCAT('ANONYMISED-', id), data_subject_type=NULL, notes=NULL
                  WHERE id=:id"
            )->execute(['by' => $actor_id, 'id' => $id]);
        } elseif ($method === 'delete') {
            $pdo->prepare(
                "UPDATE data_records SET status='disposed', disposed_at=NOW(), disposed_by=:by, deleted_at=NOW() WHERE id=:id"
            )->execute(['by' => $actor_id, 'id' => $id]);
        } else { // archive
            $pdo->prepare(
                "UPDATE data_records SET status='disposed', disposed_at=NOW(), disposed_by=:by WHERE id=:id"
            )->execute(['by' => $actor_id, 'id' => $id]);
        }

        log_audit($pdo, 'record_disposed_' . $method, 'data_record', $id, $actor_id, ['method' => $method], get_client_ip());

        // Enterprise (E3): queue outbound disposal instructions to connected systems that synced this record.
        if (get_setting($pdo, 'adrs_tier', 'core') === 'enterprise') {
            require_once __DIR__ . '/../includes/enterprise_lib.php';
            queue_disposal_dispatch($pdo, $id, $method);
        }

        $pdo->commit();
        return true;
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) { $pdo->rollBack(); }
        if (defined('LOG_PATH')) {
            if (!is_dir(LOG_PATH)) { @mkdir(LOG_PATH, 0755, true); }
            @file_put_contents(LOG_PATH . 'cron_errors.log', '[' . date('c') . "] execute_disposal #$id: " . $e->getMessage() . PHP_EOL, FILE_APPEND);
        }
        return false;
    }
}

/** Step 2: flag date_based active records approaching their end date. Returns count flagged. */
function engine_flag_due_reviews(PDO $pdo, int $review_days): int {
    $stmt = $pdo->prepare(
        "UPDATE data_records dr
            JOIN data_categories dc ON dc.id = dr.category_id AND dc.deleted_at IS NULL AND dc.disposal_trigger='date_based'
            SET dr.status='due_review', dr.review_flagged_at=NOW()
          WHERE dr.organization_id = :org AND dr.status='active' AND dr.legal_hold=0 AND dr.deleted_at IS NULL
            AND dr.retention_end_date IS NOT NULL
            AND dr.retention_end_date <= DATE_ADD(CURDATE(), INTERVAL :days DAY)"
    );
    $stmt->execute(['org' => engine_org_id(), 'days' => $review_days]);
    $n = $stmt->rowCount();
    if ($n > 0) { log_audit($pdo, 'record_flagged_review', 'data_record', null, null, ['count' => $n], null); }
    return $n;
}

/** Step 3 (B1): dispose consent-withdrawal records whose withdrawal is >= consent_days old. */
function engine_process_consent_disposals(PDO $pdo, int $consent_days): int {
    $stmt = $pdo->prepare(
        "SELECT dr.id FROM data_records dr
            JOIN data_categories dc ON dc.id = dr.category_id AND dc.deleted_at IS NULL AND dc.disposal_trigger='consent_withdrawal'
          WHERE dr.organization_id = :org AND dr.consent_withdrawn_at IS NOT NULL AND dr.status != 'disposed'
            AND dr.legal_hold=0 AND dr.deleted_at IS NULL
            AND dr.consent_withdrawn_at <= DATE_SUB(NOW(), INTERVAL :days DAY)"
    );
    $stmt->execute(['org' => engine_org_id(), 'days' => $consent_days]);
    $n = 0;
    foreach ($stmt->fetchAll() as $r) { if (execute_disposal($pdo, $r)) { $n++; } }
    return $n;
}

/**
 * Step 4: auto-dispose overdue date_based records — SKIPPING any whose category
 * requires_dual_approval (B5 safeguard). Returns ['disposed'=>int, 'skipped_dual'=>int].
 */
function engine_auto_dispose_overdue(PDO $pdo): array {
    $stmt = $pdo->prepare(
        "SELECT dr.id, dc.requires_dual_approval
         FROM data_records dr
         JOIN data_categories dc ON dc.id = dr.category_id AND dc.deleted_at IS NULL AND dc.disposal_trigger='date_based'
         WHERE dr.organization_id = :org AND dr.status='due_review' AND dr.legal_hold=0 AND dr.deleted_at IS NULL
           AND dr.retention_end_date IS NOT NULL AND dr.retention_end_date < CURDATE()"
    );
    $stmt->execute(['org' => engine_org_id()]);
    $disposed = 0; $skipped = 0;
    foreach ($stmt->fetchAll() as $r) {
        if ((int) $r['requires_dual_approval'] === 1) {
            $skipped++;            // NEVER auto-dispose sensitive records (B5)
            continue;
        }
        if (execute_disposal($pdo, $r)) { $disposed++; }
    }
    if ($skipped > 0) { log_audit($pdo, 'record_flagged_review', 'data_record', null, null, ['dual_approval_skipped' => $skipped], null); }
    return ['disposed' => $disposed, 'skipped_dual' => $skipped];
}

/** Step 5 (B7): escalate records left in due_review beyond escalation_days. Returns count escalated. */
function engine_escalate(PDO $pdo, int $escalation_days): int {
    $stmt = $pdo->prepare(
        "SELECT id FROM data_records
          WHERE organization_id = :org AND status='due_review' AND legal_hold=0 AND deleted_at IS NULL
            AND escalation_sent_at IS NULL AND review_flagged_at IS NOT NULL
            AND review_flagged_at <= DATE_SUB(NOW(), INTERVAL :days DAY)"
    );
    $stmt->execute(['org' => engine_org_id(), 'days' => $escalation_days]);
    $ids = array_column($stmt->fetchAll(), 'id');
    if (!$ids) { return 0; }

    $place = implode(',', array_fill(0, count($ids), '?'));
    $pdo->prepare("UPDATE data_records SET escalation_sent_at=NOW() WHERE id IN ($place)")->execute($ids);
    notify_role($pdo, ['admin'], 'escalation_alert',
        '🚨 ESCALATION: ' . count($ids) . ' record(s) overdue for review',
        count($ids) . ' record(s) have been awaiting review beyond the escalation window.');
    log_audit($pdo, 'escalation_sent', 'data_record', null, null, ['count' => count($ids)], null);
    return count($ids);
}

/** Step 6 (C1): DSAR alerts for requests due in 5 days or overdue. Returns count alerted. */
function engine_dsar_alerts(PDO $pdo): int {
    $stmt = $pdo->prepare(
        "SELECT id, reference, assigned_to, due_date,
                (due_date < CURDATE()) AS overdue
         FROM dsar_requests
         WHERE organization_id = :org AND status NOT IN ('completed','rejected')
           AND ( due_date = DATE_ADD(CURDATE(), INTERVAL 5 DAY)
              OR (due_date < CURDATE() AND (extended_due_date IS NULL OR extended_due_date < CURDATE())) )"
    );
    $stmt->execute(['org' => engine_org_id()]);
    $dpos = users_with_role($pdo, 'dpo');
    $n = 0;
    foreach ($stmt->fetchAll() as $d) {
        $type = $d['overdue'] ? 'dsar_overdue' : 'dsar_due_soon';
        $subject = ($d['overdue'] ? 'OVERDUE DSAR ' : 'DSAR due soon: ') . $d['reference'];
        $recipients = $dpos;
        if ($d['assigned_to']) { $recipients[] = ['id' => $d['assigned_to']]; }
        foreach ($recipients as $u) {
            create_notification($pdo, (int) $u['id'], $type, $subject,
                'DSAR ' . $d['reference'] . ' is ' . ($d['overdue'] ? 'overdue' : 'due on ' . $d['due_date']) . '.', null, (int) $d['id']);
            $n++;
        }
        log_audit($pdo, 'notification_sent', 'dsar', (int) $d['id'], null, ['type' => $type], null);
    }
    return $n;
}

/** Step 7: notify category owners (N1: DPO fallback) about their flagged records. Returns notifications sent. */
function engine_notify_review_owners(PDO $pdo): int {
    $stmt = $pdo->prepare(
        "SELECT dr.id, dr.record_reference, dc.owner_id
         FROM data_records dr JOIN data_categories dc ON dc.id = dr.category_id
         WHERE dr.organization_id = :org AND dr.status='due_review' AND dr.deleted_at IS NULL"
    );
    $stmt->execute(['org' => engine_org_id()]);
    $rows = $stmt->fetchAll();
    if (!$rows) { return 0; }

    $byOwner = [];
    foreach ($rows as $r) { $byOwner[$r['owner_id'] ?: 0][] = $r; }
    $dpos = users_with_role($pdo, 'dpo');
    $sent = 0;
    foreach ($byOwner as $ownerId => $recs) {
        $targets = $ownerId ? [['id' => $ownerId]] : $dpos; // N1 fallback
        foreach ($targets as $t) {
            create_notification($pdo, (int) $t['id'], 'review_due',
                count($recs) . ' record(s) due for review',
                'You have ' . count($recs) . ' record(s) flagged for retention review.',
                (int) $recs[0]['id'], null, $ownerId ? false : true);
            $sent++;
        }
    }
    return $sent;
}

/** Orchestrate the full daily engine. Returns a summary of counts. */
function run_retention_engine(PDO $pdo): array {
    $reviewDays    = (int) get_setting($pdo, 'review_alert_days', '30');
    $escalationDays = (int) get_setting($pdo, 'escalation_days', '14');
    $consentDays   = (int) get_setting($pdo, 'consent_disposal_days', '30');

    $flagged   = engine_flag_due_reviews($pdo, $reviewDays);
    $consent   = engine_process_consent_disposals($pdo, $consentDays);
    $auto      = engine_auto_dispose_overdue($pdo);
    $escalated = engine_escalate($pdo, $escalationDays);
    $dsar      = engine_dsar_alerts($pdo);
    $notified  = engine_notify_review_owners($pdo);

    return [
        'flagged' => $flagged, 'consent_disposed' => $consent,
        'auto_disposed' => $auto['disposed'], 'dual_skipped' => $auto['skipped_dual'],
        'escalated' => $escalated, 'dsar_alerts' => $dsar, 'review_notifications' => $notified,
    ];
}

/** Daily housekeeping: prune rows that would otherwise grow unbounded. Returns counts. */
function run_housekeeping(PDO $pdo): array {
    $del = function (string $sql) use ($pdo): int {
        try { $s = $pdo->prepare($sql); $s->execute(); return $s->rowCount(); } catch (Throwable $e) { return 0; }
    };
    return [
        'login_attempts' => $del("DELETE FROM login_attempts WHERE created_at < DATE_SUB(NOW(), INTERVAL 7 DAY)"),
        'password_resets' => $del("DELETE FROM password_resets WHERE expires_at < DATE_SUB(NOW(), INTERVAL 7 DAY)"),
        'read_notifications' => $del("DELETE FROM notifications WHERE read_at IS NOT NULL AND created_at < DATE_SUB(NOW(), INTERVAL 180 DAY)"),
    ];
}

/**
 * Quarterly review task: summarise compliance posture and notify Admins + DPOs.
 * Returns the summary array. Records a schedule_reviews-style audit entry.
 */
function run_quarterly_review(PDO $pdo): array {
    $summary = [
        'total_categories' => (int) $pdo->query("SELECT COUNT(*) c FROM data_categories WHERE deleted_at IS NULL")->fetch()['c'],
        'on_legal_hold'    => (int) $pdo->query("SELECT COUNT(*) c FROM data_records WHERE legal_hold=1 AND deleted_at IS NULL")->fetch()['c'],
        'disposed_quarter' => (int) $pdo->query("SELECT COUNT(*) c FROM data_records WHERE status='disposed' AND disposed_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)")->fetch()['c'],
        'open_dsars'       => (int) $pdo->query("SELECT COUNT(*) c FROM dsar_requests WHERE status NOT IN ('completed','rejected')")->fetch()['c'],
        'due_review'       => (int) $pdo->query("SELECT COUNT(*) c FROM data_records WHERE status='due_review' AND deleted_at IS NULL")->fetch()['c'],
    ];
    $msg = sprintf(
        'Quarterly compliance review: %d categories, %d on legal hold, %d disposed this quarter, %d open DSARs, %d records due for review.',
        $summary['total_categories'], $summary['on_legal_hold'], $summary['disposed_quarter'], $summary['open_dsars'], $summary['due_review']
    );
    notify_role($pdo, ['admin', 'dpo'], 'quarterly_review', 'Quarterly Compliance Review', $msg);
    log_audit($pdo, 'schedule_reviewed', 'system', null, null, $summary, null);
    return $summary;
}
