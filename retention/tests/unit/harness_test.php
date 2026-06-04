<?php
assert_true(true, 'harness boolean true');
assert_equals(4, 2 + 2, 'harness arithmetic');
assert_throws(fn() => 1 / 0, 'harness catches errors');
