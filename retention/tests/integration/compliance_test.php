<?php
if (!require_db('compliance')) { return; }
require_once __DIR__ . '/../../src/includes/categories_lib.php';
require_once __DIR__ . '/../../src/includes/compliance_lib.php';

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Comp','comp@x.io','x','dpo',1)");
$actor = (int) $pdo->lastInsertId();

// --- DPIA risk scoring ---
assert_equals('low', dpia_risk_level(1, 3), 'score 3 -> low');
assert_equals('medium', dpia_risk_level(3, 3), 'score 9 -> medium');
assert_equals('high', dpia_risk_level(5, 5), 'score 25 -> high');
$dpiaId = create_dpia($pdo, ['title'=>'New CRM rollout','likelihood_score'=>4,'severity_score'=>4,'necessity_score'=>3,'proportionality_score'=>3], $actor);
$dpia = $pdo->query("SELECT * FROM dpia_assessments WHERE id=$dpiaId")->fetch();
assert_equals(16, (int) $dpia['risk_score'], 'risk_score = likelihood*severity');
assert_equals('high', $dpia['risk_level'], 'risk level stored');
set_dpia_status($pdo, $dpiaId, 'approved', $actor);
$dpia2 = $pdo->query("SELECT * FROM dpia_assessments WHERE id=$dpiaId")->fetch();
assert_equals('approved', $dpia2['status'], 'dpia approved');
assert_true($dpia2['approved_at'] !== null, 'approved_at set');

// --- Breach register (72h) ---
assert_equals('2025-01-04 10:00:00', breach_notify_deadline('2025-01-01 10:00:00'), 'deadline = discovered + 72h');
assert_equals(72, breach_hours_remaining('2025-01-04 10:00:00', strtotime('2025-01-01 10:00:00')), '72h remaining at discovery');
assert_true(breach_hours_remaining('2025-01-01 10:00:00', strtotime('2025-01-05 10:00:00')) < 0, 'past deadline is negative');
$b1 = create_breach($pdo, ['title'=>'Laptop lost','severity'=>'high','discovered_at'=>date('Y-m-d H:i:s'),'affected_records'=>120], $actor);
assert_true((bool) preg_match('/^BR-\d{4}-\d{4}$/', $b1['reference']), "breach ref format: {$b1['reference']}");
$b2 = create_breach($pdo, ['title'=>'Second','severity'=>'low','discovered_at'=>date('Y-m-d H:i:s')], $actor);
assert_true($b2['reference'] !== $b1['reference'], 'breach references are unique/sequential');
update_breach_status($pdo, $b1['id'], 'notified', $actor);
$bn = $pdo->query("SELECT * FROM breach_incidents WHERE id={$b1['id']}")->fetch();
assert_equals('notified', $bn['status'], 'breach marked notified');
assert_true($bn['notified_authority_at'] !== null, 'authority notification timestamp set');

// --- Consent receipts ---
$r = issue_consent_receipt($pdo, ['data_subject_ref'=>'CUST-77','purpose'=>'Marketing','lawful_basis'=>'consent','channel'=>'web','given_at'=>date('Y-m-d H:i:s')], $actor);
assert_equals(64, strlen($r['receipt_hash']), 'receipt hash is sha-256');
withdraw_consent_receipt($pdo, $r['id'], $actor);
assert_true($pdo->query("SELECT withdrawn_at FROM consent_receipts WHERE id={$r['id']}")->fetchColumn() !== null, 'receipt withdrawn timestamp set');

// --- RoPA auto-generation from categories ---
$before = (int) $pdo->query("SELECT COUNT(*) FROM ropa_entries")->fetchColumn();
$made = generate_ropa_from_categories($pdo, $actor);
$after = (int) $pdo->query("SELECT COUNT(*) FROM ropa_entries")->fetchColumn();
assert_true($made > 0, 'RoPA entries generated from categories');
assert_equals($before + $made, $after, 'RoPA rows persisted');
assert_equals(0, generate_ropa_from_categories($pdo, $actor), 'second run creates none (idempotent)');
