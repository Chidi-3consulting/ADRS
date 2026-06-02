<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/records_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();

if ($_SERVER['REQUEST_METHOD'] !== 'POST') { redirect(APP_URL . '/records'); }
csrf_verify();
$recordId = (int) ($_POST['record_id'] ?? 0);
$newCat = (int) ($_POST['new_category_id'] ?? 0);
$recalc = isset($_POST['recalculate']);

try {
    reassign_category($pdo, $recordId, $newCat, (int) current_user()['id'], $recalc);
    flash('success', 'Record reassigned' . ($recalc ? ' and retention date recalculated.' : '.'));
} catch (Throwable $e) {
    flash('error', $e->getMessage());
}
redirect(APP_URL . '/records/view?id=' . $recordId);
