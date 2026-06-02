<?php
require_once __DIR__ . '/helpers.php';

function _auth_session(): void { if (session_status() === PHP_SESSION_NONE) { session_start(); } }

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
function login_user(PDO $pdo, string $email, string $password): bool {
    $stmt = $pdo->prepare("SELECT * FROM users WHERE email = :e AND is_active = 1 AND deleted_at IS NULL LIMIT 1");
    $stmt->execute(['e' => $email]);
    $user = $stmt->fetch();
    if (!$user || !password_verify($password, $user['password_hash'])) {
        return false;
    }
    _auth_session();
    session_regenerate_id(true);
    unset($user['password_hash']);
    $_SESSION['user'] = $user;
    $pdo->prepare("UPDATE users SET last_login_at = NOW() WHERE id = :id")->execute(['id' => $user['id']]);
    log_audit($pdo, 'user_login', 'user', (int) $user['id'], (int) $user['id'], null, get_client_ip());
    return true;
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
