<?php
if (!require_db('dsar')) { return; }
require_once __DIR__ . '/../../src/includes/dsar_lib.php';

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('DSAR Admin','dsaradmin@x.io','x','admin',1)");
$admin = (int) $pdo->lastInsertId();

$res = create_dsar($pdo, [
    'request_type' => 'access', 'compliance_framework' => 'GDPR',
    'data_subject_name' => 'Jane Subject', 'data_subject_email' => 'jane@example.test',
    'received_date' => '2026-01-10',
], $admin);
assert_true((bool) preg_match('/^DSAR-\d{4}-\d{4}$/', $res['reference']), 'DSAR reference format: ' . $res['reference']);

$d = fetch_dsar($pdo, $res['id']);
assert_equals('2026-02-09', $d['due_date'], 'due date = received + 30 days');
assert_equals('open', $d['status'], 'new DSAR is open');

verify_dsar_identity($pdo, $res['id'], $admin);
assert_equals(1, (int) fetch_dsar($pdo, $res['id'])['identity_verified'], 'identity marked verified');

update_dsar_status($pdo, $res['id'], 'in_progress', $admin);
assert_equals('in_progress', fetch_dsar($pdo, $res['id'])['status'], 'status updated');

update_dsar_status($pdo, $res['id'], 'completed', $admin, 'Provided data export');
$done = fetch_dsar($pdo, $res['id']);
assert_equals('completed', $done['status'], 'status completed');
assert_true($done['completed_at'] !== null, 'completed_at stamped');

assert_throws(fn() => update_dsar_status($pdo, $res['id'], 'bogus', $admin), 'invalid status rejected');
