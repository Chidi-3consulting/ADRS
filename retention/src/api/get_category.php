<?php
// AJAX: category + retention rules for record create preview.
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/retention_rules_lib.php';
require_login();

header('Content-Type: application/json');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

$id = filter_input(INPUT_GET, 'id', FILTER_VALIDATE_INT);
if (!$id || $id < 1) { http_response_code(400); echo json_encode(['error' => 'Invalid category ID']); exit; }

$pdo = get_db();
$where = '';
$params = ['id' => $id];
if (has_role('data_owner')) { $where = ' AND owner_id = :owner'; $params['owner'] = current_user()['id']; }

$stmt = $pdo->prepare(
    "SELECT id, name, retention_period_days, retention_period_label, disposal_trigger,
            disposal_method, requires_dual_approval, legal_basis, compliance_framework
     FROM data_categories
     WHERE id = :id AND is_active = 1 AND deleted_at IS NULL" . $where
);
$stmt->execute($params);
$category = $stmt->fetch();

if (!$category) { http_response_code(404); echo json_encode(['error' => 'Category not found or access denied']); exit; }

$rules = list_category_retention_rules($pdo, $id);
$category['rules'] = array_map(function ($r) {
    return [
        'id'                     => (int) $r['id'],
        'rule_name'              => $r['rule_name'],
        'legal_basis'            => $r['legal_basis'],
        'processing_purpose'     => $r['processing_purpose'],
        'institution_type'       => $r['institution_type'],
        'institution_type_label' => institution_type_label($r['institution_type']),
        'retention_period_days'  => (int) $r['retention_period_days'],
        'retention_period_label' => $r['retention_period_label'],
        'disposal_trigger'       => $r['disposal_trigger'],
        'disposal_method'        => $r['disposal_method'],
        'requires_dual_approval' => (int) $r['requires_dual_approval'],
        'is_default'             => (int) $r['is_default'],
    ];
}, $rules);

echo json_encode($category);
