<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_login();
$pdo = get_db();
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $pdo->prepare("UPDATE notifications SET read_at = NOW() WHERE recipient_id = :u AND read_at IS NULL")
        ->execute(['u' => (int) current_user()['id']]);
    flash('success', 'All notifications marked read.');
}
redirect(APP_URL . '/notifications');
