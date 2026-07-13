<?php
require_once __DIR__ . '/db.php';

/** Platform-wide settings stored in system_settings (not per-tenant). */
const PLATFORM_SETTING_KEYS = [
    'deployment_mode', 'setup_complete', 'allow_public_signup',
    'paystack_public_key', 'paystack_secret_key', 'core_plan_amount_kobo', 'enterprise_plan_amount_kobo',
    'trial_days', 'platform_support_email',
];

/** Tenant settings exposed in the grouped Settings UI (never includes tier/API flags). */
const ORG_SETTING_SECTIONS = [
    'retention' => [
        'label' => 'Retention & compliance',
        'description' => 'Default deadlines and list behaviour for your organisation.',
        'keys' => [
            'review_alert_days'      => ['label' => 'Review alert (days before end)', 'type' => 'number'],
            'escalation_days'        => ['label' => 'Escalation window (days)', 'type' => 'number'],
            'consent_disposal_days'  => ['label' => 'Consent withdrawal disposal (days)', 'type' => 'number'],
            'attachment_max_size_mb' => ['label' => 'Max attachment size (MB)', 'type' => 'number'],
            'rows_per_page'          => ['label' => 'Rows per page', 'type' => 'number'],
        ],
    ],
    'email' => [
        'label' => 'Email delivery',
        'description' => 'SMTP settings for retention alerts and escalations.',
        'keys' => [
            'smtp_host'       => ['label' => 'SMTP host', 'type' => 'text'],
            'smtp_port'       => ['label' => 'SMTP port', 'type' => 'number'],
            'smtp_encryption' => ['label' => 'Encryption (ssl / tls)', 'type' => 'text'],
            'smtp_user'       => ['label' => 'SMTP username', 'type' => 'text'],
            'smtp_pass'       => ['label' => 'SMTP password', 'type' => 'password'],
            'smtp_from_name'  => ['label' => 'From name', 'type' => 'text'],
        ],
    ],
    'branding' => [
        'label' => 'Portal branding',
        'description' => 'How ADRS appears to your team (white-label options).',
        'keys' => [
            'white_label_name'    => ['label' => 'Portal display name', 'type' => 'text'],
            'white_label_primary' => ['label' => 'Primary colour (hex)', 'type' => 'text', 'placeholder' => '#C85C1A'],
            'white_label_logo_url'=> ['label' => 'Logo URL', 'type' => 'url'],
            'white_label_footer'  => ['label' => 'Footer text', 'type' => 'text'],
        ],
    ],
];

/** Flat allowlist of organisation setting keys editable via Settings forms. */
function org_editable_setting_keys(): array {
    $keys = [];
    foreach (ORG_SETTING_SECTIONS as $section) {
        foreach ($section['keys'] as $k => $_meta) {
            $keys[] = $k;
        }
    }
    return $keys;
}

/** Load current values for a settings section. */
function org_settings_for_section(PDO $pdo, int $orgId, string $sectionKey): array {
    $section = ORG_SETTING_SECTIONS[$sectionKey] ?? null;
    if ($section === null) { return []; }
    $out = [];
    foreach ($section['keys'] as $key => $meta) {
        $out[$key] = [
            'meta'  => $meta,
            'value' => (string) get_setting($pdo, $key, '', $orgId),
        ];
    }
    return $out;
}

/* ---------------- Date & retention (D4: fixed days) ---------------- */

/** Collection date + N days, as Y-m-d. */
function retention_end_date(string $collection_date, int $days): string {
    return date('Y-m-d', strtotime("+{$days} days", strtotime($collection_date)));
}

/** Whole days until $date (negative if past). */
function days_until(string $date): int {
    $today = new DateTimeImmutable('today');
    $target = new DateTimeImmutable($date);
    return (int) $today->diff($target)->format('%r%a');
}

/** Convert a number + unit (days/months/years) to whole days (30/mo, 365/yr). */
function calculate_retention_days(int $number, string $unit): int {
    return match ($unit) {
        'years'  => $number * 365,
        'months' => $number * 30,
        default  => $number,
    };
}

/** Human date; '—' for null/empty. */
function format_date(?string $date, string $format = 'd M Y'): string {
    if ($date === null || $date === '' || $date === '0000-00-00') { return '—'; }
    return date($format, strtotime($date));
}

/** Human datetime; '—' for null/empty. */
function format_datetime(?string $dt): string {
    if ($dt === null || $dt === '') { return '—'; }
    return date('d M Y H:i:s', strtotime($dt));
}

/* ---------------- Settings (system_settings: setting_key / setting_value) ---------------- */

/** Read a setting with in-request cache. Platform keys use system_settings; others use organization_settings. */
function get_setting(PDO $pdo, string $key, $default = null, ?int $orgId = null) {
    if (!isset($GLOBALS['__setting_cache'])) { $GLOBALS['__setting_cache'] = []; }
    $cache = &$GLOBALS['__setting_cache'];
    $orgId = $orgId ?? (function_exists('current_org_id') ? current_org_id() : null);
    if (!in_array($key, PLATFORM_SETTING_KEYS, true) && ($orgId === null || $orgId <= 0) && PHP_SAPI === 'cli') {
        $orgId = 1;
    }
    $cacheKey = (in_array($key, PLATFORM_SETTING_KEYS, true) ? 'p:' : 'o:' . ($orgId ?? 0) . ':') . $key;
    if (array_key_exists($cacheKey, $cache)) { return $cache[$cacheKey]; }

    if (in_array($key, PLATFORM_SETTING_KEYS, true)) {
        $stmt = $pdo->prepare('SELECT setting_value FROM system_settings WHERE setting_key = :k LIMIT 1');
        $stmt->execute(['k' => $key]);
        $row = $stmt->fetch();
        return $cache[$cacheKey] = ($row === false ? $default : $row['setting_value']);
    }

    if ($orgId === null || $orgId <= 0) { return $default; }
    $stmt = $pdo->prepare(
        'SELECT setting_value FROM organization_settings WHERE organization_id = :o AND setting_key = :k LIMIT 1'
    );
    $stmt->execute(['o' => $orgId, 'k' => $key]);
    $row = $stmt->fetch();
    if ($row !== false) { return $cache[$cacheKey] = $row['setting_value']; }

    // Legacy single-tenant fallback before organization_settings is populated.
    $stmt = $pdo->prepare('SELECT setting_value FROM system_settings WHERE setting_key = :k LIMIT 1');
    $stmt->execute(['k' => $key]);
    $row = $stmt->fetch();
    return $cache[$cacheKey] = ($row === false ? $default : $row['setting_value']);
}

/** Clear the in-request settings cache (after updating settings, or between test scenarios). */
function clear_setting_cache(): void { $GLOBALS['__setting_cache'] = []; }

function is_local_environment(): bool {
    return defined('APP_ENV') && APP_ENV === 'local';
}

/** True only if SMTP looks genuinely configured (non-empty host that isn't the seed placeholder). */
function smtp_is_configured(PDO $pdo): bool {
    $host = trim((string) get_setting($pdo, 'smtp_host', ''));
    return $host !== '' && stripos($host, 'yourdomain') === false;
}

/** Update (upsert) a platform or organisation setting and clear the cache. */
function set_setting(PDO $pdo, string $key, string $value, ?int $orgId = null): void {
    if (in_array($key, PLATFORM_SETTING_KEYS, true)) {
        $pdo->prepare(
            "INSERT INTO system_settings (setting_key, setting_value) VALUES (:k,:v)
             ON DUPLICATE KEY UPDATE setting_value = :v2"
        )->execute(['k' => $key, 'v' => $value, 'v2' => $value]);
    } else {
        $orgId = $orgId ?? (function_exists('current_org_id') ? current_org_id() : null);
        if ($orgId === null || $orgId <= 0) {
            if (PHP_SAPI === 'cli') {
                $orgId = 1;
            } else {
                $orgId = require_org_id();
            }
        }
        $pdo->prepare(
            "INSERT INTO organization_settings (organization_id, setting_key, setting_value) VALUES (:o,:k,:v)
             ON DUPLICATE KEY UPDATE setting_value = :v2"
        )->execute(['o' => $orgId, 'k' => $key, 'v' => $value, 'v2' => $value]);
    }
    clear_setting_cache();
}

/* ---------------- Output / input ---------------- */

/** Trim + htmlspecialchars (UTF-8, quotes). */
function sanitize(mixed $input): string {
    return htmlspecialchars(trim((string) $input), ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

/** Alias used in views for already-typed strings. */
function escape_html(string $value): string {
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

/** Header redirect + exit. */
function redirect(string $url): never {
    header('Location: ' . $url);
    exit;
}

/**
 * Emit security response headers (call before any output). Defends against clickjacking,
 * MIME sniffing, referrer leakage, and constrains resource origins via CSP. The single CDN
 * (jsDelivr) is allow-listed; 'unsafe-inline' is permitted because the UI uses inline
 * styles/handlers (a future nonce-based refactor could remove it).
 */
function send_security_headers(): void {
    if (headers_sent()) { return; }
    header('X-Frame-Options: DENY');
    header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: strict-origin-when-cross-origin');
    header('Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=(), usb=()');
    header('Cross-Origin-Opener-Policy: same-origin');
    header('X-Permitted-Cross-Domain-Policies: none');
    if (defined('APP_ENV') && APP_ENV === 'production') {
        header('Strict-Transport-Security: max-age=31536000; includeSubDomains');
    }
    $nonce = csp_nonce();
    // script-src is nonce-based (no 'unsafe-inline'): inline scripts must carry the nonce,
    // and there are NO inline on* handlers (moved to app.js). style-src keeps 'unsafe-inline'
    // because inline style attributes are pervasive and low-risk.
    header(
        "Content-Security-Policy: default-src 'self'; "
        . "script-src 'self' 'nonce-$nonce' https://cdn.jsdelivr.net; "
        . "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        . "img-src 'self' data:; font-src 'self' https://cdn.jsdelivr.net; "
        . "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    );
}

/** Per-request CSP nonce for inline <script> tags. Generated once per request. */
function csp_nonce(): string {
    if (empty($GLOBALS['__csp_nonce'])) { $GLOBALS['__csp_nonce'] = base64_encode(random_bytes(16)); }
    return $GLOBALS['__csp_nonce'];
}

/** Returns an error message if a password fails the policy (min 10 chars, letters + numbers), else null. */
function password_policy_error(string $password): ?string {
    if (strlen($password) < 10) { return 'Password must be at least 10 characters long.'; }
    if (!preg_match('/[A-Za-z]/', $password) || !preg_match('/\d/', $password)) {
        return 'Password must include both letters and numbers.';
    }
    return null;
}

/** Best-effort real client IP. */
function get_client_ip(): string {
    foreach (['HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'] as $k) {
        if (!empty($_SERVER[$k])) {
            $ip = trim(explode(',', $_SERVER[$k])[0]);
            if (filter_var($ip, FILTER_VALIDATE_IP)) { return $ip; }
        }
    }
    return '0.0.0.0';
}

/* ---------------- CSRF ---------------- */

function _session(): void {
    if (PHP_SAPI === 'cli') { $_SESSION = $_SESSION ?? []; return; }
    if (session_status() === PHP_SESSION_NONE) { session_start(); }
}

/** Current CSRF token (64 hex chars), created on first use. */
function csrf_token(): string {
    _session();
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(CSRF_TOKEN_LENGTH));
    }
    return $_SESSION['csrf_token'];
}

/** Hidden input HTML for forms. */
function csrf_field(): string {
    return '<input type="hidden" name="csrf_token" value="' . escape_html(csrf_token()) . '">';
}

/** Verify POSTed token; 403 + exit on mismatch. */
function csrf_verify(): void {
    _session();
    $posted = $_POST['csrf_token'] ?? '';
    if (!hash_equals($_SESSION['csrf_token'] ?? '', $posted)) {
        http_response_code(403);
        exit('Invalid CSRF token.');
    }
}

/* ---------------- Flash messages ---------------- */

function flash(string $type, string $message): void {
    _session();
    $_SESSION['flash'][] = ['type' => $type, 'message' => $message];
}

function get_flash(): array {
    _session();
    $f = $_SESSION['flash'] ?? [];
    unset($_SESSION['flash']);
    return $f;
}

/** Bootstrap alert HTML for all pending flashes. */
function render_flash(): string {
    $map = ['success' => 'success', 'error' => 'danger', 'danger' => 'danger', 'info' => 'info', 'warning' => 'warning'];
    $html = '';
    foreach (get_flash() as $f) {
        $cls = $map[$f['type']] ?? 'info';
        $html .= '<div class="alert alert-' . $cls . ' alert-dismissible fade show" role="alert">'
              . escape_html($f['message'])
              . '<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>';
    }
    return $html;
}

/* ---------------- Audit logging (append-only; never breaks main flow) ---------------- */

/** Recursively key-sort an array (in place) so JSON is order-invariant. */
function _audit_rksort(&$a): void { if (is_array($a)) { ksort($a); foreach ($a as &$v) { _audit_rksort($v); } } }

/**
 * Normalise a details JSON string to a storage-invariant canonical form: MySQL's JSON
 * column may reorder object keys, so we decode + recursively key-sort + re-encode in both
 * the writer and verifier to keep the hash stable across the DB round-trip.
 */
function audit_norm_details(?string $json): string {
    if ($json === null || $json === '') { return ''; }
    $v = json_decode($json, true);
    if ($v === null) { return (string) $json; }
    _audit_rksort($v);
    return json_encode($v, JSON_UNESCAPED_UNICODE);
}

/** Canonical string hashed for an audit row (must match in writer and verifier). */
function audit_canonical(string $prev_hash, string $action, string $entity_type, ?int $entity_id, ?int $performed_by, ?string $details_json, ?string $ip, string $created_at): string {
    return implode('|', [$prev_hash, $action, $entity_type, (string) $entity_id, (string) $performed_by, audit_norm_details($details_json), (string) $ip, $created_at]);
}

/**
 * Insert an audit_log row, extending the tamper-evident hash chain (Phase 3).
 * Each row stores prev_hash (previous row's row_hash) and row_hash (SHA-256 over its
 * canonical content + prev_hash), set atomically at INSERT so the table stays append-only.
 * Silently swallows any error so logging never breaks a request.
 */
function log_audit(PDO $pdo, string $action, string $entity_type, ?int $entity_id, ?int $performed_by, ?array $details, ?string $ip): void {
    try {
        $detailsJson = $details === null ? null : json_encode($details, JSON_UNESCAPED_UNICODE);
        $createdAt = date('Y-m-d H:i:s');
        $orgId = function_exists('current_org_id') ? (current_org_id() ?? 1) : 1;
        $prevStmt = $pdo->prepare('SELECT row_hash FROM audit_log WHERE organization_id = :o ORDER BY id DESC LIMIT 1');
        $prevStmt->execute(['o' => $orgId]);
        $prev = $prevStmt->fetchColumn();
        $prevHash = ($prev !== false && $prev !== null) ? $prev : str_repeat('0', 64);
        $rowHash = hash('sha256', audit_canonical($prevHash, $action, $entity_type, $entity_id, $performed_by, $detailsJson, $ip, $createdAt));
        $stmt = $pdo->prepare(
            'INSERT INTO audit_log (organization_id, action, entity_type, entity_id, performed_by, details, ip_address, created_at, prev_hash, row_hash)
             VALUES (:oid, :a, :et, :eid, :pb, :d, :ip, :ca, :ph, :rh)'
        );
        $stmt->execute([
            'oid' => $orgId,
            'a'   => $action,
            'et'  => $entity_type,
            'eid' => $entity_id,
            'pb'  => $performed_by,
            'd'   => $detailsJson,
            'ip'  => $ip,
            'ca'  => $createdAt,
            'ph'  => $prevHash,
            'rh'  => $rowHash,
        ]);
    } catch (Throwable $e) {
        if (defined('LOG_PATH')) {
            if (!is_dir(LOG_PATH)) { @mkdir(LOG_PATH, 0755, true); }
            @file_put_contents(LOG_PATH . 'audit_error.log', '[' . date('c') . '] ' . $e->getMessage() . PHP_EOL, FILE_APPEND);
        }
    }
}

/**
 * Verify the audit-log hash chain. Walks rows in id order, recomputing each row_hash and
 * checking prev_hash links to the prior row. Returns
 * ['ok'=>bool, 'checked'=>int, 'broken_at'=>?int(id)].
 */
function verify_audit_chain(PDO $pdo, ?int $orgId = null): array {
    $orgId = $orgId ?? (function_exists('current_org_id') ? current_org_id() : null);
    if ($orgId !== null && $orgId > 0) {
        $stmt = $pdo->prepare(
            "SELECT id, action, entity_type, entity_id, performed_by, details, ip_address, created_at, prev_hash, row_hash
             FROM audit_log WHERE organization_id = :o ORDER BY id ASC"
        );
        $stmt->execute(['o' => $orgId]);
        $rows = $stmt->fetchAll();
    } else {
        $rows = $pdo->query(
            "SELECT id, action, entity_type, entity_id, performed_by, details, ip_address, created_at, prev_hash, row_hash
             FROM audit_log ORDER BY id ASC"
        )->fetchAll();
    }
    $expectedPrev = str_repeat('0', 64);
    $checked = 0;
    foreach ($rows as $r) {
        if ((string) $r['prev_hash'] !== $expectedPrev) {
            return ['ok' => false, 'checked' => $checked, 'broken_at' => (int) $r['id']];
        }
        $eid = $r['entity_id'] !== null ? (int) $r['entity_id'] : null;
        $pb  = $r['performed_by'] !== null ? (int) $r['performed_by'] : null;
        $calc = hash('sha256', audit_canonical((string) $r['prev_hash'], $r['action'], $r['entity_type'], $eid, $pb, $r['details'], $r['ip_address'], $r['created_at']));
        if (!hash_equals((string) $r['row_hash'], $calc)) {
            return ['ok' => false, 'checked' => $checked, 'broken_at' => (int) $r['id']];
        }
        $expectedPrev = $r['row_hash'];
        $checked++;
    }
    return ['ok' => true, 'checked' => $checked, 'broken_at' => null];
}

/* ---------------- Pagination ---------------- */

/** Compute pagination state. Returns total/per_page/pages/current/offset/has_prev/has_next. */
function paginate(int $total, int $per_page, int $current_page): array {
    $per_page = max(1, $per_page);
    $pages = max(1, (int) ceil($total / $per_page));
    $current = min(max(1, $current_page), $pages);
    return [
        'total' => $total, 'per_page' => $per_page, 'pages' => $pages, 'current' => $current,
        'offset' => ($current - 1) * $per_page, 'has_prev' => $current > 1, 'has_next' => $current < $pages,
    ];
}

/** Bootstrap pagination nav HTML. $base is the path; $params are preserved query args (page is replaced). */
function pagination_links(array $pg, string $base, array $params = []): string {
    if ($pg['pages'] <= 1) { return ''; }
    $url = function (int $p) use ($base, $params) {
        $params['page'] = $p;
        return escape_html($base . '?' . http_build_query($params));
    };
    $html = '<nav><ul class="pagination pagination-sm mb-0">';
    $html .= '<li class="page-item' . ($pg['has_prev'] ? '' : ' disabled') . '"><a class="page-link" href="' . $url(max(1, $pg['current'] - 1)) . '">Prev</a></li>';
    $start = max(1, $pg['current'] - 2); $end = min($pg['pages'], $pg['current'] + 2);
    for ($i = $start; $i <= $end; $i++) {
        $html .= '<li class="page-item' . ($i === $pg['current'] ? ' active' : '') . '"><a class="page-link" href="' . $url($i) . '">' . $i . '</a></li>';
    }
    $html .= '<li class="page-item' . ($pg['has_next'] ? '' : ' disabled') . '"><a class="page-link" href="' . $url(min($pg['pages'], $pg['current'] + 1)) . '">Next</a></li>';
    return $html . '</ul></nav>';
}

/* ---------------- UI label/badge helpers ---------------- */

function get_legal_basis_label(string $v): string {
    return [
        'legal_obligation' => 'Legal Obligation', 'contract' => 'Contract', 'consent' => 'Consent',
        'legitimate_interest' => 'Legitimate Interest', 'vital_interest' => 'Vital Interest', 'public_task' => 'Public Task',
    ][$v] ?? ucfirst(str_replace('_', ' ', $v));
}

function get_disposal_method_label(string $v): string {
    return ['delete' => 'Secure Delete', 'anonymise' => 'Anonymise', 'archive' => 'Archive'][$v] ?? ucfirst($v);
}

function get_status_badge(string $status): string {
    $map = [
        'active' => 'success', 'due_review' => 'warning', 'disposal_requested' => 'info',
        'legal_hold' => 'dark', 'disposed' => 'secondary',
    ];
    $cls = $map[$status] ?? 'secondary';
    return '<span class="badge bg-' . $cls . '">' . escape_html(ucwords(str_replace('_', ' ', $status))) . '</span>';
}

function get_role_badge(string $role): string {
    $label = ['admin' => 'Administrator', 'dpo' => 'DPO', 'data_owner' => 'Data Owner'][$role] ?? $role;
    return '<span class="badge bg-secondary">' . escape_html($label) . '</span>';
}

function get_framework_badge(string $f): string {
    $parts = array_filter(array_map('trim', explode(',', $f)));
    $html = '';
    foreach ($parts as $p) {
        $cls = ['GDPR' => 'badge-gdpr', 'NDPR' => 'badge-ndpr', 'BOTH' => 'badge-both', 'CCPA' => 'bg-info text-dark', 'LGPD' => 'bg-success', 'POPIA' => 'bg-dark', 'DPA_KE' => 'bg-primary', 'UK_GDPR' => 'bg-primary', 'DPA_GH' => 'bg-success', 'PDPA_SG' => 'bg-info text-dark'][$p] ?? 'bg-secondary';
        $html .= '<span class="badge ' . $cls . ' me-1">' . escape_html($p) . '</span>';
    }
    return $html ?: '<span class="badge bg-secondary">—</span>';
}

function list_regulations(PDO $pdo): array {
    return $pdo->query("SELECT * FROM regulations WHERE is_active = 1 ORDER BY name")->fetchAll(PDO::FETCH_ASSOC);
}

function get_regulation_name(PDO $pdo, string $code): string {
    $stmt = $pdo->prepare("SELECT name FROM regulations WHERE code = :c LIMIT 1");
    $stmt->execute(['c' => $code]);
    $name = $stmt->fetchColumn();
    return $name ?: $code;
}

/* ---------------- Notification bell (N2) ---------------- */

function get_unread_notification_count(PDO $pdo, int $user_id): int {
    $stmt = $pdo->prepare("SELECT COUNT(*) c FROM notifications WHERE recipient_id = :u AND read_at IS NULL AND status = 'sent'");
    $stmt->execute(['u' => $user_id]);
    return (int) $stmt->fetch()['c'];
}

function get_unread_notifications(PDO $pdo, int $user_id, int $limit = 10): array {
    $stmt = $pdo->prepare("SELECT * FROM notifications WHERE recipient_id = :u AND read_at IS NULL ORDER BY created_at DESC LIMIT :lim");
    $stmt->bindValue('u', $user_id, PDO::PARAM_INT);
    $stmt->bindValue('lim', $limit, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll();
}
