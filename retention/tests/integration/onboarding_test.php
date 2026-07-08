<?php
if (!require_db('onboarding')) { return; }

require_once __DIR__ . '/../../src/includes/public_layout.php';

$pdo = get_db();

// Seeded test DB should already be marked complete.
assert_true(setup_is_complete($pdo), 'seeded install is setup-complete');

// Public signup gate.
$prevSignup = get_setting($pdo, 'allow_public_signup', '0');
set_setting($pdo, 'allow_public_signup', '0');
clear_setting_cache();
assert_false(public_signup_enabled($pdo), 'signup disabled by default');
set_setting($pdo, 'allow_public_signup', '1');
clear_setting_cache();
assert_true(public_signup_enabled($pdo), 'signup enabled via setting');
set_setting($pdo, 'allow_public_signup', $prevSignup);
clear_setting_cache();

// Category seed import is idempotent on a seeded DB.
assert_equals(0, import_category_seed($pdo), 'seeded DB skips category import');

// must_change_password on seeded admin.
$row = $pdo->query("SELECT must_change_password FROM users WHERE email='admin@3consult-ng.com'")->fetch();
assert_equals(1, (int) ($row['must_change_password'] ?? 0), 'seeded admin must change password');

// Simulated fresh install (in-memory checks only — restore settings after).
$prevSetup = get_setting($pdo, 'setup_complete', '1');
set_setting($pdo, 'setup_complete', '0');
clear_setting_cache();
assert_true(setup_is_complete($pdo), 'legacy admin still implies setup complete');
set_setting($pdo, 'setup_complete', $prevSetup);
clear_setting_cache();
