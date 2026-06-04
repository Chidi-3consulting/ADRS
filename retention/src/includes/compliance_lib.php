<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';

/**
 * Phase 3 compliance modules: RoPA (Article 30), DPIA (risk scoring), data-breach
 * register (Art. 33/34 72-hour tracking), and consent receipts. Pure-ish logic with
 * thin UI pages on top; the risk/deadline/reference helpers are unit-tested.
 */

/* ----------------------------- RoPA / Article 30 ----------------------------- */

function create_ropa_entry(PDO $pdo, array $in, ?int $actor_id): int {
    $pdo->prepare(
        "INSERT INTO ropa_entries (category_id, activity_name, controller_name, controller_contact, dpo_contact,
            purpose, lawful_basis, data_subjects, data_categories, recipients, third_country_transfers,
            retention_summary, security_measures, created_by)
         VALUES (:cat,:an,:cn,:cc,:dpo,:pur,:lb,:ds,:dc,:rec,:tct,:ret,:sec,:by)"
    )->execute([
        'cat' => $in['category_id'] ?: null, 'an' => $in['activity_name'], 'cn' => $in['controller_name'] ?? null,
        'cc' => $in['controller_contact'] ?? null, 'dpo' => $in['dpo_contact'] ?? null, 'pur' => $in['purpose'] ?? null,
        'lb' => $in['lawful_basis'] ?? null, 'ds' => $in['data_subjects'] ?? null, 'dc' => $in['data_categories'] ?? null,
        'rec' => $in['recipients'] ?? null, 'tct' => $in['third_country_transfers'] ?? null,
        'ret' => $in['retention_summary'] ?? null, 'sec' => $in['security_measures'] ?? null, 'by' => $actor_id,
    ]);
    $id = (int) $pdo->lastInsertId();
    log_audit($pdo, 'export_generated', 'system', $id, $actor_id, ['ropa_entry_created' => $in['activity_name']], get_client_ip());
    return $id;
}

/**
 * Seed draft RoPA entries from every active category that doesn't yet have one.
 * Returns the number created — turns the data register into an Article 30 starting point.
 */
function generate_ropa_from_categories(PDO $pdo, ?int $actor_id): int {
    $cats = $pdo->query(
        "SELECT c.* FROM data_categories c
         WHERE c.deleted_at IS NULL AND c.is_active = 1
           AND NOT EXISTS (SELECT 1 FROM ropa_entries r WHERE r.category_id = c.id)"
    )->fetchAll();
    $n = 0;
    foreach ($cats as $c) {
        create_ropa_entry($pdo, [
            'category_id' => $c['id'], 'activity_name' => $c['name'],
            'purpose' => $c['description'], 'lawful_basis' => get_legal_basis_label($c['legal_basis']),
            'retention_summary' => $c['retention_period_label'],
        ], $actor_id);
        $n++;
    }
    return $n;
}

/* ----------------------------- DPIA ----------------------------- */

/** Map a likelihood×severity score (1–25) to a risk level. */
function dpia_risk_level(int $likelihood, int $severity): string {
    $score = $likelihood * $severity;
    if ($score <= 6) { return 'low'; }
    if ($score <= 14) { return 'medium'; }
    return 'high';
}

function create_dpia(PDO $pdo, array $in, ?int $actor_id): int {
    $likelihood = max(1, min(5, (int) ($in['likelihood_score'] ?? 1)));
    $severity   = max(1, min(5, (int) ($in['severity_score'] ?? 1)));
    $risk = $likelihood * $severity;
    $pdo->prepare(
        "INSERT INTO dpia_assessments (title, category_id, description, necessity_score, proportionality_score,
            likelihood_score, severity_score, risk_score, risk_level, mitigation, status, assessed_by)
         VALUES (:t,:cat,:d,:nec,:prop,:lik,:sev,:rs,:rl,:mit,'draft',:by)"
    )->execute([
        't' => $in['title'], 'cat' => $in['category_id'] ?: null, 'd' => $in['description'] ?? null,
        'nec' => max(1, min(5, (int) ($in['necessity_score'] ?? 1))), 'prop' => max(1, min(5, (int) ($in['proportionality_score'] ?? 1))),
        'lik' => $likelihood, 'sev' => $severity, 'rs' => $risk, 'rl' => dpia_risk_level($likelihood, $severity),
        'mit' => $in['mitigation'] ?? null, 'by' => $actor_id,
    ]);
    $id = (int) $pdo->lastInsertId();
    log_audit($pdo, 'export_generated', 'system', $id, $actor_id, ['dpia_created' => $in['title'], 'risk' => $risk], get_client_ip());
    return $id;
}

function set_dpia_status(PDO $pdo, int $id, string $status, ?int $actor_id): void {
    if (!in_array($status, ['draft','in_review','approved','rejected'], true)) { throw new InvalidArgumentException('Bad status'); }
    $approved = $status === 'approved';
    $pdo->prepare("UPDATE dpia_assessments SET status=:s, approved_by=:by, approved_at=" . ($approved ? 'NOW()' : 'NULL') . " WHERE id=:id")
        ->execute(['s' => $status, 'by' => $approved ? $actor_id : null, 'id' => $id]);
    log_audit($pdo, 'export_generated', 'system', $id, $actor_id, ['dpia_status' => $status], get_client_ip());
}

/* ----------------------------- Breach register (Art. 33/34) ----------------------------- */

/** Next breach reference BR-YYYY-NNNN. */
function generate_breach_reference(PDO $pdo): string {
    $year = date('Y');
    $n = ((int) $pdo->query("SELECT COUNT(*) FROM breach_incidents WHERE YEAR(created_at) = $year")->fetchColumn()) + 1;
    return sprintf('BR-%s-%04d', $year, $n);
}

/** 72-hour notification deadline from a discovery datetime. */
function breach_notify_deadline(string $discovered_at): string {
    return date('Y-m-d H:i:s', strtotime($discovered_at . ' +72 hours'));
}

/** Whole hours remaining until a breach's 72h deadline (negative if past). */
function breach_hours_remaining(string $deadline, ?int $now = null): int {
    return (int) floor(((strtotime($deadline)) - ($now ?? time())) / 3600);
}

function create_breach(PDO $pdo, array $in, ?int $actor_id): array {
    $ref = generate_breach_reference($pdo);
    $discovered = $in['discovered_at'] ?: date('Y-m-d H:i:s');
    $deadline = breach_notify_deadline($discovered);
    $pdo->prepare(
        "INSERT INTO breach_incidents (reference, title, description, discovered_at, occurred_at, severity,
            affected_records, status, notify_deadline, reported_by)
         VALUES (:ref,:t,:d,:disc,:occ,:sev,:aff,'open',:dl,:by)"
    )->execute([
        'ref' => $ref, 't' => $in['title'], 'd' => $in['description'] ?? null, 'disc' => $discovered,
        'occ' => $in['occurred_at'] ?: null, 'sev' => $in['severity'] ?? 'medium',
        'aff' => isset($in['affected_records']) && $in['affected_records'] !== '' ? (int) $in['affected_records'] : null,
        'dl' => $deadline, 'by' => $actor_id,
    ]);
    $id = (int) $pdo->lastInsertId();
    log_audit($pdo, 'export_generated', 'system', $id, $actor_id, ['breach_logged' => $ref, 'severity' => $in['severity'] ?? 'medium'], get_client_ip());
    return ['id' => $id, 'reference' => $ref, 'notify_deadline' => $deadline];
}

function update_breach_status(PDO $pdo, int $id, string $status, ?int $actor_id): void {
    if (!in_array($status, ['open','contained','notified','closed'], true)) { throw new InvalidArgumentException('Bad status'); }
    $extra = $status === 'notified' ? ', notified_authority_at = NOW()' : '';
    $pdo->prepare("UPDATE breach_incidents SET status=:s$extra WHERE id=:id")->execute(['s' => $status, 'id' => $id]);
    log_audit($pdo, 'export_generated', 'system', $id, $actor_id, ['breach_status' => $status], get_client_ip());
}

/* ----------------------------- Consent receipts ----------------------------- */

function issue_consent_receipt(PDO $pdo, array $in, ?int $actor_id): array {
    $given = $in['given_at'] ?: date('Y-m-d H:i:s');
    $hash = hash('sha256', implode('|', [$in['data_subject_ref'], $in['purpose'], $given, bin2hex(random_bytes(8))]));
    $pdo->prepare(
        "INSERT INTO consent_receipts (record_id, data_subject_ref, purpose, lawful_basis, channel, given_at, receipt_hash, created_by)
         VALUES (:rid,:dsr,:pur,:lb,:ch,:ga,:h,:by)"
    )->execute([
        'rid' => $in['record_id'] ?: null, 'dsr' => $in['data_subject_ref'], 'pur' => $in['purpose'],
        'lb' => $in['lawful_basis'] ?? null, 'ch' => $in['channel'] ?? null, 'ga' => $given, 'h' => $hash, 'by' => $actor_id,
    ]);
    $id = (int) $pdo->lastInsertId();
    log_audit($pdo, 'export_generated', 'system', $id, $actor_id, ['consent_receipt' => $in['data_subject_ref']], get_client_ip());
    return ['id' => $id, 'receipt_hash' => $hash];
}

function withdraw_consent_receipt(PDO $pdo, int $id, ?int $actor_id): void {
    $pdo->prepare("UPDATE consent_receipts SET withdrawn_at = NOW() WHERE id = :id AND withdrawn_at IS NULL")->execute(['id' => $id]);
    log_audit($pdo, 'export_generated', 'system', $id, $actor_id, ['consent_receipt_withdrawn' => $id], get_client_ip());
}
