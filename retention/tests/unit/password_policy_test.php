<?php
assert_true(password_policy_error('short1') !== null, 'under 10 chars rejected');
assert_true(password_policy_error('abcdefghijkl') !== null, 'letters-only rejected');
assert_true(password_policy_error('123456789012') !== null, 'digits-only rejected');
assert_true(password_policy_error('Password123') === null, 'valid password accepted');
assert_true(password_policy_error('aVeryLongButLettersOnlyPassphrase') !== null, 'long but no digit rejected');
