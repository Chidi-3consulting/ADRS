<?php
if (!require_db('audit chain')) { return; }

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Chain','chain@x.io','x','admin',1)");
$uid = (int) $pdo->lastInsertId();

// Write a series of audit entries (with varied details, incl. multi-key objects).
log_audit($pdo, 'user_login', 'user', $uid, $uid, ['ip' => '1.1.1.1', 'agent' => 'test'], '1.1.1.1');
log_audit($pdo, 'category_created', 'data_category', 1, $uid, ['name' => 'X', 'framework' => 'GDPR'], '1.1.1.1');
log_audit($pdo, 'record_created', 'data_record', 5, null, null, null);

$res = verify_audit_chain($pdo);
assert_true($res['ok'], 'intact chain verifies');
assert_true($res['checked'] >= 3, 'verified all rows: ' . $res['checked']);

// Tamper: silently alter a row's content WITHOUT recomputing its hash (simulating an attacker).
$row = $pdo->query("SELECT id FROM audit_log WHERE action='category_created' ORDER BY id DESC LIMIT 1")->fetch();
$pdo->prepare("UPDATE audit_log SET details = JSON_OBJECT('name','TAMPERED','framework','GDPR') WHERE id = :id")->execute(['id' => $row['id']]);

$res2 = verify_audit_chain($pdo);
assert_false($res2['ok'], 'tampered content breaks the chain');
assert_equals((int) $row['id'], $res2['broken_at'], 'verifier pinpoints the tampered row');

// Tamper detection also fires if a row is deleted (chain link breaks).
$pdo->exec("DELETE FROM audit_log WHERE id = " . (int) $row['id']);
assert_false(verify_audit_chain($pdo)['ok'], 'a deleted row breaks the prev_hash link');
