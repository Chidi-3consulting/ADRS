<?php
if (!require_db('engine')) { return; }
require_once __DIR__ . '/../../src/includes/categories_lib.php';
require_once __DIR__ . '/../../src/engine/engine_lib.php';

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Eng Admin','engadmin@x.io','x','admin',1)");
$admin = (int) $pdo->lastInsertId();

// Categories with distinct disposal behaviours.
$catNormal  = create_category($pdo, ['name'=>'ENG Normal','legal_basis'=>'legal_obligation','retention_period_days'=>30,'disposal_trigger'=>'date_based','disposal_method'=>'delete','requires_dual_approval'=>0], $admin);
$catDual    = create_category($pdo, ['name'=>'ENG Dual','legal_basis'=>'legal_obligation','retention_period_days'=>30,'disposal_trigger'=>'date_based','disposal_method'=>'delete','requires_dual_approval'=>1], $admin);
$catAnon    = create_category($pdo, ['name'=>'ENG Anon','legal_basis'=>'legal_obligation','retention_period_days'=>30,'disposal_trigger'=>'date_based','disposal_method'=>'anonymise','requires_dual_approval'=>0], $admin);
$catArchive = create_category($pdo, ['name'=>'ENG Archive','legal_basis'=>'legal_obligation','retention_period_days'=>30,'disposal_trigger'=>'date_based','disposal_method'=>'archive','requires_dual_approval'=>0], $admin);
$catConsent = create_category($pdo, ['name'=>'ENG Consent','legal_basis'=>'consent','disposal_trigger'=>'consent_withdrawal','disposal_method'=>'delete'], $admin);

$yesterday = date('Y-m-d', strtotime('-1 day'));
$future    = date('Y-m-d', strtotime('+10 days'));
$ins = function(int $cat, string $ref, ?string $end, string $status='active', int $hold=0, ?string $consent=null) use ($pdo): int {
    $pdo->prepare(
        "INSERT INTO data_records (category_id, record_reference, data_subject_type, collection_date, retention_end_date, status, legal_hold, consent_withdrawn_at)
         VALUES (:c,:r,'Customer','2020-01-01',:e,:s,:h,:cw)"
    )->execute(['c'=>$cat,'r'=>$ref,'e'=>$end,'s'=>$status,'h'=>$hold,'cw'=>$consent]);
    return (int) $pdo->lastInsertId();
};

$A = $ins($catNormal,  'ENG-A', $yesterday);                                  // overdue normal -> dispose (delete)
$B = $ins($catDual,    'ENG-B', $yesterday);                                  // overdue SENSITIVE -> must NOT auto-dispose
$C = $ins($catNormal,  'ENG-C', $yesterday, 'active', 1);                     // overdue but legal hold -> protected
$D = $ins($catConsent, 'ENG-D', null, 'active', 0, date('Y-m-d H:i:s', strtotime('-40 days'))); // consent withdrawn 40d ago
$E = $ins($catNormal,  'ENG-E', $future);                                     // within window -> flag only
$F = $ins($catAnon,    'ENG-F', $yesterday);                                  // overdue -> anonymise
$G = $ins($catArchive, 'ENG-G', $yesterday);                                  // overdue -> archive

$s = run_retention_engine($pdo);
$row = fn(int $id) => $pdo->query("SELECT * FROM data_records WHERE id=$id")->fetch();

// ---- THE CRITICAL SAFEGUARD (B5 regression guard) ----
assert_equals('due_review', $row($B)['status'], 'CRITICAL: dual-approval record must NOT be auto-disposed');
assert_true($s['dual_skipped'] >= 1, 'engine reports a dual-approval skip');

// Normal overdue record disposed via delete (soft-deleted).
assert_equals('disposed', $row($A)['status'], 'normal overdue record disposed');
assert_true($row($A)['deleted_at'] !== null, 'delete method sets deleted_at');

// Legal hold protects record.
assert_equals('active', $row($C)['status'], 'legal-hold record protected from disposal');

// Consent disposal.
assert_equals('disposed', $row($D)['status'], 'consent-withdrawn record disposed after countdown');

// Within-window record flagged but not disposed.
assert_equals('due_review', $row($E)['status'], 'within-window record flagged, not disposed');

// Anonymise nulls PII; archive retains data.
$f = $row($F);
assert_equals('disposed', $f['status'], 'anonymise record disposed');
assert_true(str_starts_with($f['record_reference'], 'ANONYMISED-'), 'anonymise scrubs the reference');
assert_true($f['data_subject_type'] === null, 'anonymise nulls data_subject_type');
$g = $row($G);
assert_equals('disposed', $g['status'], 'archive record disposed');
assert_equals('ENG-G', $g['record_reference'], 'archive retains the reference (data kept)');

// Summary counts: A, F, G auto-disposed = 3; consent = 1.
assert_equals(3, $s['auto_disposed'], 'three date-based records auto-disposed');
assert_equals(1, $s['consent_disposed'], 'one consent record disposed');

// Idempotency: a second run disposes nothing new and B still survives.
$s2 = run_retention_engine($pdo);
assert_equals(0, $s2['auto_disposed'], 'second run auto-disposes nothing (idempotent)');
assert_equals('due_review', $row($B)['status'], 'dual-approval record still protected after re-run');

// execute_disposal is idempotent on an already-disposed record.
assert_false(execute_disposal($pdo, ['id' => $A]), 'execute_disposal skips already-disposed record');

// Escalation (B7): a record flagged > escalation window escalates once, then not again.
$pdo->prepare("UPDATE data_records SET review_flagged_at = DATE_SUB(NOW(), INTERVAL 20 DAY), escalation_sent_at = NULL WHERE id = ?")->execute([$B]);
assert_equals(1, engine_escalate($pdo, 14), 'overdue review escalates');
assert_true($row($B)['escalation_sent_at'] !== null, 'escalation timestamp set');
assert_equals(0, engine_escalate($pdo, 14), 'no double escalation');
