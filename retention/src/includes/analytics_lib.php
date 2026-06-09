<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';

/**
 * Phase 3 analytics: aggregate compliance metrics for the management/board dashboard and
 * exportable reports. Pure read-side aggregation — unit-tested for correctness.
 */

/** Headline compliance metrics across the whole inventory. */
function compliance_metrics(PDO $pdo): array {
    $orgId = function_exists('current_org_id') ? (current_org_id() ?? 1) : 1;
    $recStmt = $pdo->prepare("SELECT status, COUNT(*) c FROM data_records WHERE organization_id = :o AND deleted_at IS NULL GROUP BY status");
    $recStmt->execute(['o' => $orgId]);
    $recStatus = $recStmt->fetchAll(PDO::FETCH_KEY_PAIR);

    $upStmt = $pdo->prepare("SELECT COUNT(*) FROM data_records WHERE organization_id = :o AND deleted_at IS NULL AND status NOT IN ('disposed') AND retention_end_date IS NOT NULL AND retention_end_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)");
    $upStmt->execute(['o' => $orgId]);
    $upcoming30 = (int) $upStmt->fetchColumn();
    $odStmt = $pdo->prepare("SELECT COUNT(*) FROM data_records WHERE organization_id = :o AND deleted_at IS NULL AND status != 'disposed' AND retention_end_date IS NOT NULL AND retention_end_date < CURDATE()");
    $odStmt->execute(['o' => $orgId]);
    $overdue = (int) $odStmt->fetchColumn();

    $catStmt = $pdo->prepare("SELECT COUNT(*) FROM data_categories WHERE organization_id = :o AND deleted_at IS NULL");
    $catStmt->execute(['o' => $orgId]);
    $totStmt = $pdo->prepare("SELECT COUNT(*) FROM data_records WHERE organization_id = :o AND deleted_at IS NULL");
    $totStmt->execute(['o' => $orgId]);
    $holdStmt = $pdo->prepare("SELECT COUNT(*) FROM data_records WHERE organization_id = :o AND legal_hold=1 AND deleted_at IS NULL");
    $holdStmt->execute(['o' => $orgId]);
    $dsarOpenStmt = $pdo->prepare("SELECT COUNT(*) FROM dsar_requests WHERE organization_id = :o AND status NOT IN ('completed','rejected')");
    $dsarOpenStmt->execute(['o' => $orgId]);
    $dsarTotStmt = $pdo->prepare('SELECT COUNT(*) FROM dsar_requests WHERE organization_id = :o');
    $dsarTotStmt->execute(['o' => $orgId]);
    $breachStmt = $pdo->prepare("SELECT COUNT(*) FROM breach_incidents WHERE organization_id = :o AND status != 'closed'");
    $breachStmt->execute(['o' => $orgId]);
    $dpiaStmt = $pdo->prepare("SELECT COUNT(*) FROM dpia_assessments WHERE organization_id = :o AND risk_level='high'");
    $dpiaStmt->execute(['o' => $orgId]);
    $auditStmt = $pdo->prepare('SELECT COUNT(*) FROM audit_log WHERE organization_id = :o');
    $auditStmt->execute(['o' => $orgId]);

    return [
        'categories'      => (int) $catStmt->fetchColumn(),
        'records_total'   => (int) $totStmt->fetchColumn(),
        'records_active'  => (int) ($recStatus['active'] ?? 0),
        'records_due'     => (int) ($recStatus['due_review'] ?? 0),
        'records_disposed'=> (int) ($recStatus['disposed'] ?? 0),
        'records_hold'    => (int) ($recStatus['legal_hold'] ?? 0) + (int) $holdStmt->fetchColumn(),
        'upcoming_30d'    => $upcoming30,
        'overdue'         => $overdue,
        'dsar_open'       => (int) $dsarOpenStmt->fetchColumn(),
        'dsar_total'      => (int) $dsarTotStmt->fetchColumn(),
        'breaches_open'   => (int) $breachStmt->fetchColumn(),
        'dpia_high'       => (int) $dpiaStmt->fetchColumn(),
        'audit_events'    => (int) $auditStmt->fetchColumn(),
    ];
}

/** Disposal counts per calendar month for the last N months: ['YYYY-MM' => count] (oldest first). */
function disposals_by_month(PDO $pdo, int $months = 12): array {
    $orgId = function_exists('current_org_id') ? (current_org_id() ?? 1) : 1;
    $out = [];
    for ($i = $months - 1; $i >= 0; $i--) { $out[date('Y-m', strtotime("-$i months"))] = 0; }
    $stmt = $pdo->prepare(
        "SELECT DATE_FORMAT(disposed_at, '%Y-%m') ym, COUNT(*) c
         FROM data_records WHERE organization_id = :o AND status='disposed'
           AND disposed_at >= DATE_SUB(CURDATE(), INTERVAL " . (int) $months . " MONTH)
         GROUP BY ym"
    );
    $stmt->execute(['o' => $orgId]);
    $rows = $stmt->fetchAll(PDO::FETCH_KEY_PAIR);
    foreach ($rows as $ym => $c) { if (array_key_exists($ym, $out)) { $out[$ym] = (int) $c; } }
    return $out;
}

/** Records grouped by category (top N by count) for the inventory breakdown. */
function records_by_category(PDO $pdo, int $limit = 10): array {
    $orgId = function_exists('current_org_id') ? (current_org_id() ?? 1) : 1;
    $stmt = $pdo->prepare(
        "SELECT dc.name, COUNT(dr.id) c FROM data_categories dc
         LEFT JOIN data_records dr ON dr.category_id = dc.id AND dr.organization_id = :o AND dr.deleted_at IS NULL
         WHERE dc.organization_id = :o2 AND dc.deleted_at IS NULL GROUP BY dc.id ORDER BY c DESC LIMIT " . (int) $limit
    );
    $stmt->execute(['o' => $orgId, 'o2' => $orgId]);
    return $stmt->fetchAll(PDO::FETCH_KEY_PAIR);
}
