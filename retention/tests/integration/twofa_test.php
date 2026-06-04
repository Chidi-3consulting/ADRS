<?php
if (!require_db('2fa')) { return; }
require_once __DIR__ . '/../../src/includes/twofa_lib.php';

// --- TOTP correctness (RFC 6238) ---
$secret = totp_generate_secret();
$now = time();
$code = totp_code($secret, $now);
assert_true((bool) preg_match('/^\d{6}$/', $code), 'TOTP code is 6 digits');
assert_true(totp_verify($secret, $code, $now), 'fresh code verifies');
assert_false(totp_verify($secret, '000000', $now), 'wrong code rejected (unless it happens to match — improbable)');
// Drift tolerance: a code from the previous 30s window still verifies (window=1).
assert_true(totp_verify($secret, totp_code($secret, $now - 30), $now), 'previous-window code accepted within drift');
// Outside the window it fails.
assert_false(totp_verify($secret, totp_code($secret, $now - 300), $now), 'far-past code rejected');

// base32 round-trip
assert_equals('Hello', base32_decode(base32_encode('Hello')), 'base32 round-trips');

// Known RFC 6238 vector: secret "12345678901234567890" (ASCII) at T=59 => 287082.
$rfcSecret = base32_encode('12345678901234567890');
assert_equals('287082', totp_code($rfcSecret, 59), 'matches RFC 6238 test vector');

// --- Recovery codes ---
$rc = generate_recovery_codes(8);
assert_equals(8, count($rc['plain']), '8 recovery codes generated');
assert_equals(8, count($rc['hashed']), '8 hashes generated');
$remaining = consume_recovery_code($rc['hashed'], $rc['plain'][2]);
assert_true(is_array($remaining) && count($remaining) === 7, 'consuming a code removes it');
assert_true(consume_recovery_code($remaining, $rc['plain'][2]) === null, 'a consumed code cannot be reused');
assert_true(consume_recovery_code($rc['hashed'], 'NOTA-CODE0') === null, 'bogus recovery code rejected');

// --- Enable/disable persistence + login gating ---
require_once __DIR__ . '/../../src/includes/auth.php';
$pdo = get_db();
$pdo->prepare("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('TwoFA','2fa@x.io',:h,'admin',1)")
    ->execute(['h' => password_hash('secret123', PASSWORD_BCRYPT)]);
$uid = (int) $pdo->lastInsertId();

assert_true(verify_credentials($pdo, '2fa@x.io', 'secret123') !== null, 'credentials verify before 2FA');
enable_user_2fa($pdo, $uid, $secret, $rc['hashed']);
$fresh = $pdo->query("SELECT twofa_enabled, twofa_secret FROM users WHERE id=$uid")->fetch();
assert_equals(1, (int) $fresh['twofa_enabled'], '2FA flag persisted');
assert_equals($secret, $fresh['twofa_secret'], 'secret persisted');
disable_user_2fa($pdo, $uid);
assert_equals(0, (int) $pdo->query("SELECT twofa_enabled FROM users WHERE id=$uid")->fetchColumn(), '2FA disabled');
