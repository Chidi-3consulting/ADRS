<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/categories_lib.php';
require_once __DIR__ . '/notifications_lib.php';

/**
 * Data record (retention schedule) business logic: B4 owner guardrails, server-side
 * retention-date calculation (D4), B3 category reassignment.
 */

/** Pure: retention end date for a record, or null for consent-withdrawal / zero-day categories. */
function compute_retention_end(array $category, string $collection_date): ?string {
    if (($category['disposal_trigger'] ?? 'date_based') === 'consent_withdrawal') { return null; }
    $days = (int) ($category['retention_period_days'] ?? 0);
    return $days > 0 ? retention_end_date($collection_date, $days) : null;
}

/**
 * Create a data record. $in: category_id, record_reference, data_subject_type, collection_date, notes.
 * $actor: ['id'=>int,'role'=>string]. Enforces B4 (Data Owner may only use their own categories;
 * collection_date forced to today). Returns ['id'=>int, 'retention_end'=>?string].
 * Throws InvalidArgumentException on validation failure or B4 violation.
 */
function create_data_record(PDO $pdo, array $in, array $actor): array {
    $category_id = (int) ($in['category_id'] ?? 0);
    $reference   = trim((string) ($in['record_reference'] ?? ''));
    if ($category_id <= 0 || $reference === '') {
        throw new InvalidArgumentException('Category and record reference are required.');
    }

    $category = fetch_category($pdo, $category_id);
    if ($category === null || (int) $category['is_active'] !== 1) {
        throw new InvalidArgumentException('Selected category is not available.');
    }

    $is_owner = ($actor['role'] ?? '') === 'data_owner';
    if ($is_owner && (int) $category['owner_id'] !== (int) $actor['id']) {
        throw new InvalidArgumentException('You can only create records in your assigned categories.');
    }

    // Data Owners always register with today's collection date (B4); others may set it.
    $collection_date = $is_owner
        ? date('Y-m-d')
        : (trim((string) ($in['collection_date'] ?? '')) ?: date('Y-m-d'));

    $retention_end    = compute_retention_end($category, $collection_date);
    $created_by_owner = $is_owner ? 1 : 0;

    $stmt = $pdo->prepare(
        "INSERT INTO data_records
           (category_id, record_reference, data_subject_type, collection_date, retention_end_date,
            status, created_by_owner, created_by, notes)
         VALUES (:cid,:ref,:subj,:cdate,:rend,'active',:cbo,:cby,:notes)"
    );
    $stmt->execute([
        'cid'   => $category_id,
        'ref'   => $reference,
        'subj'  => ($in['data_subject_type'] ?? '') !== '' ? $in['data_subject_type'] : null,
        'cdate' => $collection_date,
        'rend'  => $retention_end,
        'cbo'   => $created_by_owner,
        'cby'   => $actor['id'] ?? null,
        'notes' => ($in['notes'] ?? '') !== '' ? $in['notes'] : null,
    ]);
    $id = (int) $pdo->lastInsertId();

    log_audit($pdo, 'record_created', 'data_record', $id, (int) ($actor['id'] ?? 0),
        ['category' => $category['name'], 'collection_date' => $collection_date, 'created_by_owner' => $created_by_owner],
        get_client_ip());

    if ($created_by_owner) {
        notify_role($pdo, ['admin', 'dpo'], 'record_created_by_owner',
            'New record added by Data Owner: ' . $reference,
            'Record "' . $reference . '" was registered in category "' . $category['name'] . '".', $id);
    }

    return ['id' => $id, 'retention_end' => $retention_end];
}

/**
 * Fetch a record by id (joined with its category), or null. By default excludes
 * soft-deleted (disposed-by-delete) records; pass $include_deleted=true to retrieve them
 * for read-only viewing (compliance teams must be able to see a record's final disposition).
 */
function fetch_record(PDO $pdo, int $id, bool $include_deleted = false): ?array {
    $sql = "SELECT dr.*, dc.name AS category_name, dc.disposal_trigger, dc.disposal_method,
                dc.requires_dual_approval, dc.retention_period_days, dc.legal_basis, dc.compliance_framework
         FROM data_records dr JOIN data_categories dc ON dc.id = dr.category_id
         WHERE dr.id = :id" . ($include_deleted ? '' : ' AND dr.deleted_at IS NULL') . " LIMIT 1";
    $stmt = $pdo->prepare($sql);
    $stmt->execute(['id' => $id]);
    $row = $stmt->fetch();
    return $row === false ? null : $row;
}

/**
 * B3: reassign a record to a new category. Preserves original_category_id on first reassignment
 * only. If $recalculate, retention_end_date is recomputed from the new category + existing
 * collection_date; otherwise the existing end date is kept. Logs before/after.
 */
function reassign_category(PDO $pdo, int $record_id, int $new_category_id, int $actor_id, bool $recalculate): void {
    $record = fetch_record($pdo, $record_id);
    if ($record === null) { throw new InvalidArgumentException('Record not found.'); }
    $newCat = fetch_category($pdo, $new_category_id);
    if ($newCat === null) { throw new InvalidArgumentException('Target category not found.'); }

    $original = $record['original_category_id'] ?? null;
    $setOriginal = $original === null ? (int) $record['category_id'] : (int) $original;

    $newEnd = $recalculate
        ? compute_retention_end($newCat, $record['collection_date'])
        : $record['retention_end_date'];

    $stmt = $pdo->prepare(
        "UPDATE data_records
            SET category_id = :ncid, original_category_id = :orig,
                retention_end_date = :rend, category_reassigned_at = NOW(), category_reassigned_by = :by
          WHERE id = :id"
    );
    $stmt->execute(['ncid' => $new_category_id, 'orig' => $setOriginal, 'rend' => $newEnd, 'by' => $actor_id, 'id' => $record_id]);

    log_audit($pdo, 'record_reassigned', 'data_record', $record_id, $actor_id, [
        'from_category' => (int) $record['category_id'], 'to_category' => $new_category_id,
        'recalculated' => $recalculate, 'new_retention_end' => $newEnd,
    ], get_client_ip());
}
