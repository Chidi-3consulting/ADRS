<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/categories_lib.php';
require_role('admin');
$pdo = get_db();

if ($_SERVER['REQUEST_METHOD'] !== 'POST') { redirect(APP_URL . '/categories'); }
csrf_verify();
$id = (int) ($_POST['id'] ?? 0);

if ($id > 0 && soft_delete_category($pdo, $id, (int) current_user()['id'])) {
    flash('success', 'Category deleted.');
} else {
    flash('error', 'Category could not be deleted — it still has active records.');
}
redirect(APP_URL . '/categories');
