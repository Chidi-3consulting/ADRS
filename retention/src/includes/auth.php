<?php
require_once __DIR__ . '/helpers.php';

function _auth_session(): void {
    // Under CLI (tests) there is no HTTP session; $_SESSION still works as a plain array.
    if (PHP_SAPI === 'cli') { $_SESSION = $_SESSION ?? []; return; }
    if (session_status() === PHP_SESSION_NONE) { session_start(); }
}

function is_logged_in(): bool { _auth_session(); return !empty($_SESSION['user']); }

function current_user(): array { _auth_session(); return $_SESSION['user'] ?? []; }

function has_role(string ...$roles): bool {
    $u = current_user();
    return isset($u['role']) && in_array($u['role'], $roles, true);
}

function require_login(): void {
    if (!is_logged_in()) { redirect(APP_URL . '/login'); }
}

function require_role(string ...$roles): void {
    require_login();
    if (!has_role(...$roles)) {
        http_response_code(403);
        exit('Forbidden — you do not have access to this page.');
    }
}

/**
 * Verify credentials and start an authenticated session.
 * Returns false (never revealing which field was wrong) on any failure.
 */
/** Validate email+password only (no session). Returns the full user row (incl. 2FA fields) or null. */
function verify_credentials(PDO $pdo, string $email, string $password): ?array {
    $stmt = $pdo->prepare("SELECT * FROM users WHERE email = :e AND is_active = 1 AND deleted_at IS NULL LIMIT 1");
    $stmt->execute(['e' => $email]);
    $user = $stmt->fetch();
    if (!$user || !password_verify($password, $user['password_hash'])) { return null; }
    return $user;
}

/** Start an authenticated session for a verified user (secrets stripped before storing). */
function establish_session(PDO $pdo, array $user): void {
    _auth_session();
    if (PHP_SAPI !== 'cli' && session_status() === PHP_SESSION_ACTIVE) { session_regenerate_id(true); }
    unset($user['password_hash'], $user['twofa_secret'], $user['twofa_recovery']);
    $_SESSION['user'] = $user;
    $pdo->prepare("UPDATE users SET last_login_at = NOW() WHERE id = :id")->execute(['id' => $user['id']]);
    log_audit($pdo, 'user_login', 'user', (int) $user['id'], (int) $user['id'], null, get_client_ip());
}

/** Convenience: verify + establish session in one step (used by non-2FA callers and tests). */
function login_user(PDO $pdo, string $email, string $password): bool {
    $user = verify_credentials($pdo, $email, $password);
    if (!$user) { return false; }
    establish_session($pdo, $user);
    return true;
}

/** Enable TOTP 2FA for a user (stores secret + hashed recovery codes). */
function enable_user_2fa(PDO $pdo, int $user_id, string $secret, array $hashed_recovery): void {
    $pdo->prepare("UPDATE users SET twofa_enabled = 1, twofa_secret = :s, twofa_recovery = :r WHERE id = :id")
        ->execute(['s' => $secret, 'r' => json_encode($hashed_recovery), 'id' => $user_id]);
}

/** Disable 2FA for a user. */
function disable_user_2fa(PDO $pdo, int $user_id): void {
    $pdo->prepare("UPDATE users SET twofa_enabled = 0, twofa_secret = NULL, twofa_recovery = NULL WHERE id = :id")->execute(['id' => $user_id]);
}

function logout_user(PDO $pdo): never {
    if (is_logged_in()) {
        $u = current_user();
        log_audit($pdo, 'user_logout', 'user', (int) $u['id'], (int) $u['id'], null, get_client_ip());
    }
    _auth_session();
    session_unset();
    session_destroy();
    redirect(APP_URL . '/login');
}

/* ---------------- Password reset tokens (1-hour expiry, SHA-256 hashed) ---------------- */

function create_password_reset_token(PDO $pdo, string $email): ?string {
    $stmt = $pdo->prepare("SELECT id FROM users WHERE email = :e AND is_active = 1 AND deleted_at IS NULL LIMIT 1");
    $stmt->execute(['e' => $email]);
    if (!$stmt->fetch()) { return null; }

    $raw  = bin2hex(random_bytes(32)); // 64 hex chars
    $hash = hash('sha256', $raw);
    $pdo->prepare("INSERT INTO password_resets (email, token_hash, expires_at) VALUES (:e, :h, DATE_ADD(NOW(), INTERVAL 1 HOUR))")
        ->execute(['e' => $email, 'h' => $hash]);
    log_audit($pdo, 'password_reset_requested', 'user', null, null, ['email' => $email], get_client_ip());
    return $raw;
}

function validate_reset_token(PDO $pdo, string $email, string $token): bool {
    $hash = hash('sha256', $token);
    $stmt = $pdo->prepare(
        "SELECT id FROM password_resets
         WHERE email = :e AND token_hash = :h AND used = 0 AND expires_at > NOW()
         ORDER BY id DESC LIMIT 1"
    );
    $stmt->execute(['e' => $email, 'h' => $hash]);
    return (bool) $stmt->fetch();
}

function consume_reset_token(PDO $pdo, string $email): void {
    $pdo->prepare("UPDATE password_resets SET used = 1 WHERE email = :e AND used = 0")->execute(['e' => $email]);
}

/* ---------------- Login brute-force throttling ---------------- */

/** Record a login attempt (success/failure). Never throws — throttling must not break login. */
function record_login_attempt(PDO $pdo, string $email, string $ip, bool $success): void {
    try {
        $pdo->prepare("INSERT INTO login_attempts (email, ip_address, success) VALUES (:e,:i,:s)")
            ->execute(['e' => $email !== '' ? $email : null, 'i' => $ip, 's' => $success ? 1 : 0]);
    } catch (Throwable $e) { /* ignore */ }
}

/**
 * Seconds the caller must wait before retrying, or 0 if not throttled. Locks after 5 failed
 * attempts for the same email OR IP within a 15-minute rolling window (slows credential
 * stuffing and password guessing without persistently locking real users out).
 */
function login_throttle_seconds(PDO $pdo, string $email, string $ip): int {
    $max = 5; $windowMin = 15;
    try {
        $stmt = $pdo->prepare(
            "SELECT COUNT(*) c, MIN(created_at) first_at FROM login_attempts
             WHERE success = 0 AND created_at >= DATE_SUB(NOW(), INTERVAL :w MINUTE)
               AND (email = :e OR ip_address = :i)"
        );
        $stmt->execute(['w' => $windowMin, 'e' => $email, 'i' => $ip]);
        $row = $stmt->fetch();
        if ((int) $row['c'] < $max) { return 0; }
        return max(1, (strtotime($row['first_at']) + $windowMin * 60) - time());
    } catch (Throwable $e) { return 0; }
}
