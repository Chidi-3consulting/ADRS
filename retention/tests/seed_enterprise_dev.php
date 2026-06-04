<?php
/**
 * Provision the DEV database (adrs) for an Enterprise API smoke test:
 * enable the tier + API, ensure a connected system, a date-based category, an
 * auto-categorisation rule for object_type "customer", and a fresh API key.
 * Prints the raw API key on the last line. Run: php tests/seed_enterprise_dev.php
 */
require_once __DIR__ . '/../src/config/database.php';   // dev profile (adrs)
require_once __DIR__ . '/../src/includes/db.php';
require_once __DIR__ . '/../src/includes/helpers.php';
require_once __DIR__ . '/../src/includes/categories_lib.php';
require_once __DIR__ . '/../src/includes/enterprise_lib.php';

$pdo = get_db();
set_setting($pdo, 'adrs_tier', 'enterprise');
set_setting($pdo, 'enterprise_api_enabled', '1');
set_setting($pdo, 'intake_queue_enabled', '1');

$admin = (int) ($pdo->query("SELECT id FROM users WHERE role='admin' AND deleted_at IS NULL ORDER BY id LIMIT 1")->fetchColumn() ?: 0) ?: null;

$sysId = (int) ($pdo->query("SELECT id FROM connected_systems WHERE name='SmokeCRM' LIMIT 1")->fetchColumn() ?: 0);
if (!$sysId) {
    $pdo->prepare("INSERT INTO connected_systems (name, system_type, base_url, created_by) VALUES ('SmokeCRM','crm','https://smoke.example/api',:b)")->execute(['b' => $admin]);
    $sysId = (int) $pdo->lastInsertId();
}

$catId = (int) ($pdo->query("SELECT id FROM data_categories WHERE name='Smoke Customer' AND deleted_at IS NULL LIMIT 1")->fetchColumn() ?: 0);
if (!$catId) {
    $catId = create_category($pdo, ['name' => 'Smoke Customer', 'legal_basis' => 'contract', 'retention_period_days' => 365, 'disposal_trigger' => 'date_based', 'disposal_method' => 'delete'], $admin);
}

$hasRule = (int) $pdo->query("SELECT COUNT(*) FROM auto_categorization_rules WHERE system_id=$sysId AND object_type='customer'")->fetchColumn();
if (!$hasRule) {
    $pdo->prepare("INSERT INTO auto_categorization_rules (system_id, rule_name, object_type, category_id, priority, created_by) VALUES (:s,'customers','customer',:c,10,:b)")
        ->execute(['s' => $sysId, 'c' => $catId, 'b' => $admin]);
}

$key = create_api_key($pdo, $sysId, 'Smoke Key ' . date('His'), ['ingest', 'batch', 'consent', 'health', 'categories'], 600, $admin);
echo $key['raw'] . PHP_EOL;
