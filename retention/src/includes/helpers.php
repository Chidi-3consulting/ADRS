<?php
require_once __DIR__ . '/db.php';

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

/** Read a system setting with in-request cache. Returns $default if absent. */
function get_setting(PDO $pdo, string $key, $default = null) {
    if (!isset($GLOBALS['__setting_cache'])) { $GLOBALS['__setting_cache'] = []; }
    $cache = &$GLOBALS['__setting_cache'];
    if (array_key_exists($key, $cache)) { return $cache[$key]; }
    $stmt = $pdo->prepare('SELECT setting_value FROM system_settings WHERE setting_key = :k LIMIT 1');
    $stmt->execute(['k' => $key]);
    $row = $stmt->fetch();
    return $cache[$key] = ($row === false ? $default : $row['setting_value']);
}

/** Clear the in-request settings cache (after updating settings, or between test scenarios). */
function clear_setting_cache(): void { $GLOBALS['__setting_cache'] = []; }

/** Update (upsert) a system setting and clear the cache. */
function set_setting(PDO $pdo, string $key, string $value): void {
    $pdo->prepare(
        "INSERT INTO system_settings (setting_key, setting_value) VALUES (:k,:v)
         ON DUPLICATE KEY UPDATE setting_value = :v2"
    )->execute(['k' => $key, 'v' => $value, 'v2' => $value]);
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

/** Insert an audit_log row. Silently swallows any error so logging never breaks a request. */
function log_audit(PDO $pdo, string $action, string $entity_type, ?int $entity_id, ?int $performed_by, ?array $details, ?string $ip): void {
    try {
        $stmt = $pdo->prepare(
            'INSERT INTO audit_log (action, entity_type, entity_id, performed_by, details, ip_address)
             VALUES (:a, :et, :eid, :pb, :d, :ip)'
        );
        $stmt->execute([
            'a'   => $action,
            'et'  => $entity_type,
            'eid' => $entity_id,
            'pb'  => $performed_by,
            'd'   => $details === null ? null : json_encode($details, JSON_UNESCAPED_UNICODE),
            'ip'  => $ip,
        ]);
    } catch (Throwable $e) {
        if (defined('LOG_PATH')) {
            if (!is_dir(LOG_PATH)) { @mkdir(LOG_PATH, 0755, true); }
            @file_put_contents(LOG_PATH . 'audit_error.log', '[' . date('c') . '] ' . $e->getMessage() . PHP_EOL, FILE_APPEND);
        }
    }
}

/* ---------------- DSAR (C1) ---------------- */

/** Next DSAR reference: DSAR-{year}-{4-digit sequence within that year}. */
function generate_dsar_reference(PDO $pdo): string {
    $year = date('Y');
    $stmt = $pdo->prepare("SELECT COUNT(*) c FROM dsar_requests WHERE YEAR(created_at) = :y");
    $stmt->execute(['y' => $year]);
    $seq = ((int) $stmt->fetch()['c']) + 1;
    return sprintf('DSAR-%s-%04d', $year, $seq);
}

/** DSAR statutory due date: received + 30 days. */
function calculate_dsar_due_date(string $received_date): string {
    return date('Y-m-d', strtotime('+30 days', strtotime($received_date)));
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
    $cls = ['GDPR' => 'badge-gdpr', 'NDPR' => 'badge-ndpr', 'BOTH' => 'badge-both'][$f] ?? 'bg-secondary';
    return '<span class="badge ' . $cls . '">' . escape_html($f) . '</span>';
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
