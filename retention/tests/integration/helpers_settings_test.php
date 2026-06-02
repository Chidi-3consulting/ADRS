<?php
if (!require_db('helpers settings')) { return; }

$pdo = get_db();
// Seeded by schema.sql:
assert_equals('30', (string) get_setting($pdo, 'review_alert_days'), 'review_alert_days seeded = 30');
assert_equals('core', (string) get_setting($pdo, 'adrs_tier'), 'adrs_tier seeded = core');
// Unknown key returns the default:
assert_equals('fallback', get_setting($pdo, 'no_such_key_xyz', 'fallback'), 'unknown key uses default');
