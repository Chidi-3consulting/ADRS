<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';

/**
 * NDPR Annual Report builder (testable). Summarises the compliance posture for a year:
 * categories, records by status, disposals by method, DSAR outcomes, and audit volume.
 */
function build_ndpr_report(PDO $pdo, int $year): array {
    $disposed = $pdo->prepare(
        "SELECT dc.disposal_method AS method, COUNT(*) c
         FROM data_records dr JOIN data_categories dc ON dc.id = dr.category_id
         WHERE dr.status='disposed' AND YEAR(dr.disposed_at) = :y GROUP BY dc.disposal_method"
    );
    $disposed->execute(['y' => $year]);
    $byMethod = ['delete' => 0, 'anonymise' => 0, 'archive' => 0];
    foreach ($disposed->fetchAll() as $r) { $byMethod[$r['method']] = (int) $r['c']; }

    $dsar = $pdo->prepare("SELECT status, COUNT(*) c FROM dsar_requests WHERE YEAR(created_at) = :y GROUP BY status");
    $dsar->execute(['y' => $year]);
    $dsarByStatus = [];
    foreach ($dsar->fetchAll() as $r) { $dsarByStatus[$r['status']] = (int) $r['c']; }

    $auditCount = $pdo->prepare("SELECT COUNT(*) c FROM audit_log WHERE YEAR(created_at) = :y");
    $auditCount->execute(['y' => $year]);

    return [
        'year' => $year,
        'generated_at' => date('c'),
        'total_categories' => (int) $pdo->query("SELECT COUNT(*) c FROM data_categories WHERE deleted_at IS NULL")->fetch()['c'],
        'active_records' => (int) $pdo->query("SELECT COUNT(*) c FROM data_records WHERE status != 'disposed' AND deleted_at IS NULL")->fetch()['c'],
        'disposed_by_method' => $byMethod,
        'disposed_total' => array_sum($byMethod),
        'dsar_by_status' => $dsarByStatus,
        'dsar_total' => array_sum($dsarByStatus),
        'on_legal_hold' => (int) $pdo->query("SELECT COUNT(*) c FROM data_records WHERE legal_hold=1 AND deleted_at IS NULL")->fetch()['c'],
        'audit_events' => (int) $auditCount->fetch()['c'],
    ];
}

/** Flatten the report into CSV rows (header + key/value lines) for export. */
function ndpr_report_to_csv_rows(array $report): array {
    $rows = [['NDPR Annual Compliance Report']];
    $rows[] = ['Year', $report['year']];
    $rows[] = ['Generated at', $report['generated_at']];
    $rows[] = [];
    $rows[] = ['Metric', 'Value'];
    $rows[] = ['Total active categories', $report['total_categories']];
    $rows[] = ['Active records', $report['active_records']];
    $rows[] = ['Records on legal hold', $report['on_legal_hold']];
    $rows[] = ['Disposed (delete)', $report['disposed_by_method']['delete']];
    $rows[] = ['Disposed (anonymise)', $report['disposed_by_method']['anonymise']];
    $rows[] = ['Disposed (archive)', $report['disposed_by_method']['archive']];
    $rows[] = ['Disposed total', $report['disposed_total']];
    $rows[] = ['DSARs total', $report['dsar_total']];
    foreach ($report['dsar_by_status'] as $status => $c) { $rows[] = ['DSAR: ' . $status, $c]; }
    $rows[] = ['Audit events', $report['audit_events']];
    return $rows;
}
