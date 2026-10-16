<?php
/**
 * Stripe integration for ADRS/SafeData.
 *
 * Runs alongside paystack_lib: Paystack handles NGN direct, Stripe handles USD
 * (and lets Stripe convert at checkout for non-NGN visitors who want to pay in
 * their own currency). No Composer — raw cURL only. PHP 8.2.
 *
 * Settings keys read: stripe_publishable_key, stripe_secret_key,
 *                     stripe_webhook_secret,
 *                     core_plan_amount_usd_cents, enterprise_plan_amount_usd_cents.
 */
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/tenant_lib.php';

/** USD plan catalog for the Stripe button. Amounts are in US cents. */
function stripe_plan_catalog(PDO $pdo): array {
    return [
        'core' => [
            'name'   => 'ADRS Core',
            'amount' => (int) get_setting($pdo, 'core_plan_amount_usd_cents', '5000'),
            'label'  => 'Standalone compliance portal',
        ],
        'enterprise' => [
            'name'   => 'ADRS Enterprise',
            'amount' => (int) get_setting($pdo, 'enterprise_plan_amount_usd_cents', '16000'),
            'label'  => 'Core + API integration & automatic data capture',
        ],
    ];
}

function format_usd_cents(int $cents): string {
    return '$' . number_format($cents / 100, 2);
}

/**
 * Start a Stripe Checkout Session. Returns ['authorization_url'=>..., 'reference'=>...].
 * Throws on misconfiguration or API failure (mirrors paystack_initialize).
 */
function stripe_initialize(PDO $pdo, int $orgId, string $tier, string $email): array {
    $secret = trim((string) get_setting($pdo, 'stripe_secret_key', ''));
    if ($secret === '') {
        throw new RuntimeException('Stripe is not configured. Contact support to complete payment.');
    }
    $plans = stripe_plan_catalog($pdo);
    if (!isset($plans[$tier])) { throw new InvalidArgumentException('Invalid plan.'); }
    $amount = $plans[$tier]['amount'];                  // USD cents
    $reference = 'adrs_st_' . $orgId . '_' . bin2hex(random_bytes(8));

    // Record the pending transaction (currency column exists on payment_transactions).
    $pdo->prepare(
        'INSERT INTO payment_transactions (organization_id, reference, amount_kobo, currency, plan_tier, status, provider)
         VALUES (:o, :r, :a, :c, :t, :s, :p)'
    )->execute([
        'o' => $orgId, 'r' => $reference, 'a' => $amount, 'c' => 'USD',
        't' => $tier, 's' => 'pending', 'p' => 'stripe',
    ]);

    // Stripe Checkout Session (POST form-encoded, nested payload uses bracket syntax).
    $success = APP_URL . '/billing/callback?provider=stripe&reference=' . rawurlencode($reference)
             . '&stripe_session_id={CHECKOUT_SESSION_ID}';
    $cancel  = APP_URL . '/billing?stripe_cancelled=1';

    $fields = [
        'mode'                                                => 'payment',
        'success_url'                                         => $success,
        'cancel_url'                                          => $cancel,
        'customer_email'                                      => $email,
        'client_reference_id'                                 => $reference,
        'line_items[0][price_data][currency]'                 => 'usd',
        'line_items[0][price_data][product_data][name]'       => $plans[$tier]['name'] . ' — annual',
        'line_items[0][price_data][unit_amount]'              => (string) $amount,
        'line_items[0][quantity]'                             => '1',
        'metadata[organization_id]'                           => (string) $orgId,
        'metadata[plan_tier]'                                 => $tier,
        'metadata[reference]'                                 => $reference,
        // Give the customer the choice of their local currency at Checkout:
        'payment_method_types[0]'                             => 'card',
    ];

    $ch = curl_init('https://api.stripe.com/v1/checkout/sessions');
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => http_build_query($fields),
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER     => [
            'Authorization: Bearer ' . $secret,
            'Content-Type: application/x-www-form-urlencoded',
        ],
    ]);
    $resp = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    $data = json_decode((string) $resp, true);
    if ($code !== 200 || empty($data['url'])) {
        throw new RuntimeException('Stripe error. Please try again.');
    }

    // Persist the Stripe session id for later verification.
    $pdo->prepare(
        'UPDATE payment_transactions SET provider_data = :d WHERE reference = :r'
    )->execute([
        'd' => json_encode(['stripe_session_id' => $data['id'] ?? null]),
        'r' => $reference,
    ]);

    return [
        'authorization_url' => $data['url'],
        'reference'         => $reference,
    ];
}

/**
 * Verify a Stripe Checkout Session by reference and activate the subscription.
 * Returns true on success, false otherwise. Mirrors paystack_verify_and_activate.
 */
function stripe_verify_and_activate(PDO $pdo, string $reference, ?string $sessionIdHint = null): bool {
    $secret = trim((string) get_setting($pdo, 'stripe_secret_key', ''));
    if ($secret === '') { return false; }

    $stmt = $pdo->prepare('SELECT * FROM payment_transactions WHERE reference = :r LIMIT 1');
    $stmt->execute(['r' => $reference]);
    $tx = $stmt->fetch();
    if (!$tx) { return false; }
    if ($tx['status'] === 'success') { return true; }
    if (($tx['provider'] ?? 'paystack') !== 'stripe') { return false; }

    $sessionId = $sessionIdHint;
    if (!$sessionId) {
        $meta = json_decode((string) ($tx['provider_data'] ?? '{}'), true);
        $sessionId = $meta['stripe_session_id'] ?? null;
    }
    if (!$sessionId) { return false; }

    $ch = curl_init('https://api.stripe.com/v1/checkout/sessions/' . rawurlencode($sessionId));
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER     => ['Authorization: Bearer ' . $secret],
    ]);
    $resp = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    $data = json_decode((string) $resp, true);
    $paid = $code === 200
         && ($data['payment_status'] ?? '') === 'paid'
         && ($data['client_reference_id'] ?? '') === $reference;

    if (!$paid) {
        $pdo->prepare("UPDATE payment_transactions SET status='failed', provider_data = :d WHERE id = :id")
            ->execute(['d' => json_encode($data ?: ['error' => 'verify failed']), 'id' => $tx['id']]);
        return false;
    }

    $orgId = (int) $tx['organization_id'];
    $tier  = $tx['plan_tier'];

    $pdo->prepare(
        "UPDATE payment_transactions
            SET status='success', completed_at = NOW(), provider_data = :d
          WHERE id = :id"
    )->execute(['d' => json_encode($data), 'id' => $tx['id']]);

    $pdo->prepare(
        "UPDATE organizations
            SET subscription_status='active', tier = :t, status='active',
                last_payment_at = NOW(),
                billing_email = COALESCE(:e, billing_email)
          WHERE id = :o"
    )->execute([
        't' => $tier,
        'e' => $data['customer_details']['email'] ?? ($data['customer_email'] ?? null),
        'o' => $orgId,
    ]);

    set_setting($pdo, 'adrs_tier', $tier, $orgId);
    if ($tier === 'enterprise') {
        set_setting($pdo, 'enterprise_api_enabled', '1', $orgId);
    }
    return true;
}
