<?php
if (!require_db('enterprise')) { return; }
require_once __DIR__ . '/../../src/includes/categories_lib.php';
require_once __DIR__ . '/../../src/includes/enterprise_lib.php';
require_once __DIR__ . '/../../src/engine/engine_lib.php';

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Ent Admin','entadmin@x.io','x','admin',1)");
$admin = (int) $pdo->lastInsertId();

$pdo->prepare("INSERT INTO connected_systems (name, system_type, base_url, created_by) VALUES ('CRM','crm','https://crm.example/api',:b)")->execute(['b'=>$admin]);
$sys = (int) $pdo->lastInsertId();
$pdo->prepare("INSERT INTO connected_systems (name, system_type, base_url, created_by) VALUES ('NoURL','custom',NULL,:b)")->execute(['b'=>$admin]);
$sysNoUrl = (int) $pdo->lastInsertId();

$catCustomer = create_category($pdo, ['name'=>'API Customer','legal_basis'=>'contract','retention_period_days'=>365,'disposal_trigger'=>'date_based','disposal_method'=>'delete'], $admin);
$catRejected = create_category($pdo, ['name'=>'API Rejected Loan','legal_basis'=>'legitimate_interest','retention_period_days'=>30,'disposal_trigger'=>'date_based','disposal_method'=>'delete'], $admin);
$catMarketing = create_category($pdo, ['name'=>'API Marketing','legal_basis'=>'consent','disposal_trigger'=>'consent_withdrawal','disposal_method'=>'delete'], $admin);

// --- API keys (E1) ---
$k = generate_api_key();
assert_true(str_starts_with($k['raw'], 'adrs_'), 'raw key prefixed adrs_');
assert_equals(64, strlen($k['hash']), 'hash is sha-256 hex');
assert_equals(12, strlen($k['prefix']), 'prefix is 12 chars');

$created = create_api_key($pdo, $sys, 'Prod Key', ['ingest','consent','health'], 60, $admin);
$verified = verify_api_key($pdo, $created['raw']);
assert_true($verified !== null, 'valid key verifies');
assert_equals('CRM', $verified['system_name'], 'verify joins the system');
assert_true(verify_api_key($pdo, 'adrs_wrongkey') === null, 'invalid key rejected');
assert_true(api_key_can($verified, 'ingest'), 'permission granted');
assert_false(api_key_can($verified, 'batch'), 'missing permission denied');
revoke_api_key($pdo, $created['id'], $admin);
assert_true(verify_api_key($pdo, $created['raw']) === null, 'revoked key rejected');

// --- Auto-categorisation (E5: first match by priority; conditions) ---
$pdo->prepare("INSERT INTO auto_categorization_rules (system_id, rule_name, object_type, category_id, priority) VALUES (:s,'cust','customer',:c,10)")->execute(['s'=>$sys,'c'=>$catCustomer]);
$pdo->prepare("INSERT INTO auto_categorization_rules (system_id, rule_name, object_type, category_id, priority) VALUES (:s,'loan-any','loan',:c,10)")->execute(['s'=>$sys,'c'=>$catCustomer]);
$pdo->prepare("INSERT INTO auto_categorization_rules (system_id, rule_name, object_type, condition_field, condition_value, category_id, priority) VALUES (:s,'loan-rejected','loan','status','rejected',:c,5)")->execute(['s'=>$sys,'c'=>$catRejected]);

assert_equals($catCustomer, auto_categorize($pdo, $sys, 'customer'), 'customer -> customer category');
assert_equals($catRejected, auto_categorize($pdo, $sys, 'loan', ['status'=>'rejected']), 'rejected loan -> higher-priority rule wins');
assert_equals($catCustomer, auto_categorize($pdo, $sys, 'loan', ['status'=>'approved']), 'approved loan -> generic rule');
assert_true(auto_categorize($pdo, $sys, 'unknown') === null, 'no rule -> null');

// --- Intake queue (E2) ---
$qid = enqueue_intake($pdo, $sys, null, null, ['object_type'=>'customer','external_ref'=>'CUST-1','data_subject_type'=>'Customer','collection_date'=>'2025-01-01']);
$item = $pdo->query("SELECT * FROM intake_queue WHERE id=$qid")->fetch();
$res = process_intake_item($pdo, $item);
assert_equals('completed', $res['status'], 'intake item processed');
$rec = $pdo->query("SELECT * FROM data_records WHERE id={$res['record_id']}")->fetch();
assert_equals('CUST-1', $rec['record_reference'], 'record created from intake');
assert_equals('2026-01-01', $rec['retention_end_date'], 'retention end computed (365d)');
assert_equals(1, (int) $pdo->query("SELECT records_synced FROM connected_systems WHERE id=$sys")->fetchColumn(), 'records_synced incremented');

// duplicate guard
$qid2 = enqueue_intake($pdo, $sys, null, null, ['object_type'=>'customer','external_ref'=>'CUST-1','collection_date'=>'2025-01-01']);
$res2 = process_intake_item($pdo, $pdo->query("SELECT * FROM intake_queue WHERE id=$qid2")->fetch());
assert_equals('duplicate', $res2['status'], 'duplicate external_ref+category detected');

// no matching rule
$qid3 = enqueue_intake($pdo, $sys, null, null, ['object_type'=>'mystery','external_ref'=>'X-9']);
$res3 = process_intake_item($pdo, $pdo->query("SELECT * FROM intake_queue WHERE id=$qid3")->fetch());
assert_equals('failed', $res3['status'], 'no_matching_rule fails the item');
assert_equals('no_matching_rule', $res3['error'], 'error reported');

// --- Consent signals (E4) ---
$pdo->prepare("INSERT INTO data_records (category_id, record_reference, collection_date, status) VALUES (:c,'MKT-1','2025-01-01','active')")->execute(['c'=>$catMarketing]);
$mktRec = (int) $pdo->lastInsertId();
$sig = record_consent_signal($pdo, $sys, 'MKT-1', 'withdrawal');
assert_true($sig['matched'], 'consent signal matched to record');
$mkt = $pdo->query("SELECT * FROM data_records WHERE id=$mktRec")->fetch();
assert_true($mkt['consent_withdrawn_at'] !== null, 'consent_withdrawn_at set');
assert_true($mkt['retention_end_date'] !== null, 'consent countdown end date set');

$sigU = record_consent_signal($pdo, $sys, 'GHOST-REF', 'withdrawal');
assert_false($sigU['matched'], 'unknown ref stays unmatched');
$pdo->prepare("INSERT INTO data_records (category_id, record_reference, collection_date, status) VALUES (:c,'GHOST-REF','2025-01-01','active')")->execute(['c'=>$catMarketing]);
assert_equals(1, retry_unmatched_consent_signals($pdo), 'retry matches the now-present record');

// --- Outbound disposal dispatch (E3) + execute_disposal hook ---
set_setting($pdo, 'adrs_tier', 'enterprise');   // clears the settings cache too
assert_equals('enterprise', get_setting($pdo, 'adrs_tier'), 'tier flipped to enterprise');

// Dispose the API-captured record -> hook should queue a dispatch to CRM (which has base_url).
assert_true(execute_disposal($pdo, ['id' => $rec['id']]), 'record disposed');
$disp = $pdo->query("SELECT * FROM disposal_dispatches WHERE record_id={$rec['id']}")->fetchAll();
assert_equals(1, count($disp), 'one disposal dispatch queued for the originating system');
assert_equals('delete', $disp[0]['dispatch_type'], 'dispatch carries the disposal method');

// Process dispatches with a stubbed sender (no real HTTP).
$result = process_disposal_dispatches($pdo, 50, fn($url, $payload) => [200, 'ok']);
assert_equals(1, $result['sent'], 'dispatch sent via stub webhook');
assert_equals('confirmed', $pdo->query("SELECT status FROM disposal_dispatches WHERE id={$disp[0]['id']}")->fetchColumn(), 'dispatch confirmed');

// Enterprise daily steps (C): purge integration_logs older than retention window.
$pdo->prepare("INSERT INTO integration_logs (system_id, direction, endpoint, method, status_code, created_at) VALUES (:s,'inbound','/old','GET',200, DATE_SUB(NOW(), INTERVAL 200 DAY))")->execute(['s'=>$sys]);
$pdo->prepare("INSERT INTO integration_logs (system_id, direction, endpoint, method, status_code) VALUES (:s,'inbound','/new','GET',200)")->execute(['s'=>$sys]);
assert_true(purge_integration_logs($pdo) >= 1, 'old integration logs purged (step C)');
assert_equals(1, (int) $pdo->query("SELECT COUNT(*) FROM integration_logs WHERE endpoint='/new'")->fetchColumn(), 'recent log retained');
$steps = run_enterprise_engine_steps($pdo);
assert_true(array_key_exists('logs_purged', $steps) && array_key_exists('consent_retried', $steps), 'enterprise engine steps return a summary');

set_setting($pdo, 'adrs_tier', 'core');  // restore for any later tests
