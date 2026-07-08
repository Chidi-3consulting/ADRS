<?php
if (!require_db('tenant registration')) { return; }

require_once __DIR__ . '/../../src/includes/billing_lib.php';
$pdo = get_db();
if (!is_saas_deployment($pdo)) {
    set_setting($pdo, 'deployment_mode', 'saas');
    clear_setting_cache();
}

$domain = 'tenant-test-' . bin2hex(random_bytes(4)) . '.example';
$email = 'admin@' . $domain;

try {
    $result = register_organization($pdo, 'Test Org Ltd', $domain, 'Test Admin', $email, 'SecurePass1', 'core');
    assert_true($result['organization_id'] > 0, 'org created');
    assert_true($result['user_id'] > 0, 'admin user created');

    $org = fetch_organization($pdo, (int) $result['organization_id']);
    assert_equals($domain, $org['primary_domain'], 'primary_domain stored');
    assert_equals('trial', $org['subscription_status'], 'starts on trial');

    $dupOk = false;
    try {
        register_organization($pdo, 'Another Org', $domain, 'Other Admin', 'other@' . $domain, 'SecurePass2', 'core');
    } catch (InvalidArgumentException $e) {
        $dupOk = str_contains($e->getMessage(), 'already registered');
    }
    assert_true($dupOk, 'duplicate domain rejected');

    $mismatchOk = false;
    $domain2 = 'tenant-test-' . bin2hex(random_bytes(4)) . '.example';
    try {
        register_organization($pdo, 'Mismatch Org', $domain2, 'Bad Admin', 'wrong@gmail.com', 'SecurePass3', 'core');
    } catch (InvalidArgumentException $e) {
        $mismatchOk = str_contains($e->getMessage(), 'work email');
    }
    assert_true($mismatchOk, 'email domain mismatch rejected');
} finally {
    if (isset($result['organization_id'])) {
        $oid = (int) $result['organization_id'];
        $pdo->prepare('DELETE FROM users WHERE organization_id = :o')->execute(['o' => $oid]);
        $pdo->prepare('DELETE FROM organization_settings WHERE organization_id = :o')->execute(['o' => $oid]);
        $pdo->prepare('DELETE FROM data_categories WHERE organization_id = :o')->execute(['o' => $oid]);
        $pdo->prepare('DELETE FROM organizations WHERE id = :o')->execute(['o' => $oid]);
    }
}
