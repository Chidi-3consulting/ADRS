<?php
if (!require_db('records')) { return; }
require_once __DIR__ . '/../../src/includes/categories_lib.php';
require_once __DIR__ . '/../../src/includes/records_lib.php';

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Rec Admin','recadmin@x.io','x','admin',1)");
$admin = (int) $pdo->lastInsertId();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Owner A','ownera@x.io','x','data_owner',1)");
$ownerA = (int) $pdo->lastInsertId();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Owner B','ownerb@x.io','x','data_owner',1)");
$ownerB = (int) $pdo->lastInsertId();

// Category owned by Owner A, 90 days date_based.
$catA = create_category($pdo, ['name'=>'CatA','legal_basis'=>'contract','retention_period_days'=>90,'disposal_trigger'=>'date_based','owner_id'=>$ownerA], $admin);
// Consent category.
$catC = create_category($pdo, ['name'=>'CatConsent','legal_basis'=>'consent','disposal_trigger'=>'consent_withdrawal','owner_id'=>$ownerA], $admin);

// date_based record by admin → retention end computed.
$r1 = create_data_record($pdo, ['category_id'=>$catA,'record_reference'=>'R-1','collection_date'=>'2025-01-01'], ['id'=>$admin,'role'=>'admin']);
assert_equals('2025-04-01', $r1['retention_end'], 'date_based end = collection + 90');

// consent record → null end date.
$r2 = create_data_record($pdo, ['category_id'=>$catC,'record_reference'=>'R-2','collection_date'=>'2025-01-01'], ['id'=>$admin,'role'=>'admin']);
assert_true($r2['retention_end'] === null, 'consent record has no end date until withdrawal');

// B4: Owner B cannot create in Owner A's category.
assert_throws(fn() => create_data_record($pdo, ['category_id'=>$catA,'record_reference'=>'BAD'], ['id'=>$ownerB,'role'=>'data_owner']), 'B4: owner blocked from foreign category');

// B4: Owner A can create in own category; flagged created_by_owner, collection date today.
$r3 = create_data_record($pdo, ['category_id'=>$catA,'record_reference'=>'R-3','collection_date'=>'2000-01-01'], ['id'=>$ownerA,'role'=>'data_owner']);
$row3 = fetch_record($pdo, $r3['id']);
assert_equals(1, (int) $row3['created_by_owner'], 'B4: created_by_owner flag set');
assert_equals(date('Y-m-d'), $row3['collection_date'], 'B4: owner collection date forced to today');

// B3: reassign to a new category with recalculation updates the end date and preserves origin.
$catA2 = create_category($pdo, ['name'=>'CatA2','legal_basis'=>'contract','retention_period_days'=>10,'disposal_trigger'=>'date_based'], $admin);
reassign_category($pdo, $r1['id'], $catA2, $admin, true);
$row1 = fetch_record($pdo, $r1['id']);
assert_equals($catA2, (int) $row1['category_id'], 'B3: category changed');
assert_equals($catA, (int) $row1['original_category_id'], 'B3: original category preserved');
assert_equals('2025-01-11', $row1['retention_end_date'], 'B3: recalculated end = collection + 10');
