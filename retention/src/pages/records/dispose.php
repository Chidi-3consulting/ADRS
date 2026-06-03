<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/lifecycle_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { redirect(APP_URL . '/records'); }
csrf_verify();
$id = (int) ($_POST['record_id'] ?? 0);
try {
    $r = request_disposal($pdo, $id, (int) current_user()['id']);
    flash('success', $r === 'disposed' ? 'Record disposed.' : 'Disposal requested — a second authorised user must approve (dual approval required).');
} catch (Throwable $e) { flash('error', $e->getMessage()); }
redirect(APP_URL . '/records/view?id=' . $id);
