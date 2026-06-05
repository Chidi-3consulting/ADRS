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
        $prev = $pdo->query("SELECT row_hash FROM audit_log ORDER BY id DESC LIMIT 1")->fetchColumn();
        $prevHash = ($prev !== false && $prev !== null) ? $prev : str_repeat('0', 64);
        $rowHash = hash('sha256', audit_canonical($prevHash, $action, $entity_type, $entity_id, $performed_by, $detailsJson, $ip, $createdAt));
        $stmt = $pdo->prepare(
            'INSERT INTO audit_log (action, entity_type, entity_id, performed_by, details, ip_address, created_at, prev_hash, row_hash)
             VALUES (:a, :et, :eid, :pb, :d, :ip, :ca, :ph, :rh)'
        );
        $stmt->execute([
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
function verify_audit_chain(PDO $pdo): array {
    $rows = $pdo->query(
        "SELECT id, action, entity_type, entity_id, performed_by, details, ip_address, created_at, prev_hash, row_hash
         FROM audit_log ORDER BY id ASC"
    )->fetchAll();
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
