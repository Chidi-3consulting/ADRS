<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';

function is_platform_admin(): bool {
    $u = current_user();
    return !empty($u['is_platform_admin']);
}

function require_platform_admin(): void {
    require_login();
    if (!is_platform_admin()) {
        http_response_code(403);
        exit('Platform administrator access required.');
    }
}

/** Platform-wide metrics for the super-admin dashboard. */
function platform_metrics(PDO $pdo): array {
    return [
        'organizations' => (int) $pdo->query("SELECT COUNT(*) FROM organizations")->fetchColumn(),
        'active_orgs'   => (int) $pdo->query("SELECT COUNT(*) FROM organizations WHERE status = 'active'")->fetchColumn(),
        'trial_orgs'    => (int) $pdo->query("SELECT COUNT(*) FROM organizations WHERE subscription_status = 'trial'")->fetchColumn(),
        'paid_orgs'     => (int) $pdo->query("SELECT COUNT(*) FROM organizations WHERE subscription_status = 'active'")->fetchColumn(),
        'users'         => (int) $pdo->query("SELECT COUNT(*) FROM users WHERE deleted_at IS NULL")->fetchColumn(),
        'records'       => (int) $pdo->query("SELECT COUNT(*) FROM data_records WHERE deleted_at IS NULL")->fetchColumn(),
        'revenue_tx'    => (int) $pdo->query("SELECT COUNT(*) FROM payment_transactions WHERE status = 'success'")->fetchColumn(),
    ];
}

/** List organisations with summary stats for the admin table. */
function platform_list_organizations(PDO $pdo): array {
    return $pdo->query(
        "SELECT o.*,
                (SELECT COUNT(*) FROM users u WHERE u.organization_id = o.id AND u.deleted_at IS NULL) AS user_count,
                (SELECT COUNT(*) FROM data_records r WHERE r.organization_id = o.id AND r.deleted_at IS NULL) AS record_count
         FROM organizations o ORDER BY o.created_at DESC"
    )->fetchAll();
}

function platform_set_org_status(PDO $pdo, int $orgId, string $status): void {
    if (!in_array($status, ['active', 'trial', 'suspended'], true)) { return; }
    $pdo->prepare('UPDATE organizations SET status = :s WHERE id = :id')->execute(['s' => $status, 'id' => $orgId]);
    log_audit($pdo, 'platform_org_status', 'organization', $orgId, (int) (current_user()['id'] ?? 0), ['status' => $status], get_client_ip());
}
