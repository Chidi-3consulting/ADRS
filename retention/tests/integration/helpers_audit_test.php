<?php
if (!require_db('helpers audit/dsar')) { return; }

$pdo = get_db();

// Need a user row for the performed_by FK.
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Auditor','auditor@x.io','x','admin',1)");
$uid = (int) $pdo->lastInsertId();

$before = (int) $pdo->query("SELECT COUNT(*) c FROM audit_log")->fetch()['c'];
log_audit($pdo, 'user_login', 'user', $uid, $uid, ['note' => 'test'], '127.0.0.1');
$after = (int) $pdo->query("SELECT COUNT(*) c FROM audit_log")->fetch()['c'];
assert_equals($before + 1, $after, 'log_audit inserts one row');

$row = $pdo->query("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1")->fetch();
assert_equals('user_login', $row['action'], 'action stored');
assert_true(str_contains($row['details'], 'test'), 'details JSON stored');

// log_audit must never throw, even with a bad action (silently swallow).
log_audit($pdo, 'not_a_real_action_value', 'system', null, null, null, null);
assert_true(true, 'log_audit swallowed invalid enum without throwing');


