<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/billing_lib.php';
require_once __DIR__ . '/../includes/stripe_lib.php';
require_login();
require_role('admin');

$pdo = get_db();
$reference = trim($_GET['reference'] ?? $_GET['trxref'] ?? '');
$provider  = trim($_GET['provider']  ?? '');

// Prefix-based auto-detect: Stripe references start with "adrs_st_".
if ($provider === '' && str_starts_with($reference, 'adrs_st_')) {
    $provider = 'stripe';
}

$ok = false;
if ($reference !== '') {
    if ($provider === 'stripe') {
        $sessionId = $_GET['stripe_session_id'] ?? null;
        $ok = stripe_verify_and_activate($pdo, $reference, is_string($sessionId) ? $sessionId : null);
    } else {
        $ok = paystack_verify_and_activate($pdo, $reference);
    }
}

if (!$ok) {
    flash('error', 'Payment could not be verified. Contact support if you were charged.');
    redirect(APP_URL . '/billing');
}

flash('success', 'Payment successful. Your ADRS subscription is now active.');
redirect(APP_URL . '/dashboard');
