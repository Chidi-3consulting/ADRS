<?php
if (!require_db('recalc apply')) { return; }
require_once __DIR__ . '/../../src/includes/categories_lib.php';
require_once __DIR__ . '/../../src/includes/records_lib.php';

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Recalc DPO','recalcdpo@x.io','x','dpo',1)");
$dpo = (int) $pdo->lastInsertId();

$cid = create_category($pdo, ['name'=>'RECALC Cat','legal_basis'=>'legal_obligation','retention_period_days'=>30,'disposal_trigger'=>'date_based'], $dpo);
$r = create_data_record($pdo, ['category_id'=>$cid,'record_reference'=>'RC-1','collection_date'=>'2025-01-01'], ['id'=>$dpo,'role'=>'dpo']);
$origEnd = fetch_record($pdo, $r['id'])['retention_end_date']; // 2025-01-31

update_category($pdo, $cid, ['name'=>'RECALC Cat','legal_basis'=>'legal_obligation','retention_period_days'=>60,'disposal_trigger'=>'date_based'], $dpo);
$pending = $pdo->query("SELECT * FROM pending_recalculations WHERE record_id={$r['id']} AND status='pending'")->fetch();
assert_true($pending !== false, 'recalculation queued');
assert_equals($origEnd, fetch_record($pdo, $r['id'])['retention_end_date'], 'record date still unchanged before decision');

apply_recalculation($pdo, (int) $pending['id'], 'recalculate', $dpo);
assert_equals('2025-03-02', fetch_record($pdo, $r['id'])['retention_end_date'], 'recalculate applies new date');
assert_equals('recalculate', $pdo->query("SELECT status FROM pending_recalculations WHERE id={$pending['id']}")->fetch()['status'], 'queue row marked reviewed');

assert_throws(fn() => apply_recalculation($pdo, (int) $pending['id'], 'recalculate', $dpo), 'cannot re-apply a reviewed recalculation');
