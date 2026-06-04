<?php
// retention_end_date(collection_date, days) = collection + N days (D4 fixed-days)
assert_equals('2025-01-31', retention_end_date('2025-01-01', 30), 'retention_end_date adds days');
assert_equals('2026-01-01', retention_end_date('2025-01-01', 365), 'retention_end_date 1 year');

// days_until is negative when the date is in the past
assert_true(days_until(date('Y-m-d', strtotime('-5 days'))) < 0, 'days_until past is negative');
assert_equals(0, days_until(date('Y-m-d')), 'days_until today is 0');

// calculate_retention_days converts units
assert_equals(30, calculate_retention_days(30, 'days'), 'days unit');
assert_equals(365, calculate_retention_days(1, 'years'), 'years unit');
assert_equals(90, calculate_retention_days(3, 'months'), 'months unit (30/mo)');

// format_date handles null
assert_equals('—', format_date(null), 'format_date null shows dash');
