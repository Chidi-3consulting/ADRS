<?php
/** GET /api/v1/categories — categories available for field-mapping config. */
api_require_permission($apiKey, 'categories');

$rows = $pdo->query(
    "SELECT id, name, compliance_framework AS framework, disposal_trigger, retention_period_label
     FROM data_categories WHERE deleted_at IS NULL AND is_active = 1 ORDER BY name"
)->fetchAll();

api_response(200, ['categories' => $rows]);
