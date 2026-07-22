<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/country_regulation_map.php';

/** True when this deployment accepts public organisation registration (SaaS). */
function is_saas_deployment(PDO $pdo): bool {
    return true;
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
    if ($id !== null && $id > 0) { return $id; }
    if (PHP_SAPI === 'cli') { return 1; }
    http_response_code(403);
    exit('Organisation context required.');
}

/** Personal email providers that cannot be used as an organisation domain. */
const BLOCKED_ORG_DOMAINS = [
    'gmail.com', 'googlemail.com', 'yahoo.com', 'yahoo.co.uk', 'hotmail.com', 'outlook.com',
    'live.com', 'icloud.com', 'me.com', 'proton.me', 'protonmail.com', 'aol.com', 'mail.com',
    'yandex.com', 'gmx.com', 'zoho.com', 'fastmail.com',
];

/** Normalise user input to a bare domain (e.g. acmebank.com). Returns '' on failure. */
function normalize_org_domain(string $input): string {
    $d = strtolower(trim($input));
    if ($d === '') { return ''; }
    if (str_contains($d, '://')) {
        $parsed = parse_url($d, PHP_URL_HOST);
        $d = strtolower((string) ($parsed ?: ''));
    }
    $d = preg_replace('#^www\.#', '', $d);
    $d = preg_replace('#/.*$#', '', $d);
    $d = rtrim($d, '.');
    if ($d === '' || !preg_match('/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/', $d)) {
        return '';
    }
    return $d;
}

/** Extract the domain part of an email address (lowercase). */
function email_domain(string $email): string {
    $email = strtolower(trim($email));
    $at = strrpos($email, '@');
    return $at === false ? '' : substr($email, $at + 1);
}

/** True when email belongs to the organisation's registered domain. */
function email_matches_org_domain(string $email, string $primaryDomain): bool {
    return email_domain($email) === strtolower($primaryDomain);
}

/** Validate a normalised domain for tenant registration; returns error message or null. */
function org_domain_policy_error(string $domain): ?string {
    if ($domain === '') {
        return 'Enter a valid company domain (e.g. acmebank.com — not a full URL or www prefix).';
    }
    if (in_array($domain, BLOCKED_ORG_DOMAINS, true)) {
        return 'Use your company domain, not a personal email provider (e.g. gmail.com).';
    }
    return null;
}

/** Load the active organisation for the current session. */
function fetch_current_organization(PDO $pdo): ?array {
    $orgId = current_org_id();
    if ($orgId === null || $orgId <= 0) { return null; }
    require_once __DIR__ . '/billing_lib.php';
    return fetch_organization($pdo, $orgId);
}

/** Human-readable tier label for UI. */
function org_tier_label(string $tier): string {
    return $tier === 'enterprise' ? 'Enterprise' : 'Core';
}

/** Subscription status badge HTML for the current org. */
function org_status_badge(array $org): string {
    $status = $org['subscription_status'] ?? $org['status'] ?? '';
    $map = ['active' => 'success', 'trial' => 'info', 'past_due' => 'warning', 'cancelled' => 'secondary', 'suspended' => 'danger'];
    $cls = $map[$status] ?? 'secondary';
    return '<span class="badge bg-' . $cls . '">' . escape_html(ucfirst(str_replace('_', ' ', (string) $status))) . '</span>';
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

/** Enforce team member emails use the organisation's registered domain (SaaS). Returns error or null. */
function org_member_email_error(PDO $pdo, string $email, ?int $orgId = null): ?string {
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        return 'A valid email address is required.';
    }
    $orgId = $orgId ?? require_org_id();
    require_once __DIR__ . '/billing_lib.php';
    $org = fetch_organization($pdo, $orgId);
    if (!$org || empty($org['primary_domain'])) { return null; }
    $domain = strtolower((string) $org['primary_domain']);
    if ($domain === 'default.local' || str_ends_with($domain, '.local')) { return null; }
    if (!email_matches_org_domain($email, $domain)) {
        return 'Team members must use a work email at @' . $domain . '.';
    }
    return null;
}
function default_org_settings(string $tier, ?string $country = null): array {
    $tzMap = [
        'NG' => 'Africa/Lagos', 'GB' => 'Europe/London', 'US' => 'America/New_York',
        'BR' => 'America/Sao_Paulo', 'ZA' => 'Africa/Johannesburg', 'KE' => 'Africa/Nairobi',
        'GH' => 'Africa/Accra', 'SG' => 'Asia/Singapore', 'EU' => 'Europe/Berlin',
        'IN' => 'Asia/Kolkata', 'AE' => 'Asia/Dubai', 'CA' => 'America/Toronto',
        'AU' => 'Australia/Sydney', 'EG' => 'Africa/Cairo',
    ];
    $tz = $tzMap[$country ?? ''] ?? 'Africa/Lagos';

    return [
        'adrs_tier'              => $tier,
        'enterprise_api_enabled' => $tier === 'enterprise' ? '1' : '0',
        'review_alert_days'      => '30',
        'escalation_days'        => '14',
        'consent_disposal_days'  => '30',
        'attachment_max_size_mb' => '10',
        'rows_per_page'          => '25',
        'timezone'               => $tz,
        'white_label_name'       => '',
        'white_label_primary'    => '#ff914d',
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

function provision_org_settings(PDO $pdo, int $orgId, string $orgName, string $tier, ?string $country = null): void {
    $settings = default_org_settings($tier, $country);
    $settings['white_label_name'] = $orgName;
    $settings['app_name'] = $orgName;
    if ($country) { $settings['org_country'] = $country; }
    $ins = $pdo->prepare(
        'INSERT INTO organization_settings (organization_id, setting_key, setting_value)
         VALUES (:oid, :k, :v) ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)'
    );
    foreach ($settings as $k => $v) {
        $ins->execute(['oid' => $orgId, 'k' => $k, 'v' => $v]);
    }
}

/** Clone master category templates (organization_id = 0) into a new tenant, filtered by country. */
function provision_org_categories(PDO $pdo, int $orgId, ?string $country = null): int {
    $stmt = $pdo->prepare('SELECT COUNT(*) FROM data_categories WHERE organization_id = :o AND deleted_at IS NULL');
    $stmt->execute(['o' => $orgId]);
    if ((int) $stmt->fetchColumn() > 0) { return 0; }

    import_master_category_templates($pdo);

    // Determine which compliance frameworks apply to this country
    $allowedFrameworks = get_country_regulations($country ?? 'OTHER');

    // Build a WHERE clause to filter by framework
    $placeholders = [];
    $params = ['oid' => $orgId];
    foreach ($allowedFrameworks as $i => $fw) {
        $key = 'fw' . $i;
        $placeholders[] = ':' . $key;
        $params[$key] = $fw;
    }
    $fwWhere = 'compliance_framework IN (' . implode(',', $placeholders) . ')';

    $templates = $pdo->query('SELECT id, name FROM data_categories WHERE organization_id = 0 AND deleted_at IS NULL')->fetchAll();

    $pdo->prepare(
        "INSERT INTO data_categories
           (organization_id, name, description, compliance_framework, legal_basis, retention_period_days,
            retention_period_label, disposal_method, disposal_trigger, requires_dual_approval,
            review_frequency, source, is_active)
         SELECT :oid, name, description, compliance_framework, legal_basis, retention_period_days,
            retention_period_label, disposal_method, disposal_trigger, requires_dual_approval,
            review_frequency, source, is_active
         FROM data_categories WHERE organization_id = 0 AND deleted_at IS NULL AND {$fwWhere}"
    )->execute($params);

    require_once __DIR__ . '/retention_rules_lib.php';
    $newCats = $pdo->prepare('SELECT id, name FROM data_categories WHERE organization_id = :o AND deleted_at IS NULL');
    $newCats->execute(['o' => $orgId]);
    $byName = [];
    foreach ($newCats->fetchAll() as $nc) { $byName[$nc['name']] = (int) $nc['id']; }
    foreach ($templates as $tpl) {
        if (!isset($byName[$tpl['name']])) { continue; }
        $existing = $pdo->prepare('SELECT COUNT(*) FROM category_retention_rules WHERE category_id = :c');
        $existing->execute(['c' => $byName[$tpl['name']]]);
        if ((int) $existing->fetchColumn() === 0) {
            clone_category_retention_rules($pdo, (int) $tpl['id'], $byName[$tpl['name']], $orgId);
        }
    }

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
 * One organisation per company domain — admin email must match primary_domain.
 * Returns ['organization_id' => int, 'user_id' => int] or throws on validation failure.
 */
function register_organization(PDO $pdo, string $orgName, string $primaryDomainInput, string $adminName, string $email, string $password, string $tier = 'core', ?string $country = null): array {
    $tier = 'enterprise';
    $email = strtolower(trim($email));
    $primaryDomain = normalize_org_domain($primaryDomainInput);

    if ($orgName === '' || $adminName === '' || $email === '') {
        throw new InvalidArgumentException('Organisation name, your name, and email are required.');
    }
    if (($domErr = org_domain_policy_error($primaryDomain)) !== null) {
        throw new InvalidArgumentException($domErr);
    }
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        throw new InvalidArgumentException('A valid work email address is required.');
    }
    if (!email_matches_org_domain($email, $primaryDomain)) {
        throw new InvalidArgumentException('Your work email must use @' . $primaryDomain . ' — the same domain you registered for your organisation.');
    }
    if (($pwErr = password_policy_error($password)) !== null) {
        throw new InvalidArgumentException($pwErr);
    }

    $exists = $pdo->prepare('SELECT 1 FROM users WHERE email = :e LIMIT 1');
    $exists->execute(['e' => $email]);
    if ($exists->fetch()) {
        throw new InvalidArgumentException('An account with that email already exists. Sign in or reset your password.');
    }

    $domainTaken = $pdo->prepare('SELECT name FROM organizations WHERE primary_domain = :d LIMIT 1');
    $domainTaken->execute(['d' => $primaryDomain]);
    if ($existing = $domainTaken->fetch()) {
        throw new InvalidArgumentException(
            'An organisation is already registered for ' . $primaryDomain . '. '
            . 'Each company may have only one ADRS account — sign in or contact your administrator.'
        );
    }

    $pdo->beginTransaction();
    try {
        $slug = generate_org_slug($pdo, $orgName);
        $trialDays = max(1, (int) get_setting($pdo, 'trial_days', '14'));
        $pdo->prepare(
            "INSERT INTO organizations (name, slug, primary_domain, country, tier, status, subscription_status, trial_ends_at, billing_email)
             VALUES (:n, :s, :d, :country, :t, 'trial', 'trial', DATE_ADD(NOW(), INTERVAL :days DAY), :email)"
        )->execute(['n' => $orgName, 's' => $slug, 'd' => $primaryDomain, 'country' => $country, 't' => $tier, 'days' => $trialDays, 'email' => $email]);
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

        provision_org_settings($pdo, $orgId, $orgName, $tier, $country);
        provision_org_categories($pdo, $orgId, $country);

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
