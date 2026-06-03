<?php
if (!require_db('attachments')) { return; }
require_once __DIR__ . '/../../src/includes/categories_lib.php';
require_once __DIR__ . '/../../src/includes/attachments_lib.php';

// Pure validation rules.
assert_true(attachment_validate('ok.pdf', 1000) === null, 'valid pdf accepted');
assert_true(attachment_validate('big.pdf', 11 * 1024 * 1024) !== null, 'oversize rejected');
assert_true(attachment_validate('evil.exe', 1000) !== null, 'disallowed extension rejected');
assert_true(attachment_validate('empty.pdf', 0) !== null, 'empty file rejected');

// Stored name is non-guessable and keeps a safe extension.
$s1 = attachment_stored_name('My File.PDF');
$s2 = attachment_stored_name('My File.PDF');
assert_true($s1 !== $s2, 'stored names are unique');
assert_true(str_ends_with($s1, '.pdf'), 'stored name preserves extension');
assert_false(str_contains($s1, ' '), 'stored name has no spaces/traversal');

$pdo = get_db();
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Att Admin','attadmin@x.io','x','admin',1)");
$admin = (int) $pdo->lastInsertId();
$cat = create_category($pdo, ['name'=>'ATT Cat','legal_basis'=>'contract','retention_period_days'=>10,'disposal_trigger'=>'date_based'], $admin);
$pdo->prepare("INSERT INTO data_records (category_id,record_reference,collection_date,status) VALUES (?,?,?,'active')")->execute([$cat,'ATT-1','2025-01-01']);
$rid = (int) $pdo->lastInsertId();

// store_attachment with an injected mover (no real upload).
$moved = null;
$id = store_attachment($pdo, $rid, ['name'=>'evidence.pdf','size'=>2048,'type'=>'application/pdf','tmp_name'=>'/tmp/x'], $admin,
    function($src, $dest) use (&$moved) { $moved = $dest; return true; });
assert_true($id > 0, 'attachment metadata stored');
$att = fetch_attachment($pdo, $id);
assert_equals('evidence.pdf', $att['original_filename'], 'original filename kept');
assert_true(str_contains($moved, $att['stored_filename']), 'file moved to its stored name');

assert_throws(fn() => store_attachment($pdo, $rid, ['name'=>'bad.exe','size'=>10,'type'=>'x','tmp_name'=>'/tmp/y'], $admin, fn($a,$b)=>true), 'disallowed type throws');
