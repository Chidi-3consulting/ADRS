<?php
require_once __DIR__ . '/../../src/includes/email_templates.php';

[$subj, $html] = email_team_invite('Jane Doe', 'Acme Bank', 'dpo', 'https://example.com/invite/accept?token=abc');
assert_true(str_contains($subj, 'Acme Bank'), 'invite subject includes org');
assert_true(str_contains($html, 'Jane Doe'), 'invite body includes name');
assert_true(str_contains($html, 'Data Protection Officer'), 'invite body includes role label');
