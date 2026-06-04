<?php
$pdo = get_pdo();
verify_enterprise_tier($pdo);
require_enterprise_api_enabled($pdo);
$apiKey = require_api_key($pdo);
require_permission($apiKey, 'categories');

$stmt = $pdo->query('SELECT id, name, compliance_framework, disposal_method FROM data_categories WHERE deleted_at IS NULL ORDER BY name');
$rows = $stmt->fetchAll();
send_json_logged($pdo, ['categories' => $rows], 200, $apiKey);
