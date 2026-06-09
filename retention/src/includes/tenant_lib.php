<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';

/** True when this deployment accepts public organisation registration (SaaS). */
function is_saas_deployment(PDO $pdo): bool {
    return get_setting($pdo, 'deployment_mode', 'saas') === 'saas';
}

/** Active organisation id for the current HTTP request, CLI cron step, or explicit override. */
function current_org_id(): ?int {
    if (isset($GLOBALS['__cron_org_id'])) { return (int) $GLOBALS['__cron_org_id']; }
    $u = current_user();
    if (!empty($u['organization_id'])) { return (int) $u['organization_id']; }
    return null;
}

function require_org_id(): int {
    $id = current_org_id();
    if ($id === null || $id <= 0) {
        http_response_code(403);
        exit('Organisation context required.');
    }
    return $id;
}

/** URL-safe slug; appends -2, -3… on collision. */
function generate_org_slug(PDO $pdo, string $name): string {
    $base = strtolower(trim(preg_replace('/[^a-z0-9]+/i', '-', $name), '-'));
    if ($base === '') { $base = 'organisation'; }
    $slug = $base;
    $n = 2;
    $stmt = $pdo->prepare('SELECT 1 FROM organizations WHERE slug = :s LIMIT 1');
    while (true) {
        $stmt->execute(['s' => $slug]);
        if (!$stmt->fetch()) { return $slug; }
        $slug = $base . '-' . $n++;
    }
}

/** Default per-organisation settings copied on registration. */
function default_org_settings(string $tier): array {
    return [
        'adrs_tier'              => $tier,
        'enterprise_api_enabled' => $tier === 'enterprise' ? '1' : '0',
        'review_alert_days'      => '30',
        'escalation_days'        => '14',
        'consent_disposal_days'  => '30',
        'dsar_response_days'     => '30',
        'attachment_max_size_mb' => '10',
        'rows_per_page'          => '25',
        'timezone'               => 'Africa/Lagos',
        'white_label_name'       => '',
        'white_label_primary'    => '#C85C1A',
        'white_label_logo_url'   => '',
        'white_label_footer'     => '3Consulting Limited',
        'smtp_host'              => '',
        'smtp_port'              => '465',
        'smtp_user'              => '',
        'smtp_pass'              => '',
        'smtp_from_name'         => 'ADRS Data Retention',
        'smtp_encryption'        => 'ssl',
    ];
}

function provision_org_settings(PDO $pdo, int $orgId, string $orgName, string $tier): void {
    $settings = default_org_settings($tier);
    $settings['white_label_name'] = $orgName;
    $settings['app_name'] = $orgName;
    $ins = $pdo->prepare(
        'INSERT INTO organization_settings (organization_id, setting_key, setting_value)
         VALUES (:oid, :k, :v) ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)'
    );
    foreach ($settings as $k => $v) {
        $ins->execute(['oid' => $orgId, 'k' => $k, 'v' => $v]);
    }
}

/** Clone master category templates (organization_id = 0) into a new tenant. */
function provision_org_categories(PDO $pdo, int $orgId): int {
    $stmt = $pdo->prepare('SELECT COUNT(*) FROM data_categories WHERE organization_id = :o AND deleted_at IS NULL');
    $stmt->execute(['o' => $orgId]);
    if ((int) $stmt->fetchColumn() > 0) { return 0; }

    import_master_category_templates($pdo);

    $pdo->prepare(
        "INSERT INTO data_categories
           (organization_id, name, description, compliance_framework, legal_basis, retention_period_days,
            retention_period_label, disposal_method, disposal_trigger, requires_dual_approval,
            review_frequency, source, is_active)
         SELECT :oid, name, description, compliance_framework, legal_basis, retention_period_days,
            retention_period_label, disposal_method, disposal_trigger, requires_dual_approval,
            review_frequency, source, is_active
         FROM data_categories WHERE organization_id = 0 AND deleted_at IS NULL"
    )->execute(['oid' => $orgId]);

    $stmt->execute(['o' => $orgId]);
    return (int) $stmt->fetchColumn();
}

/** Load the 30-category library as organisation_id = 0 master templates (once per deployment). */
function import_master_category_templates(PDO $pdo): void {
    if ((int) $pdo->query('SELECT COUNT(*) FROM data_categories WHERE organization_id = 0')->fetchColumn() > 0) {
        return;
    }
    $org1 = (int) $pdo->query("SELECT COUNT(*) FROM data_categories WHERE organization_id = 1 AND source = 'seeded'")->fetchColumn();
    if ($org1 > 0) {
        $pdo->exec(
            "INSERT INTO data_categories
               (organization_id, name, description, compliance_framework, legal_basis, retention_period_days,
                retention_period_label, disposal_method, disposal_trigger, requires_dual_approval,
                review_frequency, source, is_active)
             SELECT 0, name, description, compliance_framework, legal_basis, retention_period_days,
                retention_period_label, disposal_method, disposal_trigger, requires_dual_approval,
                review_frequency, source, is_active
             FROM data_categories WHERE organization_id = 1 AND source = 'seeded'"
        );
        return;
    }
    require_once __DIR__ . '/public_layout.php';
    import_category_seed($pdo, 0);
}

/**
 * Register a new organisation + first admin (SaaS self-service).
 * Returns ['organization_id' => int, 'user_id' => int] or throws on validation failure.
 */
function register_organization(PDO $pdo, string $orgName, string $adminName, string $email, string $password, string $tier = 'core'): array {
    $tier = $tier === 'enterprise' ? 'enterprise' : 'core';
    if ($orgName === '' || $adminName === '' || $email === '') {
        throw new InvalidArgumentException('Organisation name, your name, and email are required.');
    }
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        throw new InvalidArgumentException('A valid email address is required.');
    }
    if (($pwErr = password_policy_error($password)) !== null) {
        throw new InvalidArgumentException($pwErr);
    }
    $exists = $pdo->prepare('SELECT 1 FROM users WHERE email = :e LIMIT 1');
    $exists->execute(['e' => $email]);
    if ($exists->fetch()) {
        throw new InvalidArgumentException('An account with that email already exists. Sign in or reset your password.');
    }

    $pdo->beginTransaction();
    try {
        $slug = generate_org_slug($pdo, $orgName);
        $trialDays = max(1, (int) get_setting($pdo, 'trial_days', '14'));
        $pdo->prepare(
            "INSERT INTO organizations (name, slug, tier, status, subscription_status, trial_ends_at, billing_email)
             VALUES (:n, :s, :t, 'trial', 'trial', DATE_ADD(NOW(), INTERVAL :days DAY), :email)"
        )->execute(['n' => $orgName, 's' => $slug, 't' => $tier, 'days' => $trialDays, 'email' => $email]);
        $orgId = (int) $pdo->lastInsertId();

        $pdo->prepare(
            "INSERT INTO users (organization_id, name, email, password_hash, role, is_active, must_change_password)
             VALUES (:oid, :n, :e, :p, 'admin', 1, 0)"
        )->execute([
            'oid' => $orgId,
            'n'   => $adminName,
            'e'   => $email,
            'p'   => password_hash($password, PASSWORD_BCRYPT),
        ]);
        $userId = (int) $pdo->lastInsertId();

        provision_org_settings($pdo, $orgId, $orgName, $tier);
        provision_org_categories($pdo, $orgId);

        $pdo->commit();
        return ['organization_id' => $orgId, 'user_id' => $userId];
    } catch (Throwable $e) {
        $pdo->rollBack();
        throw $e;
    }
}

/** All active organisations (for cron iteration). */
function list_active_organizations(PDO $pdo): array {
    return $pdo->query("SELECT * FROM organizations WHERE status IN ('active','trial') ORDER BY id")->fetchAll();
}

/** Users in the current organisation (for dropdowns). Optional SQL fragment, e.g. "role IN ('admin','dpo')". */
function list_org_users(PDO $pdo, string $extraWhere = ''): array {
    $orgId = require_org_id();
    $sql = 'SELECT id, name, email, role FROM users WHERE organization_id = :org AND is_active = 1 AND deleted_at IS NULL';
    if ($extraWhere !== '') { $sql .= ' AND ' . $extraWhere; }
    $sql .= ' ORDER BY name';
    $stmt = $pdo->prepare($sql);
    $stmt->execute(['org' => $orgId]);
    return $stmt->fetchAll();
}

/** Category options for the current organisation. */
function list_org_categories(PDO $pdo, bool $activeOnly = true): array {
    $orgId = require_org_id();
    $sql = 'SELECT id, name, compliance_framework FROM data_categories WHERE organization_id = :org AND deleted_at IS NULL';
    if ($activeOnly) { $sql .= ' AND is_active = 1'; }
    $sql .= ' ORDER BY name';
    $stmt = $pdo->prepare($sql);
    $stmt->execute(['org' => $orgId]);
    return $stmt->fetchAll();
}

/** Connected systems for the current organisation. */
function list_org_systems(PDO $pdo, bool $activeOnly = false): array {
    $orgId = require_org_id();
    $sql = 'SELECT id, name FROM connected_systems WHERE organization_id = :org';
    if ($activeOnly) { $sql .= ' AND is_active = 1'; }
    $sql .= ' ORDER BY name';
    $stmt = $pdo->prepare($sql);
    $stmt->execute(['org' => $orgId]);
    return $stmt->fetchAll();
}

/** Verify a row belongs to the current tenant (prevents cross-org IDOR). */
function assert_org_row(?array $row): void {
    if ($row === null) {
        http_response_code(404);
        exit('Not found.');
    }
    $orgId = current_org_id();
    if ($orgId !== null && isset($row['organization_id']) && (int) $row['organization_id'] !== $orgId) {
        http_response_code(403);
        exit('Forbidden.');
    }
}
