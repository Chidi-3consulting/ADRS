<?php
require_once __DIR__ . '/../../../../src/includes/db.php';
require_once __DIR__ . '/../../../../src/includes/helpers.php';

function api_raw_key(): ?string
{
    $header = $_SERVER['HTTP_X_API_KEY'] ?? '';
    return $header !== '' ? trim($header) : null;
}

function get_api_request_body(): array
{
    $raw = file_get_contents('php://input');
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : ['raw_payload' => $raw];
}

function require_api_key(PDO $pdo): array
{
    $rawKey = api_raw_key();
    if ($rawKey === null) {
        send_json(['error' => 'Missing API key'], 401);
    }

    $hash = hash('sha256', $rawKey);
    $stmt = $pdo->prepare('SELECT * FROM api_keys WHERE key_hash = :hash AND is_active = 1 LIMIT 1');
    $stmt->execute(['hash' => $hash]);
    $apiKey = $stmt->fetch(PDO::FETCH_ASSOC);

    if ($apiKey === false) {
        send_json(['error' => 'Invalid API key'], 403);
    }

    $stmt = $pdo->prepare('UPDATE api_keys SET last_used_at = NOW() WHERE id = :id');
    $stmt->execute(['id' => $apiKey['id']]);

    $apiKey['permissions'] = json_decode($apiKey['permissions'] ?? '[]', true) ?: [];
    return $apiKey;
}

function require_permission(array $apiKey, string $permission): void
{
    if (!in_array($permission, $apiKey['permissions'], true)) {
        send_json(['error' => 'Permission denied'], 403);
    }
}

function require_enterprise_api_enabled(PDO $pdo): void
{
    if (get_setting($pdo, 'enterprise_api_enabled', '0') !== '1') {
        send_json(['error' => 'Enterprise API is disabled'], 403);
    }
}

function verify_enterprise_tier(PDO $pdo): void
{
    $tier = get_setting($pdo, 'adrs_tier', 'core');
    if ($tier !== 'enterprise') {
        send_json(['error' => 'Enterprise tier required'], 403);
    }
}

function current_api_endpoint(): string
{
    $path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
    return '/' . trim(basename($path), '/');
}

function log_integration(PDO $pdo, string $direction, string $endpoint, int $statusCode, array $requestBody, $responseBody, ?array $apiKey = null, int $durationMs = 0): void
{
    $requestJson = json_encode($requestBody, JSON_UNESCAPED_UNICODE);
    $responseJson = is_array($responseBody) ? json_encode($responseBody, JSON_UNESCAPED_UNICODE) : (string)$responseBody;
    $stmt = $pdo->prepare(
        'INSERT INTO integration_logs (system_id, api_key_id, direction, endpoint, method, status_code, request_body, response_body, records_affected, duration_ms, ip_address)
         VALUES (:system_id, :api_key_id, :direction, :endpoint, :method, :status_code, :request_body, :response_body, :records_affected, :duration_ms, :ip_address)'
    );
    $stmt->execute([
        'system_id' => $apiKey['system_id'] ?? null,
        'api_key_id' => $apiKey['id'] ?? null,
        'direction' => $direction,
        'endpoint' => $endpoint,
        'method' => $_SERVER['REQUEST_METHOD'] ?? 'GET',
        'status_code' => $statusCode,
        'request_body' => $requestJson,
        'response_body' => $responseJson,
        'records_affected' => 0,
        'duration_ms' => $durationMs,
        'ip_address' => $_SERVER['REMOTE_ADDR'] ?? null,
    ]);
}

function send_json_logged(PDO $pdo, array $data, int $statusCode = 200, ?array $apiKey = null): void
{
    $start = microtime(true);
    $requestBody = get_api_request_body();
    log_integration($pdo, 'inbound', current_api_endpoint(), $statusCode, $requestBody, $data, $apiKey, 0);
    send_json($data, $statusCode);
}
