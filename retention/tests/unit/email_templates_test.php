<?php
require_once __DIR__ . '/../../src/includes/email_templates.php';

$html = email_layout('Hello Title', '<p>Body here</p>');
assert_true(str_contains($html, 'Hello Title'), 'layout includes the title');
assert_true(str_contains($html, 'Body here'), 'layout includes the body');
assert_true(str_contains($html, '3Consulting'), 'layout includes branding');

[$subject, $body] = email_password_reset('Ada', 'https://example.test/reset?t=abc');
assert_equals('Reset your ADRS password', $subject, 'reset subject');
assert_true(str_contains($body, 'https://example.test/reset?t=abc'), 'reset email contains the link');
assert_true(str_contains($body, 'Ada'), 'reset email greets the user');

$n = render_notification_email(['subject' => 'Review due', 'message' => "Line1\nLine2"]);
assert_true(str_contains($n, 'Review due'), 'notification email shows subject');
assert_true(str_contains($n, 'Line1'), 'notification email shows message');
