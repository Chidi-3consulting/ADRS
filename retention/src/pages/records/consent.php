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
    $end = log_consent_withdrawal($pdo, $id, (int) current_user()['id']);
    flash('success', 'Consent withdrawal logged. Disposal scheduled for ' . format_date($end) . '.');
} catch (Throwable $e) { flash('error', $e->getMessage()); }
redirect(APP_URL . '/records/view?id=' . $id);
