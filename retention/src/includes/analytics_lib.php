<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';

/**
 * Phase 3 analytics: aggregate compliance metrics for the management/board dashboard and
 * exportable reports. Pure read-side aggregation — unit-tested for correctness.
 */

/** Headline compliance metrics across the whole inventory. */
function compliance_metrics(PDO $pdo): array {
    $recStatus = $pdo->query(
        "SELECT status, COUNT(*) c FROM data_records WHERE deleted_at IS NULL GROUP BY status"
    )->fetchAll(PDO::FETCH_KEY_PAIR);

    $upcoming30 = (int) $pdo->query("SELECT COUNT(*) FROM data_records WHERE deleted_at IS NULL AND status NOT IN ('disposed') AND retention_end_date IS NOT NULL AND retention_end_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)")->fetchColumn();
    $overdue = (int) $pdo->query("SELECT COUNT(*) FROM data_records WHERE deleted_at IS NULL AND status != 'disposed' AND retention_end_date IS NOT NULL AND retention_end_date < CURDATE()")->fetchColumn();

    return [
        'categories'      => (int) $pdo->query("SELECT COUNT(*) FROM data_categories WHERE deleted_at IS NULL")->fetchColumn(),
        'records_total'   => (int) $pdo->query("SELECT COUNT(*) FROM data_records WHERE deleted_at IS NULL")->fetchColumn(),
        'records_active'  => (int) ($recStatus['active'] ?? 0),
        'records_due'     => (int) ($recStatus['due_review'] ?? 0),
        'records_disposed'=> (int) ($recStatus['disposed'] ?? 0),
        'records_hold'    => (int) ($recStatus['legal_hold'] ?? 0) + (int) $pdo->query("SELECT COUNT(*) FROM data_records WHERE legal_hold=1 AND deleted_at IS NULL")->fetchColumn(),
        'upcoming_30d'    => $upcoming30,
        'overdue'         => $overdue,
        'dsar_open'       => (int) $pdo->query("SELECT COUNT(*) FROM dsar_requests WHERE status NOT IN ('completed','rejected')")->fetchColumn(),
        'dsar_total'      => (int) $pdo->query("SELECT COUNT(*) FROM dsar_requests")->fetchColumn(),
        'breaches_open'   => (int) $pdo->query("SELECT COUNT(*) FROM breach_incidents WHERE status != 'closed'")->fetchColumn(),
        'dpia_high'       => (int) $pdo->query("SELECT COUNT(*) FROM dpia_assessments WHERE risk_level='high'")->fetchColumn(),
        'audit_events'    => (int) $pdo->query("SELECT COUNT(*) FROM audit_log")->fetchColumn(),
    ];
}

/** Disposal counts per calendar month for the last N months: ['YYYY-MM' => count] (oldest first). */
function disposals_by_month(PDO $pdo, int $months = 12): array {
    $out = [];
    for ($i = $months - 1; $i >= 0; $i--) { $out[date('Y-m', strtotime("-$i months"))] = 0; }
    $rows = $pdo->query(
        "SELECT DATE_FORMAT(disposed_at, '%Y-%m') ym, COUNT(*) c
         FROM data_records WHERE status='disposed' AND disposed_at >= DATE_SUB(CURDATE(), INTERVAL " . (int) $months . " MONTH)
         GROUP BY ym"
    )->fetchAll(PDO::FETCH_KEY_PAIR);
    foreach ($rows as $ym => $c) { if (array_key_exists($ym, $out)) { $out[$ym] = (int) $c; } }
    return $out;
}

/** Records grouped by category (top N by count) for the inventory breakdown. */
function records_by_category(PDO $pdo, int $limit = 10): array {
    $stmt = $pdo->query(
        "SELECT dc.name, COUNT(dr.id) c FROM data_categories dc
         LEFT JOIN data_records dr ON dr.category_id = dc.id AND dr.deleted_at IS NULL
         WHERE dc.deleted_at IS NULL GROUP BY dc.id ORDER BY c DESC LIMIT " . (int) $limit
    );
    return $stmt->fetchAll(PDO::FETCH_KEY_PAIR);
}
