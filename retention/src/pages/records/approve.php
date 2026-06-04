<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/lifecycle_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { redirect(APP_URL . '/records'); }
csrf_verify();
$id = (int) ($_POST['record_id'] ?? 0);
$decision = $_POST['decision'] ?? 'approve';
try {
    if ($decision === 'reject') {
        reject_disposal($pdo, $id, (int) current_user()['id'], trim($_POST['reason'] ?? ''));
        flash('success', 'Disposal request rejected; record returned to review.');
    } else {
        approve_disposal($pdo, $id, (int) current_user()['id']);
        flash('success', 'Disposal approved and executed.');
    }
} catch (Throwable $e) { flash('error', $e->getMessage()); }
redirect(APP_URL . '/records/view?id=' . $id);
