<?php
if (!require_db('login throttle')) { return; }
require_once __DIR__ . '/../../src/includes/auth.php';
$pdo = get_db();

$ip = '203.0.113.9';
// Below the threshold: not throttled.
for ($i = 0; $i < 4; $i++) { record_login_attempt($pdo, 'victim@x.io', $ip, false); }
assert_equals(0, login_throttle_seconds($pdo, 'victim@x.io', $ip), '4 failures -> not throttled');

// 5th failure trips the lock.
record_login_attempt($pdo, 'victim@x.io', $ip, false);
assert_true(login_throttle_seconds($pdo, 'victim@x.io', $ip) > 0, '5 failures -> throttled');

// A different, clean email from a different IP is unaffected.
assert_equals(0, login_throttle_seconds($pdo, 'other@x.io', '198.51.100.2'), 'unrelated user not throttled');

// Same IP, different email is also throttled (slows credential stuffing from one host).
assert_true(login_throttle_seconds($pdo, 'newtarget@x.io', $ip) > 0, 'same IP throttles across emails');

// Old failures (outside the 15-min window) do not count.
$pdo->exec("UPDATE login_attempts SET created_at = DATE_SUB(NOW(), INTERVAL 30 MINUTE) WHERE ip_address = '203.0.113.9'");
assert_equals(0, login_throttle_seconds($pdo, 'victim@x.io', $ip), 'expired failures no longer throttle');

// A successful attempt is recorded too.
$before = (int) $pdo->query("SELECT COUNT(*) FROM login_attempts WHERE success=1")->fetchColumn();
record_login_attempt($pdo, 'good@x.io', $ip, true);
assert_equals($before + 1, (int) $pdo->query("SELECT COUNT(*) FROM login_attempts WHERE success=1")->fetchColumn(), 'success recorded');
