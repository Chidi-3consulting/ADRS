<?php
/** Paystack webhook — verify charge.success and activate subscriptions. */
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/db.php';
require_once __DIR__ . '/../../includes/billing_lib.php';

$payload = file_get_contents('php://input');
$sig = $_SERVER['HTTP_X_PAYSTACK_SIGNATURE'] ?? '';
$pdo = get_db();
$secret = trim((string) get_setting($pdo, 'paystack_secret_key', ''));

if ($secret === '' || !hash_equals(hash_hmac('sha512', $payload, $secret), $sig)) {
    http_response_code(401);
    exit('Invalid signature');
}

$data = json_decode($payload, true);
if (($data['event'] ?? '') === 'charge.success' && !empty($data['data']['reference'])) {
    paystack_verify_and_activate($pdo, $data['data']['reference']);
}
http_response_code(200);
echo json_encode(['ok' => true]);
