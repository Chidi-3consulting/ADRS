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
    if (($_POST['action'] ?? '') === 'lift') {
        lift_legal_hold($pdo, $id, (int) current_user()['id']);
        flash('success', 'Legal hold lifted.');
    } else {
        set_legal_hold($pdo, $id, trim($_POST['reason'] ?? ''), (int) current_user()['id']);
        flash('success', 'Legal hold applied — disposal is suspended.');
    }
} catch (Throwable $e) { flash('error', $e->getMessage()); }
redirect(APP_URL . '/records/view?id=' . $id);
