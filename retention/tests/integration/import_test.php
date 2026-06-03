<?php
if (!require_db('import')) { return; }
require_once __DIR__ . '/../../src/includes/categories_lib.php';
require_once __DIR__ . '/../../src/includes/import_lib.php';

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Imp Admin','impadmin@x.io','x','admin',1)");
$admin = (int) $pdo->lastInsertId();
create_category($pdo, ['name'=>'IMP Cat','legal_basis'=>'contract','retention_period_days'=>50,'disposal_trigger'=>'date_based'], $admin);

$csv = "category_name,record_reference,data_subject_type,collection_date\n"
     . "IMP Cat,IMP-1,Customer,2025-01-01\n"
     . "IMP Cat,IMP-2,Customer,2025-02-01\n"
     . "Nonexistent Cat,IMP-3,Customer,2025-03-01\n"   // unknown category -> error
     . "IMP Cat,,Customer,2025-04-01\n"                 // missing reference -> error
     . "IMP Cat,IMP-5,Customer,not-a-date\n";           // bad date -> error

$rows = parse_csv($csv);
assert_equals(5, count($rows), 'parsed 5 data rows');

$check = validate_import_rows($pdo, $rows);
assert_equals(2, count($check['valid']), 'two valid rows');
assert_equals(3, count($check['errors']), 'three rows flagged with errors');

$before = (int) $pdo->query("SELECT COUNT(*) c FROM data_records WHERE record_reference IN ('IMP-1','IMP-2')")->fetch()['c'];
$summary = commit_import($pdo, 'test.csv', $rows, $admin);
assert_equals(2, $summary['imported'], 'two records imported');
assert_equals(3, $summary['errors'], 'three errors recorded');

$imp1 = $pdo->query("SELECT * FROM data_records WHERE record_reference='IMP-1'")->fetch();
assert_equals('2025-02-20', $imp1['retention_end_date'], 'imported record end = collection + 50');

$job = $pdo->query("SELECT * FROM import_jobs ORDER BY id DESC LIMIT 1")->fetch();
assert_equals('imported', $job['status'], 'import job recorded as imported');
assert_equals(5, (int) $job['total_rows'], 'job total rows recorded');
