<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/billing_lib.php';
require_login();
require_role('admin');

$pdo = get_db();
$reference = trim($_GET['reference'] ?? $_GET['trxref'] ?? '');
if ($reference === '' || !paystack_verify_and_activate($pdo, $reference)) {
    flash('error', 'Payment could not be verified. Contact support if you were charged.');
    redirect(APP_URL . '/billing');
}
flash('success', 'Payment successful. Your ADRS subscription is now active.');
redirect(APP_URL . '/dashboard');
