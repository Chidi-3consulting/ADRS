<?php
require_once __DIR__ . '/../../src/includes/tenant_lib.php';

assert_equals('acmebank.com', normalize_org_domain('AcmeBank.COM'), 'lowercase domain');
assert_equals('acmebank.com', normalize_org_domain('https://www.acmebank.com/about'), 'strip protocol and www');
assert_equals('', normalize_org_domain(''), 'empty input');
assert_equals('', normalize_org_domain('not-a-domain'), 'invalid domain');

assert_true(email_matches_org_domain('Jane.Doe@AcmeBank.com', 'acmebank.com'), 'email domain match');
assert_false(email_matches_org_domain('jane@gmail.com', 'acmebank.com'), 'email domain mismatch');

assert_equals(
    'Use your company domain, not a personal email provider (e.g. gmail.com).',
    org_domain_policy_error('gmail.com'),
    'block free providers'
);
assert_true(org_domain_policy_error('acmebank.com') === null, 'valid corp domain');
