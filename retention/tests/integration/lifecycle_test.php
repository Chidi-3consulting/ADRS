<?php
if (!require_db('lifecycle')) { return; }
require_once __DIR__ . '/../../src/includes/categories_lib.php';
require_once __DIR__ . '/../../src/includes/lifecycle_lib.php';

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('LC U1','lc1@x.io','x','admin',1)");
$u1 = (int) $pdo->lastInsertId();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('LC U2','lc2@x.io','x','dpo',1)");
$u2 = (int) $pdo->lastInsertId();

$normal = create_category($pdo, ['name'=>'LC Normal','legal_basis'=>'legal_obligation','retention_period_days'=>30,'disposal_trigger'=>'date_based','disposal_method'=>'archive','requires_dual_approval'=>0], $u1);
$dual   = create_category($pdo, ['name'=>'LC Dual','legal_basis'=>'legal_obligation','retention_period_days'=>30,'disposal_trigger'=>'date_based','disposal_method'=>'archive','requires_dual_approval'=>1], $u1);
$consent= create_category($pdo, ['name'=>'LC Consent','legal_basis'=>'consent','disposal_trigger'=>'consent_withdrawal'], $u1);

$mk = function(int $cat, string $ref) use ($pdo): int {
    $pdo->prepare("INSERT INTO data_records (category_id,record_reference,collection_date,retention_end_date,status) VALUES (?,?,?,?,'due_review')")
        ->execute([$cat, $ref, '2020-01-01', '2020-02-01']);
    return (int) $pdo->lastInsertId();
};
$row = fn(int $id) => $pdo->query("SELECT * FROM data_records WHERE id=$id")->fetch();

// Standard category: single approver disposes immediately.
$rNormal = $mk($normal, 'LC-N');
assert_equals('disposed', request_disposal($pdo, $rNormal, $u1), 'standard disposal completes with one approver');
assert_equals('disposed', $row($rNormal)['status'], 'standard record disposed');

// Sensitive category: requires two different users (B5).
$rDual = $mk($dual, 'LC-D');
assert_equals('pending_second_approval', request_disposal($pdo, $rDual, $u1), 'dual category needs a second approval');
assert_equals('disposal_requested', $row($rDual)['status'], 'status is disposal_requested');
assert_throws(fn() => approve_disposal($pdo, $rDual, $u1), 'B5: same user cannot approve their own request');
assert_equals('disposal_requested', $row($rDual)['status'], 'still pending after same-user attempt');
approve_disposal($pdo, $rDual, $u2);
assert_equals('disposed', $row($rDual)['status'], 'second different user completes disposal');

// Legal hold blocks disposal; lifting restores it.
$rHold = $mk($normal, 'LC-H');
set_legal_hold($pdo, $rHold, 'Litigation pending', $u1);
assert_equals(1, (int) $row($rHold)['legal_hold'], 'legal hold set');
assert_throws(fn() => request_disposal($pdo, $rHold, $u1), 'disposal blocked while on legal hold');
assert_throws(fn() => set_legal_hold($pdo, $rHold, '', $u1), 'legal hold requires a documented reason');
lift_legal_hold($pdo, $rHold, $u1);
assert_equals(0, (int) $row($rHold)['legal_hold'], 'legal hold lifted');

// Consent withdrawal sets a 30-day disposal clock (B1).
$rConsent = $mk($consent, 'LC-C');
$pdo->prepare("UPDATE data_records SET retention_end_date=NULL, status='active' WHERE id=?")->execute([$rConsent]);
$end = log_consent_withdrawal($pdo, $rConsent, $u1);
assert_equals(date('Y-m-d', strtotime('+30 days')), $end, 'consent withdrawal sets +30 day disposal date');
assert_true($row($rConsent)['consent_withdrawn_at'] !== null, 'consent_withdrawn_at recorded');
