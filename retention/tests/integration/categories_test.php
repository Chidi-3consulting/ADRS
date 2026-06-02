<?php
if (!require_db('categories')) { return; }
require_once __DIR__ . '/../../src/includes/categories_lib.php';
require_once __DIR__ . '/../../src/includes/records_lib.php';

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Cat Admin','catadmin@x.io','x','admin',1)");
$admin = (int) $pdo->lastInsertId();

// Create a date_based category.
$cid = create_category($pdo, [
    'name' => 'Test Invoices', 'compliance_framework' => 'GDPR', 'legal_basis' => 'legal_obligation',
    'retention_period_days' => 30, 'disposal_method' => 'delete', 'disposal_trigger' => 'date_based',
    'requires_dual_approval' => 0, 'review_frequency' => 'quarterly',
], $admin);
$cat = fetch_category($pdo, $cid);
assert_equals(30, (int) $cat['retention_period_days'], 'date_based retention stored');
assert_equals('date_based', $cat['disposal_trigger'], 'trigger stored');

// Consent-withdrawal category forces retention_period_days = 0 (B1).
$consentId = create_category($pdo, [
    'name' => 'Test Marketing Consent', 'legal_basis' => 'consent',
    'retention_period_days' => 999, 'disposal_trigger' => 'consent_withdrawal',
], $admin);
assert_equals(0, (int) fetch_category($pdo, $consentId)['retention_period_days'], 'consent category forces days=0');

// B5 dual approval flag persists.
$dualId = create_category($pdo, [
    'name' => 'Test Health', 'legal_basis' => 'legal_obligation', 'retention_period_days' => 100,
    'disposal_trigger' => 'date_based', 'requires_dual_approval' => 1,
], $admin);
assert_equals(1, (int) fetch_category($pdo, $dualId)['requires_dual_approval'], 'dual approval flag stored');

// B2: editing retention period queues recalculations and does NOT change record dates.
$rec = create_data_record($pdo, ['category_id' => $cid, 'record_reference' => 'INV-1', 'collection_date' => '2025-01-01'], ['id' => $admin, 'role' => 'admin']);
$origEnd = fetch_record($pdo, $rec['id'])['retention_end_date'];
assert_equals('2025-01-31', $origEnd, 'record end = collection + 30');

$res = update_category($pdo, $cid, [
    'name' => 'Test Invoices', 'legal_basis' => 'legal_obligation', 'retention_period_days' => 60,
    'disposal_method' => 'delete', 'disposal_trigger' => 'date_based',
], $admin);
assert_equals(1, $res['recalc_queued'], 'B2: one recalculation queued');
assert_equals($origEnd, fetch_record($pdo, $rec['id'])['retention_end_date'], 'B2: record date UNCHANGED until reviewed');
$pend = $pdo->query("SELECT * FROM pending_recalculations WHERE record_id = {$rec['id']}")->fetch();
assert_equals('2025-03-02', $pend['new_retention_end_date'], 'B2: queued new date = collection + 60');

// soft_delete blocked while an active record exists, allowed once none.
assert_false(soft_delete_category($pdo, $cid, $admin), 'delete blocked with active records');
$pdo->prepare("UPDATE data_records SET status='disposed' WHERE id=?")->execute([$rec['id']]);
assert_true(soft_delete_category($pdo, $cid, $admin), 'delete allowed when no active records');
assert_true(fetch_category($pdo, $cid) === null, 'category soft-deleted');
