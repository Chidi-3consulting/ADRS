<?php
if (!require_db('db connection')) { return; }

$pdo = get_db();
assert_true($pdo instanceof PDO, 'get_db returns PDO');

$tz = $pdo->query("SELECT @@session.time_zone AS tz")->fetch()['tz'];
assert_equals('+01:00', $tz, 'session time zone is +01:00');

// Schema imported: data_categories should be seeded (30 categories) by schema.sql/seed.
$count = (int) $pdo->query("SELECT COUNT(*) c FROM data_categories")->fetch()['c'];
assert_true($count >= 30, "schema+seed loaded: $count categories");
