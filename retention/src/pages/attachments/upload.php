<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/attachments_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { redirect(APP_URL . '/records'); }
csrf_verify();

$recordId = (int) ($_POST['record_id'] ?? 0);
$file = $_FILES['file'] ?? null;
try {
    if (!$file || ($file['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK) {
        throw new InvalidArgumentException('Please choose a file to upload.');
    }
    store_attachment($pdo, $recordId, $file, (int) current_user()['id']);
    flash('success', 'Attachment uploaded.');
} catch (Throwable $e) {
    flash('error', $e->getMessage());
}
redirect(APP_URL . '/records/view?id=' . $recordId);
