<?php
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/helpers.php';

$pdo = get_pdo();
$dispatches = $pdo->prepare('SELECT id, record_id, system_id, endpoint_url, payload, attempts FROM disposal_dispatches WHERE status = "pending" ORDER BY created_at ASC LIMIT 20');
$dispatches->execute();
$items = $dispatches->fetchAll(PDO::FETCH_ASSOC);

foreach ($items as $item) {
    $payload = json_decode($item['payload'] ?? '{}', true);
    $endpoint = $item['endpoint_url'];

    if (!$endpoint) {
        $stmt = $pdo->prepare('UPDATE disposal_dispatches SET status = "failed", error_message = :error, attempts = attempts + 1 WHERE id = :id');
        $stmt->execute(['error' => 'Missing endpoint_url', 'id' => $item['id']]);
        continue;
    }

    $start = microtime(true);
    $ch = curl_init($endpoint);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 20);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
    $response = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curlErr = curl_error($ch);
    curl_close($ch);
    $duration = (int)((microtime(true) - $start) * 1000);

    if ($response !== false && $code >= 200 && $code < 300) {
        $stmt = $pdo->prepare('UPDATE disposal_dispatches SET status = "sent", response_code = :code, response_body = :body, sent_at = NOW(), attempts = attempts + 1 WHERE id = :id');
        $stmt->execute(['code' => $code, 'body' => $response, 'id' => $item['id']]);
    } else {
        $stmt = $pdo->prepare('UPDATE disposal_dispatches SET status = "failed", response_code = :code, response_body = :body, attempts = attempts + 1 WHERE id = :id');
        $stmt->execute(['code' => $code ?: 0, 'body' => $curlErr ?: $response, 'id' => $item['id']]);
    }

    if (!empty($item['system_id'])) {
        $log = $pdo->prepare(
            'INSERT INTO integration_logs (system_id, direction, endpoint, method, status_code, request_body, response_body, records_affected, duration_ms, ip_address)
             VALUES (:system_id, "outbound", :endpoint, "POST", :status_code, :request_body, :response_body, :records_affected, :duration_ms, :ip_address)'
        );
        $log->execute([
            'system_id' => $item['system_id'],
            'endpoint' => $endpoint,
            'status_code' => $code ?: 0,
            'request_body' => json_encode($payload, JSON_UNESCAPED_UNICODE),
            'response_body' => $response !== false ? $response : $curlErr,
            'records_affected' => 0,
            'duration_ms' => $duration,
            'ip_address' => $_SERVER['REMOTE_ADDR'] ?? null,
        ]);
    }
}

echo 'Disposal dispatch cron completed.';
