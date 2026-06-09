<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/tenant_lib.php';

/** Plan prices and labels for the billing UI. */
function billing_plan_catalog(PDO $pdo): array {
    return [
        'core' => [
            'name'   => 'ADRS Core',
            'amount' => (int) get_setting($pdo, 'core_plan_amount_kobo', '7500000'),
            'label'  => 'Standalone compliance portal',
        ],
        'enterprise' => [
            'name'   => 'ADRS Enterprise',
            'amount' => (int) get_setting($pdo, 'enterprise_plan_amount_kobo', '25000000'),
            'label'  => 'Core + API integration & automatic data capture',
        ],
    ];
}

function format_ngn_kobo(int $kobo): string {
    return '₦' . number_format($kobo / 100, 2);
}

/** Fetch organisation billing row or null. */
function fetch_organization(PDO $pdo, int $orgId): ?array {
    $stmt = $pdo->prepare('SELECT * FROM organizations WHERE id = :id LIMIT 1');
    $stmt->execute(['id' => $orgId]);
    $row = $stmt->fetch();
    return $row === false ? null : $row;
}

/** True when the org may use the app (trial active or paid subscription). */
function organization_has_access(PDO $pdo, int $orgId): bool {
    $org = fetch_organization($pdo, $orgId);
    if (!$org || $org['status'] === 'suspended') { return false; }
    if ($org['subscription_status'] === 'active') { return true; }
    if ($org['subscription_status'] === 'trial' && $org['trial_ends_at'] !== null) {
        return strtotime($org['trial_ends_at']) >= time();
    }
    return $org['subscription_status'] === 'trial' && $org['trial_ends_at'] === null;
}

function organization_trial_days_left(PDO $pdo, int $orgId): ?int {
    $org = fetch_organization($pdo, $orgId);
    if (!$org || $org['subscription_status'] !== 'trial' || empty($org['trial_ends_at'])) { return null; }
    return max(0, (int) ceil((strtotime($org['trial_ends_at']) - time()) / 86400));
}

/** Redeem an Enterprise licence key for an organisation. */
function redeem_enterprise_licence(PDO $pdo, string $rawKey, int $orgId): bool {
    $hash = hash('sha256', trim($rawKey));
    $stmt = $pdo->prepare(
        'SELECT id FROM enterprise_licence_keys
         WHERE key_hash = :h AND redeemed_by_organization_id IS NULL LIMIT 1'
    );
    $stmt->execute(['h' => $hash]);
    $row = $stmt->fetch();
    if (!$row) { return false; }

    $pdo->prepare(
        'UPDATE enterprise_licence_keys SET redeemed_by_organization_id = :o, redeemed_at = NOW() WHERE id = :id'
    )->execute(['o' => $orgId, 'id' => $row['id']]);

    $pdo->prepare(
        "UPDATE organizations SET tier = 'enterprise', enterprise_licence_key = :k WHERE id = :o"
    )->execute(['k' => substr(trim($rawKey), 0, 64), 'o' => $orgId]);

    set_setting($pdo, 'adrs_tier', 'enterprise', $orgId);
    set_setting($pdo, 'enterprise_api_enabled', '1', $orgId);
    return true;
}

/** Validate licence without redeeming (for UI feedback). */
function enterprise_licence_is_valid(PDO $pdo, string $rawKey): bool {
    $hash = hash('sha256', trim($rawKey));
    $stmt = $pdo->prepare(
        'SELECT 1 FROM enterprise_licence_keys WHERE key_hash = :h AND redeemed_by_organization_id IS NULL LIMIT 1'
    );
    $stmt->execute(['h' => $hash]);
    return (bool) $stmt->fetch();
}

/** Start a Paystack transaction; returns ['authorization_url'=>..., 'reference'=>...] or throws. */
function paystack_initialize(PDO $pdo, int $orgId, string $tier, string $email): array {
    $secret = trim((string) get_setting($pdo, 'paystack_secret_key', ''));
    if ($secret === '') {
        throw new RuntimeException('Paystack is not configured. Contact support to complete payment.');
    }
    $plans = billing_plan_catalog($pdo);
    if (!isset($plans[$tier])) { throw new InvalidArgumentException('Invalid plan.'); }
    $amount = $plans[$tier]['amount'];
    $reference = 'adrs_' . $orgId . '_' . bin2hex(random_bytes(8));

    $pdo->prepare(
        'INSERT INTO payment_transactions (organization_id, reference, amount_kobo, plan_tier, status)
         VALUES (:o,:r,:a,:t,:s)'
    )->execute(['o' => $orgId, 'r' => $reference, 'a' => $amount, 't' => $tier, 's' => 'pending']);

    $payload = json_encode([
        'email'     => $email,
        'amount'    => $amount,
        'reference' => $reference,
        'currency'  => 'NGN',
        'metadata'  => ['organization_id' => $orgId, 'plan_tier' => $tier],
        'callback_url' => APP_URL . '/billing/callback',
    ]);

    $ch = curl_init('https://api.paystack.co/transaction/initialize');
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $payload,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER     => [
            'Authorization: Bearer ' . $secret,
            'Content-Type: application/json',
        ],
    ]);
    $resp = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    $data = json_decode((string) $resp, true);
    if ($code !== 200 || empty($data['status']) || empty($data['data']['authorization_url'])) {
        throw new RuntimeException('Payment provider error. Please try again.');
    }
    return [
        'authorization_url' => $data['data']['authorization_url'],
        'reference'       => $reference,
    ];
}

/** Verify a Paystack reference and activate subscription on success. */
function paystack_verify_and_activate(PDO $pdo, string $reference): bool {
    $secret = trim((string) get_setting($pdo, 'paystack_secret_key', ''));
    if ($secret === '') { return false; }

    $stmt = $pdo->prepare('SELECT * FROM payment_transactions WHERE reference = :r LIMIT 1');
    $stmt->execute(['r' => $reference]);
    $tx = $stmt->fetch();
    if (!$tx || $tx['status'] === 'success') { return $tx && $tx['status'] === 'success'; }

    $ch = curl_init('https://api.paystack.co/transaction/verify/' . rawurlencode($reference));
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER     => ['Authorization: Bearer ' . $secret],
    ]);
    $resp = curl_exec($ch);
    curl_close($ch);
    $data = json_decode((string) $resp, true);
    if (empty($data['status']) || ($data['data']['status'] ?? '') !== 'success') {
        $pdo->prepare("UPDATE payment_transactions SET status = 'failed' WHERE id = :id")->execute(['id' => $tx['id']]);
        return false;
    }

    $orgId = (int) $tx['organization_id'];
    $tier  = $tx['plan_tier'];
    $pdo->prepare(
        "UPDATE payment_transactions SET status = 'success', completed_at = NOW(), provider_data = :d WHERE id = :id"
    )->execute(['d' => json_encode($data['data']), 'id' => $tx['id']]);

    $pdo->prepare(
        "UPDATE organizations SET subscription_status = 'active', tier = :t, status = 'active',
                last_payment_at = NOW(), billing_email = :e WHERE id = :o"
    )->execute(['t' => $tier, 'e' => $data['data']['customer']['email'] ?? null, 'o' => $orgId]);

    set_setting($pdo, 'adrs_tier', $tier, $orgId);
    if ($tier === 'enterprise') {
        set_setting($pdo, 'enterprise_api_enabled', '1', $orgId);
    }
    return true;
}
