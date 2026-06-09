<?php
require_once __DIR__ . '/../../src/includes/billing_lib.php';

assert_equals('₦75,000.00', format_ngn_kobo(7500000), 'formats NGN from kobo');
assert_equals('₦0.00', format_ngn_kobo(0), 'formats zero');
