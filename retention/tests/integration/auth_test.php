<?php
if (!require_db('auth')) { return; }

$pdo = get_db();

// Seed a known user with bcrypt of 'password'.
$hash = password_hash('password', PASSWORD_BCRYPT);
$pdo->prepare("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('T','t@x.io',:h,'admin',1)")
    ->execute(['h' => $hash]);

assert_true(login_user($pdo, 't@x.io', 'password'), 'login succeeds with correct password');
assert_false(login_user($pdo, 't@x.io', 'wrong'), 'login fails with wrong password');
assert_false(login_user($pdo, 'nobody@x.io', 'password'), 'login fails unknown email');

// Inactive users cannot log in.
$pdo->exec("UPDATE users SET is_active=0 WHERE email='t@x.io'");
assert_false(login_user($pdo, 't@x.io', 'password'), 'inactive user cannot log in');

// Password reset token lifecycle.
$pdo->exec("UPDATE users SET is_active=1 WHERE email='t@x.io'");
$raw = create_password_reset_token($pdo, 't@x.io');
assert_true(is_string($raw) && strlen($raw) === 64, 'reset token is 64 hex chars');
assert_true(validate_reset_token($pdo, 't@x.io', $raw), 'valid token validates');
assert_false(validate_reset_token($pdo, 't@x.io', 'deadbeef'), 'bad token rejected');
consume_reset_token($pdo, 't@x.io');
assert_false(validate_reset_token($pdo, 't@x.io', $raw), 'consumed token no longer valid');
