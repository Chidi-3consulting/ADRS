<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_login();
$pdo = get_db();
$me = current_user();

$orgId = require_org_id();
if (has_role('data_owner')) {
    $stmt = $pdo->prepare("SELECT * FROM data_categories WHERE organization_id = :org AND deleted_at IS NULL AND owner_id = :o ORDER BY name");
    $stmt->execute(['org' => $orgId, 'o' => $me['id']]);
} else {
    $stmt = $pdo->prepare("SELECT * FROM data_categories WHERE organization_id = :org AND deleted_at IS NULL ORDER BY name");
    $stmt->execute(['org' => $orgId]);
}
$categories = $stmt->fetchAll();

log_audit($pdo, 'categories_exported', 'category', null, (int)$me['id'], ['count' => count($categories)], get_client_ip());

header('Content-Type: text/csv; charset=utf-8');
header('Content-Disposition: attachment; filename="adrs_data_categories_' . date('Y-m-d') . '.csv"');
echo "\xEF\xBB\xBF"; // UTF-8 BOM

$out = fopen('php://output', 'w');
fputcsv($out, [
    'Name', 
    'Compliance Framework', 
    'Legal Basis', 
    'Retention Period (Days)', 
    'Retention Period Label', 
    'Disposal Method', 
    'Disposal Trigger', 
    'Sensitive (Requires Dual Approval)', 
    'Retention Reason',
    'Description', 
    'Source'
]);

foreach ($categories as $c) {
    fputcsv($out, [
        $c['name'],
        $c['compliance_framework'],
        $c['legal_basis'],
        $c['retention_period_days'],
        $c['retention_period_label'],
        $c['disposal_method'],
        $c['disposal_trigger'],
        ((int)$c['requires_dual_approval'] === 1 ? 'Yes' : 'No'),
        $c['retention_reason'] ?: '',
        $c['description'] ?: '',
        $c['source']
    ]);
}
fclose($out);
