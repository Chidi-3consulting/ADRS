<?php
if (!require_db('reports')) { return; }
require_once __DIR__ . '/../../src/includes/categories_lib.php';
require_once __DIR__ . '/../../src/engine/engine_lib.php';
require_once __DIR__ . '/../../src/includes/reports_lib.php';

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Rep Admin','repadmin@x.io','x','admin',1)");
$admin = (int) $pdo->lastInsertId();

$cat = create_category($pdo, ['name'=>'REP Cat','legal_basis'=>'legal_obligation','retention_period_days'=>1,'disposal_trigger'=>'date_based','disposal_method'=>'delete'], $admin);
$pdo->prepare("INSERT INTO data_records (category_id,record_reference,collection_date,retention_end_date,status) VALUES (?,?,?,?,'due_review')")
    ->execute([$cat, 'REP-1', '2020-01-01', date('Y-m-d', strtotime('-2 days'))]);
$rid = (int) $pdo->lastInsertId();
assert_true(execute_disposal($pdo, ['id' => $rid]), 'report fixture record disposed');

$year = (int) date('Y');
$report = build_ndpr_report($pdo, $year);
assert_equals($year, $report['year'], 'report year');
assert_true($report['total_categories'] >= 30, 'report counts seeded + custom categories');
assert_true($report['disposed_by_method']['delete'] >= 1, 'report counts a delete disposal this year');
assert_true($report['disposed_total'] >= 1, 'report disposed total');
assert_true($report['audit_events'] >= 1, 'report counts audit events');

$rows = ndpr_report_to_csv_rows($report);
assert_equals('NDPR Annual Compliance Report', $rows[0][0], 'csv has report title');
assert_true(count($rows) > 8, 'csv has metric rows');
