<?php
if (!require_db('advanced ops')) { return; }
require_once __DIR__ . '/../../src/includes/analytics_lib.php';
require_once __DIR__ . '/../../src/includes/webhooks_lib.php';
require_once __DIR__ . '/../../src/includes/backups_lib.php';
require_once __DIR__ . '/../../src/includes/categories_lib.php';
require_once __DIR__ . '/../../src/includes/records_lib.php';

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Ops','ops@x.io','x','admin',1)");
$admin = (int) $pdo->lastInsertId();

// --- Analytics metrics ---
$cat = create_category($pdo, ['name'=>'Ops Cat','legal_basis'=>'contract','retention_period_days'=>30,'disposal_trigger'=>'date_based'], $admin);
create_data_record($pdo, ['category_id'=>$cat,'record_reference'=>'OPS-1','collection_date'=>date('Y-m-d')], ['id'=>$admin,'role'=>'admin']);
$m = compliance_metrics($pdo);
assert_true($m['records_total'] >= 1, 'metrics count records');
assert_true(array_key_exists('overdue', $m) && array_key_exists('breaches_open', $m), 'metrics include key fields');
$dm = disposals_by_month($pdo, 12);
assert_equals(12, count($dm), 'disposals_by_month returns 12 buckets');

// --- Webhook matching ---
assert_true(webhook_matches('*', 'breach.created'), 'wildcard matches');
assert_true(webhook_matches('breach.created,escalation.sent', 'escalation.sent'), 'CSV matches listed event');
assert_false(webhook_matches('breach.created', 'escalation.sent'), 'CSV rejects unlisted event');

// fire_ops_event respects the enable flag, fires to subscribed endpoints, records last_fired_at.
set_setting($pdo, 'ops_webhooks_enabled', '0');
$pdo->prepare("INSERT INTO webhook_endpoints (name,url,event_types,created_by) VALUES ('W','https://x.test/hook','breach.created',:b)")->execute(['b'=>$admin]);
$wid = (int) $pdo->lastInsertId();
$captured = [];
$stub = function($url, $payload) use (&$captured) { $captured[] = [$url, $payload]; return [200, 'ok']; };
assert_equals(0, fire_ops_event($pdo, 'breach.created', ['x'=>1], $stub), 'disabled => fires nothing');
set_setting($pdo, 'ops_webhooks_enabled', '1');
assert_equals(1, fire_ops_event($pdo, 'breach.created', ['ref'=>'BR-1'], $stub), 'enabled => fires to subscriber');
assert_equals(0, fire_ops_event($pdo, 'unrelated.event', [], $stub), 'non-subscribed event => no fire');
assert_true($captured[0][1]['event'] === 'breach.created', 'payload carries the event name');
assert_true($pdo->query("SELECT last_fired_at FROM webhook_endpoints WHERE id=$wid")->fetchColumn() !== null, 'last_fired_at recorded');
set_setting($pdo, 'ops_webhooks_enabled', '0');

// --- Pure-PHP backup ---
$dir = sys_get_temp_dir() . DIRECTORY_SEPARATOR . 'adrs_bk_' . uniqid();
$res = backup_database($pdo, $dir);
assert_equals('success', $res['status'], 'backup succeeds');
assert_true($res['size'] > 0 && is_file($res['file']), 'backup file written');
$content = file_get_contents($res['file']);
assert_true(str_contains($content, 'CREATE TABLE') && str_contains($content, 'data_categories'), 'backup contains schema');
assert_equals(1, (int) $pdo->query("SELECT COUNT(*) FROM backup_log WHERE status='success'")->fetchColumn() >= 1 ? 1 : 0, 'backup logged');
@unlink($res['file']); @rmdir($dir);
