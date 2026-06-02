<?php
require_once __DIR__ . '/db.php';

function get_setting(PDO $pdo, string $key, $default = null)
{
    static $cache = [];

    if (array_key_exists($key, $cache)) {
        return $cache[$key];
    }

    $stmt = $pdo->prepare('SELECT `value` FROM system_settings WHERE `key` = :key LIMIT 1');
    $stmt->execute(['key' => $key]);
    $result = $stmt->fetch();

    if ($result === false) {
        return $cache[$key] = $default;
    }

    return $cache[$key] = $result['value'];
}

function escape_html(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function flash_set(string $type, string $message): void
{
    session_start();
    $_SESSION['flash_messages'][] = ['type' => $type, 'message' => $message];
}

function flash_get(): array
{
    session_start();
    $messages = $_SESSION['flash_messages'] ?? [];
    unset($_SESSION['flash_messages']);
    return $messages;
}

function csrf_token(): string
{
    session_start();
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

function validate_csrf(string $token): bool
{
    session_start();
    return hash_equals($_SESSION['csrf_token'] ?? '', $token);
}

function redirect(string $url): void
{
    header('Location: ' . $url);
    exit;
}

function send_json(array $data, int $statusCode = 200): void
{
    header('Content-Type: application/json; charset=utf-8');
    http_response_code($statusCode);
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

function attachment_storage_path(): string
{
    $folder = __DIR__ . '/../../storage/attachments';
    if (!is_dir($folder)) {
        mkdir($folder, 0755, true);
    }
    return $folder;
}

function attachment_allowed_extensions(): array
{
    return ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'];
}

function attachment_max_size_bytes(): int
{
    return 10 * 1024 * 1024;
}

function attachment_safe_filename(string $filename): string
{
    return preg_replace('/[^A-Za-z0-9._-]/', '_', basename($filename));
}
