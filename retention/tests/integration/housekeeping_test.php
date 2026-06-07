<?php
if (!require_db('housekeeping')) { return; }
require_once __DIR__ . '/../../src/engine/engine_lib.php';
$pdo = get_db();

// Old failed attempt should be pruned; a recent one kept.
$pdo->exec("INSERT INTO login_attempts (email, ip_address, success, created_at) VALUES ('old@x.io','1.1.1.1',0, DATE_SUB(NOW(), INTERVAL 10 DAY))");
$pdo->exec("INSERT INTO login_attempts (email, ip_address, success) VALUES ('new@x.io','1.1.1.1',0)");
// Expired reset token should be pruned.
$pdo->exec("INSERT INTO password_resets (email, token_hash, expires_at) VALUES ('r@x.io', REPEAT('a',64), DATE_SUB(NOW(), INTERVAL 10 DAY))");

$r = run_housekeeping($pdo);
assert_true($r['login_attempts'] >= 1, 'old login attempt pruned');
assert_true($r['password_resets'] >= 1, 'expired reset token pruned');
assert_equals(1, (int) $pdo->query("SELECT COUNT(*) FROM login_attempts")->fetchColumn(), 'recent login attempt retained');
