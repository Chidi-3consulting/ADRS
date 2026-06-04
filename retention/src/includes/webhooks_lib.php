<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';

/**
 * Phase 3 ops webhooks: fire outbound notifications (Slack/Teams/generic JSON) to configured
 * endpoints when key events occur (breaches, escalations, failures). Self-contained cURL.
 */

/** True if an endpoint's event_types ('*' or CSV) subscribes to $event. */
function webhook_matches(string $event_types, string $event): bool {
    $event_types = trim($event_types);
    if ($event_types === '' || $event_types === '*') { return true; }
    $list = array_map('trim', explode(',', $event_types));
    return in_array($event, $list, true);
}

/**
 * Fire an ops event to every active, subscribed webhook (when ops_webhooks_enabled=1).
 * $sender(url,payload) => [code,body] can be injected for tests. Returns count fired.
 */
function fire_ops_event(PDO $pdo, string $event, array $payload, ?callable $sender = null): int {
    if (get_setting($pdo, 'ops_webhooks_enabled', '0') !== '1') { return 0; }
    $endpoints = $pdo->query("SELECT * FROM webhook_endpoints WHERE is_active = 1")->fetchAll();
    if (!$endpoints) { return 0; }
    $sender = $sender ?? 'webhook_http_post';
    $body = ['event' => $event, 'timestamp' => date('c'), 'data' => $payload];
    $fired = 0;
    foreach ($endpoints as $e) {
        if (!webhook_matches($e['event_types'], $event)) { continue; }
        try {
            $sender($e['url'], $body);
            $pdo->prepare("UPDATE webhook_endpoints SET last_fired_at = NOW() WHERE id = :id")->execute(['id' => $e['id']]);
            $fired++;
        } catch (Throwable $ex) { /* never let a webhook break the originating action */ }
    }
    return $fired;
}

/** Production sender via cURL. Returns [http_code, body]. */
function webhook_http_post(string $url, array $payload): array {
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($payload),
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 10,
        CURLOPT_CONNECTTIMEOUT => 6,
    ]);
    $body = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    return [$code, $body === false ? curl_error($ch) : $body];
}
