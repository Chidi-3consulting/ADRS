<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/reports_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();

$year = (int) ($_GET['year'] ?? date('Y'));
$report = build_ndpr_report($pdo, $year);
log_audit($pdo, 'export_generated', 'system', null, (int) current_user()['id'], ['report' => 'ndpr_annual', 'year' => $year], get_client_ip());

header('Content-Type: text/csv; charset=utf-8');
header('Content-Disposition: attachment; filename="ndpr_annual_report_' . $year . '.csv"');
echo "\xEF\xBB\xBF"; // UTF-8 BOM
$out = fopen('php://output', 'w');
foreach (ndpr_report_to_csv_rows($report) as $row) { fputcsv($out, $row); }
fclose($out);
