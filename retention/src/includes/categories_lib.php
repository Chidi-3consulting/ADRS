<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/notifications_lib.php';

/**
 * Data Category register business logic (B1 disposal_trigger, B2 recalculation queue,
 * B5 dual approval). Pages call these; tests target them directly.
 */

/** Fetch one non-deleted category by id, or null. */
function fetch_category(PDO $pdo, int $id): ?array {
    $stmt = $pdo->prepare("SELECT * FROM data_categories WHERE id = :id AND deleted_at IS NULL LIMIT 1");
    $stmt->execute(['id' => $id]);
    $row = $stmt->fetch();
    return $row === false ? null : $row;
}

/** Count active (non-disposed, non-deleted) records in a category. */
function count_active_records_for_category(PDO $pdo, int $category_id): int {
    $stmt = $pdo->prepare(
        "SELECT COUNT(*) c FROM data_records
         WHERE category_id = :cid AND deleted_at IS NULL AND status != 'disposed'"
    );
    $stmt->execute(['cid' => $category_id]);
    return (int) $stmt->fetch()['c'];
}

/**
 * Create a category. $in keys: name, description, compliance_framework, legal_basis,
 * retention_period_days, retention_period_label, disposal_method, disposal_trigger,
 * requires_dual_approval, owner_id, review_frequency. Returns new id.
 * Consent-withdrawal categories always store retention_period_days = 0 (B1).
 */
function create_category(PDO $pdo, array $in, int $actor_id): int {
    $trigger = $in['disposal_trigger'] === 'consent_withdrawal' ? 'consent_withdrawal' : 'date_based';
    $days = $trigger === 'consent_withdrawal' ? 0 : max(0, (int) ($in['retention_period_days'] ?? 0));

    $stmt = $pdo->prepare(
        "INSERT INTO data_categories
           (name, description, compliance_framework, legal_basis, retention_period_days,
            retention_period_label, disposal_method, disposal_trigger, requires_dual_approval,
            owner_id, review_frequency, source, is_active)
         VALUES (:name,:descr,:fw,:lb,:days,:label,:dm,:dt,:dual,:owner,:rf,'custom',1)"
    );
    $stmt->execute([
        'name'  => $in['name'],
        'descr' => $in['description'] ?? null,
        'fw'    => $in['compliance_framework'] ?? 'GDPR',
        'lb'    => $in['legal_basis'],
        'days'  => $days,
        'label' => $in['retention_period_label'] ?? ($days > 0 ? "$days days" : 'Until consent withdrawn'),
        'dm'    => $in['disposal_method'] ?? 'delete',
        'dt'    => $trigger,
        'dual'  => !empty($in['requires_dual_approval']) ? 1 : 0,
        'owner' => $in['owner_id'] ?? null,
        'rf'    => $in['review_frequency'] ?? 'quarterly',
    ]);
    $id = (int) $pdo->lastInsertId();
    log_audit($pdo, 'category_created', 'data_category', $id, $actor_id, ['name' => $in['name']], get_client_ip());
    return $id;
}

/**
 * B2: when the retention period changes, DO NOT mutate record dates. Instead queue every
 * affected date_based record into pending_recalculations for DPO review. Returns rows queued.
 */
function queue_recalculations(PDO $pdo, int $category_id, int $new_days, int $actor_id): int {
    $stmt = $pdo->prepare(
        "SELECT id, collection_date, retention_end_date FROM data_records
         WHERE category_id = :cid AND deleted_at IS NULL AND status != 'disposed'
           AND retention_end_date IS NOT NULL"
    );
    $stmt->execute(['cid' => $category_id]);
    $ins = $pdo->prepare(
        "INSERT INTO pending_recalculations
           (record_id, category_id, old_retention_end_date, new_retention_end_date, triggered_by, status)
         VALUES (:rid,:cid,:old,:new,:by,'pending')"
    );
    $n = 0;
    foreach ($stmt->fetchAll() as $r) {
        $newEnd = retention_end_date($r['collection_date'], $new_days);
        $ins->execute([
            'rid' => $r['id'], 'cid' => $category_id,
            'old' => $r['retention_end_date'], 'new' => $newEnd, 'by' => $actor_id,
        ]);
        $n++;
    }
    if ($n > 0) {
        notify_role($pdo, ['dpo', 'admin'], 'recalculation_pending',
            "Retention change queued $n record(s) for review",
            "A category's retention period changed. $n record(s) are awaiting recalculation review.");
    }
    return $n;
}

/**
 * Update a category. If retention_period_days changed (date_based), queues recalculations (B2)
 * instead of touching record dates. Returns ['recalc_queued' => int].
 */
function update_category(PDO $pdo, int $id, array $in, int $actor_id): array {
    $existing = fetch_category($pdo, $id);
    if ($existing === null) { throw new RuntimeException('Category not found'); }

    $trigger = $in['disposal_trigger'] === 'consent_withdrawal' ? 'consent_withdrawal' : 'date_based';
    $days = $trigger === 'consent_withdrawal' ? 0 : max(0, (int) ($in['retention_period_days'] ?? 0));

    $stmt = $pdo->prepare(
        "UPDATE data_categories SET
           name=:name, description=:descr, compliance_framework=:fw, legal_basis=:lb,
           retention_period_days=:days, retention_period_label=:label, disposal_method=:dm,
           disposal_trigger=:dt, requires_dual_approval=:dual, owner_id=:owner, review_frequency=:rf
         WHERE id=:id AND deleted_at IS NULL"
    );
    $stmt->execute([
        'name'  => $in['name'],
        'descr' => $in['description'] ?? null,
        'fw'    => $in['compliance_framework'] ?? 'GDPR',
        'lb'    => $in['legal_basis'],
        'days'  => $days,
        'label' => $in['retention_period_label'] ?? ($days > 0 ? "$days days" : 'Until consent withdrawn'),
        'dm'    => $in['disposal_method'] ?? 'delete',
        'dt'    => $trigger,
        'dual'  => !empty($in['requires_dual_approval']) ? 1 : 0,
        'owner' => $in['owner_id'] ?? null,
        'rf'    => $in['review_frequency'] ?? 'quarterly',
        'id'    => $id,
    ]);
    log_audit($pdo, 'category_updated', 'data_category', $id, $actor_id, ['name' => $in['name']], get_client_ip());

    $queued = 0;
    if ($trigger === 'date_based' && $days !== (int) $existing['retention_period_days']) {
        $queued = queue_recalculations($pdo, $id, $days, $actor_id);
    }
    return ['recalc_queued' => $queued];
}

/** Soft-delete a category. Blocked (returns false) if it still has active records. */
function soft_delete_category(PDO $pdo, int $id, int $actor_id): bool {
    if (count_active_records_for_category($pdo, $id) > 0) { return false; }
    $pdo->prepare("UPDATE data_categories SET deleted_at = NOW() WHERE id = :id")->execute(['id' => $id]);
    log_audit($pdo, 'category_deleted', 'data_category', $id, $actor_id, null, get_client_ip());
    return true;
}
