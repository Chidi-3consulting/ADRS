<?php
require_once __DIR__ . '/helpers.php';

function session_start_if_needed(): void
{
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }
}

function current_user(): ?array
{
    session_start_if_needed();
    return $_SESSION['user'] ?? null;
}

function require_login(): void
{
    session_start_if_needed();

    if (empty($_SESSION['user'])) {
        redirect('/retention/login');
    }
}

function require_role(array $allowedRoles): void
{
    $user = current_user();
    if ($user === null || !in_array($user['role'], $allowedRoles, true)) {
        http_response_code(403);
        echo 'Forbidden';
        exit;
    }
}

function login_user(PDO $pdo, string $email, string $password): bool
{
    $stmt = $pdo->prepare('SELECT * FROM users WHERE email = :email AND is_active = 1 LIMIT 1');
    $stmt->execute(['email' => $email]);
    $user = $stmt->fetch();

    if (!$user || !password_verify($password, $user['password_hash'])) {
        return false;
    }

    session_start_if_needed();
    unset($user['password_hash']);
    $_SESSION['user'] = $user;

    $stmt = $pdo->prepare('UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = :id');
    $stmt->execute(['id' => $user['id']]);

    return true;
}

function logout_user(): void
{
    session_start_if_needed();
    session_unset();
    session_destroy();
}
