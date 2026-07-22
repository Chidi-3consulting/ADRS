<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/reports_lib.php';
require_once __DIR__ . '/../../includes/tenant_lib.php';
require_once __DIR__ . '/../../includes/country_regulation_map.php';
require_role('admin', 'dpo');
$pdo = get_db();

$org = fetch_current_organization($pdo);
$orgCountry = $org['country'] ?? 'OTHER';
$regLabels = get_country_regulation_labels($orgCountry);
$reportTitle = $regLabels['audit_label'] ?? 'Annual Compliance Report';

$year = (int) ($_GET['year'] ?? date('Y'));
$report = build_compliance_report($pdo, $year);
log_audit($pdo, 'export_generated', 'system', null, (int) current_user()['id'], ['report' => 'annual_compliance', 'year' => $year], get_client_ip());

$safeFilename = strtolower(preg_replace('/[^a-zA-Z0-9]+/', '_', $reportTitle)) . '_' . $year . '.csv';

header('Content-Type: text/csv; charset=utf-8');
header('Content-Disposition: attachment; filename="' . $safeFilename . '"');
echo "\xEF\xBB\xBF"; // UTF-8 BOM
$out = fopen('php://output', 'w');
foreach (compliance_report_to_csv_rows($report, $reportTitle) as $row) { fputcsv($out, $row); }
fclose($out);
