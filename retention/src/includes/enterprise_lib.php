<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/records_lib.php';

/**
 * ADRS Enterprise business logic (testable). Covers: API-key lifecycle (E1, SHA-256 hashed),
 * auto-categorisation (E5 first-match-by-priority), async intake queue (E2), inbound consent
 * signal matching (E4), and outbound disposal dispatch queueing (E3). The REST endpoints and
 * cron scripts are thin wrappers over these functions.
 *
 * Tier gating: callers must verify get_setting($pdo,'adrs_tier')==='enterprise' first.
 */

/* ----------------------------- API keys (E1) ----------------------------- */

/** Generate a raw key + its SHA-256 hash + display prefix. Raw is shown to the user once only. */
function generate_api_key(): array {
    $raw = 'adrs_' . bin2hex(random_bytes(24)); // 53 chars, unguessable
    return ['raw' => $raw, 'hash' => hash('sha256', $raw), 'prefix' => substr($raw, 0, 12)];
}

/**
 * Create an API key for a connected system. Returns ['id'=>int, 'raw'=>string].
 * Only the hash + prefix are stored; the raw key is returned ONCE for the caller to show.
 */
function create_api_key(PDO $pdo, int $system_id, string $name, array $permissions, int $rate_limit, ?int $actor_id, ?string $expires_at = null): array {
    $k = generate_api_key();
    $pdo->prepare(
        "INSERT INTO api_keys (system_id, key_name, key_hash, key_prefix, permissions, rate_limit_per_min, created_by, expires_at)
         VALUES (:sid,:name,:hash,:prefix,:perms,:rl,:by,:exp)"
    )->execute([
        'sid' => $system_id, 'name' => $name, 'hash' => $k['hash'], 'prefix' => $k['prefix'],
        'perms' => json_encode(array_values($permissions)), 'rl' => $rate_limit, 'by' => $actor_id, 'exp' => $expires_at,
    ]);
    $id = (int) $pdo->lastInsertId();
    log_audit($pdo, 'user_updated', 'system', $id, $actor_id, ['api_key_created' => $name, 'prefix' => $k['prefix']], get_client_ip());
    return ['id' => $id, 'raw' => $k['raw']];
}

/** Verify a raw API key. Returns the key row (joined with system) if valid+active, else null. Updates last_used_at. */
function verify_api_key(PDO $pdo, string $raw_key): ?array {
    if ($raw_key === '') { return null; }
    $stmt = $pdo->prepare(
        "SELECT ak.*, cs.name AS system_name, cs.is_active AS system_active, cs.base_url
         FROM api_keys ak JOIN connected_systems cs ON cs.id = ak.system_id
         WHERE ak.key_hash = :h AND ak.is_active = 1 AND ak.revoked_at IS NULL
           AND (ak.expires_at IS NULL OR ak.expires_at > NOW()) LIMIT 1"
    );
    $stmt->execute(['h' => hash('sha256', $raw_key)]);
    $key = $stmt->fetch();
    if (!$key || (int) $key['system_active'] !== 1) { return null; }
    $pdo->prepare("UPDATE api_keys SET last_used_at = NOW() WHERE id = :id")->execute(['id' => $key['id']]);
    $key['permissions'] = json_decode($key['permissions'] ?? '[]', true) ?: [];
    return $key;
}

/** Revoke an API key. */
function revoke_api_key(PDO $pdo, int $key_id, ?int $actor_id): void {
    $pdo->prepare("UPDATE api_keys SET is_active = 0, revoked_at = NOW() WHERE id = :id")->execute(['id' => $key_id]);
    log_audit($pdo, 'user_updated', 'system', $key_id, $actor_id, ['api_key_revoked' => $key_id], get_client_ip());
}

/** True if the key has the given permission (empty permissions = allow all, for convenience). */
function api_key_can(array $key, string $permission): bool {
    $perms = $key['permissions'] ?? [];
    return $perms === [] || in_array($permission, $perms, true);
}

/** Rate-limit gate: returns true if under the limit (counted from inbound integration_logs in the last minute). */
function within_rate_limit(PDO $pdo, int $api_key_id, int $limit_per_min): bool {
    $stmt = $pdo->prepare(
        "SELECT COUNT(*) c FROM integration_logs
         WHERE api_key_id = :id AND direction='inbound' AND created_at >= DATE_SUB(NOW(), INTERVAL 1 MINUTE)"
    );
    $stmt->execute(['id' => $api_key_id]);
    return (int) $stmt->fetch()['c'] < $limit_per_min;
}

/** Append an integration_logs row. Never throws. */
function log_integration(PDO $pdo, ?int $system_id, ?int $api_key_id, string $direction, string $endpoint, string $method, int $status, ?array $req, ?array $res, int $records_affected = 0, int $duration_ms = 0, ?string $error = null): void {
    try {
        $pdo->prepare(
            "INSERT INTO integration_logs (system_id, api_key_id, direction, endpoint, method, status_code, request_body, response_body, records_affected, duration_ms, ip_address, error_message)
             VALUES (:s,:k,:d,:e,:m,:sc,:rq,:rs,:ra,:du,:ip,:err)"
        )->execute([
            's' => $system_id, 'k' => $api_key_id, 'd' => $direction, 'e' => $endpoint, 'm' => $method, 'sc' => $status,
            'rq' => $req ? json_encode($req) : null, 'rs' => $res ? json_encode($res) : null,
            'ra' => $records_affected, 'du' => $duration_ms, 'ip' => get_client_ip(), 'err' => $error,
        ]);
    } catch (Throwable $e) { /* logging must never break the API */ }
}

/* ----------------------------- Auto-categorisation (E5) ----------------------------- */

/**
 * Resolve a category for an inbound object using auto_categorization_rules.
 * First active matching rule by ascending priority wins. A rule matches when object_type
 * matches and (no condition, OR metadata[condition_field] === condition_value).
 * Returns category_id or null if nothing matches.
 */
function auto_categorize(PDO $pdo, int $system_id, string $object_type, array $metadata = []): ?int {
    $stmt = $pdo->prepare(
        "SELECT * FROM auto_categorization_rules
         WHERE system_id = :s AND is_active = 1 AND object_type = :ot
         ORDER BY priority ASC, id ASC"
    );
    $stmt->execute(['s' => $system_id, 'ot' => $object_type]);
    foreach ($stmt->fetchAll() as $rule) {
        if ($rule['condition_field'] === null || $rule['condition_field'] === '') {
            return (int) $rule['category_id'];
        }
        $val = $metadata[$rule['condition_field']] ?? null;
        if ($val !== null && (string) $val === (string) $rule['condition_value']) {
            return (int) $rule['category_id'];
        }
    }
    return null;
}

/* ----------------------------- Intake queue (E2) ----------------------------- */

/** Insert a record into the intake queue. Returns queue id. */
function enqueue_intake(PDO $pdo, int $system_id, ?int $api_key_id, ?string $batch_id, array $payload): int {
    $pdo->prepare(
        "INSERT INTO intake_queue (system_id, api_key_id, batch_id, payload, status) VALUES (:s,:k,:b,:p,'pending')"
    )->execute(['s' => $system_id, 'k' => $api_key_id, 'b' => $batch_id, 'p' => json_encode($payload)]);
    return (int) $pdo->lastInsertId();
}

/** True if a non-deleted record already exists with this reference in this category (duplicate guard). */
function intake_is_duplicate(PDO $pdo, string $external_ref, int $category_id): bool {
    $stmt = $pdo->prepare("SELECT 1 FROM data_records WHERE record_reference = :r AND category_id = :c AND deleted_at IS NULL LIMIT 1");
    $stmt->execute(['r' => $external_ref, 'c' => $category_id]);
    return (bool) $stmt->fetch();
}

/**
 * Process a single intake_queue row: auto-categorise, create the data_record, link them.
 * Returns ['status'=>'completed'|'failed'|'duplicate', 'record_id'=>?int, 'error'=>?string].
 */
function process_intake_item(PDO $pdo, array $item): array {
    $payload = is_array($item['payload']) ? $item['payload'] : (json_decode($item['payload'], true) ?: []);
    $objectType = $payload['object_type'] ?? '';
    $externalRef = $payload['external_ref'] ?? '';
    $metadata = $payload['metadata'] ?? [];

    try {
        if ($objectType === '' || $externalRef === '') { throw new RuntimeException('object_type and external_ref are required'); }

        $categoryId = $payload['category_id'] ?? auto_categorize($pdo, (int) $item['system_id'], $objectType, $metadata);
        if (!$categoryId) {
            $pdo->prepare("UPDATE intake_queue SET status='failed', error='no_matching_rule', attempts=attempts+1, processed_at=NOW() WHERE id=:id")->execute(['id' => $item['id']]);
            return ['status' => 'failed', 'record_id' => null, 'error' => 'no_matching_rule'];
        }

        if (intake_is_duplicate($pdo, $externalRef, (int) $categoryId)) {
            $pdo->prepare("UPDATE intake_queue SET status='duplicate', category_id=:c, processed_at=NOW() WHERE id=:id")->execute(['c' => $categoryId, 'id' => $item['id']]);
            return ['status' => 'duplicate', 'record_id' => null, 'error' => null];
        }

        $category = fetch_category($pdo, (int) $categoryId);
        $collectionDate = !empty($payload['collection_date']) ? $payload['collection_date'] : date('Y-m-d');
        $retentionEnd = compute_retention_end($category, $collectionDate);

        $pdo->prepare(
            "INSERT INTO data_records (category_id, record_reference, data_subject_type, collection_date, retention_end_date, status, created_by, notes)
             VALUES (:c,:r,:st,:cd,:re,'active',NULL,:notes)"
        )->execute([
            'c' => $categoryId, 'r' => $externalRef, 'st' => $payload['data_subject_type'] ?? null,
            'cd' => $collectionDate, 're' => $retentionEnd, 'notes' => 'Captured via Enterprise API from system #' . $item['system_id'],
        ]);
        $recordId = (int) $pdo->lastInsertId();

        $pdo->prepare("UPDATE intake_queue SET status='completed', category_id=:c, record_id=:r, processed_at=NOW() WHERE id=:id")
            ->execute(['c' => $categoryId, 'r' => $recordId, 'id' => $item['id']]);
        $pdo->prepare("UPDATE connected_systems SET records_synced = records_synced + 1 WHERE id=:s")->execute(['s' => $item['system_id']]);
        log_audit($pdo, 'record_created', 'data_record', $recordId, null, ['source' => 'enterprise_api', 'external_ref' => $externalRef], null);

        return ['status' => 'completed', 'record_id' => $recordId, 'error' => null];
    } catch (Throwable $e) {
        $pdo->prepare("UPDATE intake_queue SET status='failed', error=:err, attempts=attempts+1, processed_at=NOW() WHERE id=:id")
            ->execute(['err' => $e->getMessage(), 'id' => $item['id']]);
        return ['status' => 'failed', 'record_id' => null, 'error' => $e->getMessage()];
    }
}

/** Process up to $limit pending intake rows. Returns counts. */
function process_intake_queue(PDO $pdo, int $limit = 100): array {
    $rows = $pdo->query("SELECT * FROM intake_queue WHERE status='pending' AND attempts < 3 ORDER BY id ASC LIMIT " . (int) $limit)->fetchAll();
    $r = ['processed' => 0, 'created' => 0, 'failed' => 0, 'duplicate' => 0];
    foreach ($rows as $item) {
        $res = process_intake_item($pdo, $item);
        $r['processed']++;
        if ($res['status'] === 'completed') { $r['created']++; }
        elseif ($res['status'] === 'duplicate') { $r['duplicate']++; }
        else { $r['failed']++; }
    }
    return $r;
}

/* ----------------------------- Consent signals (E4) ----------------------------- */

/**
 * Record an inbound consent signal and attempt to match it to a consent-based record by
 * external_ref. On match: set consent_withdrawn_at + a consent-countdown retention_end_date.
 * Returns ['signal_id'=>int, 'matched'=>bool, 'record_id'=>?int].
 */
function record_consent_signal(PDO $pdo, int $system_id, string $external_ref, string $signal_type, array $payload = []): array {
    $pdo->prepare(
        "INSERT INTO consent_signals (system_id, external_ref, signal_type, raw_payload, status) VALUES (:s,:r,:t,:p,'pending')"
    )->execute(['s' => $system_id, 'r' => $external_ref, 't' => $signal_type, 'p' => json_encode($payload)]);
    $signalId = (int) $pdo->lastInsertId();
    $matched = match_consent_signal($pdo, $signalId);
    return ['signal_id' => $signalId, 'matched' => $matched['matched'], 'record_id' => $matched['record_id']];
}

/** Try to match a pending/unmatched consent signal to a record. Returns ['matched'=>bool,'record_id'=>?int]. */
function match_consent_signal(PDO $pdo, int $signal_id): array {
    $sig = $pdo->query("SELECT * FROM consent_signals WHERE id = " . (int) $signal_id)->fetch();
    if (!$sig || in_array($sig['status'], ['processed'], true)) { return ['matched' => false, 'record_id' => null]; }

    $stmt = $pdo->prepare(
        "SELECT dr.id FROM data_records dr JOIN data_categories dc ON dc.id = dr.category_id
         WHERE dr.record_reference = :ref AND dc.disposal_trigger = 'consent_withdrawal'
           AND dr.deleted_at IS NULL AND dr.status != 'disposed' LIMIT 1"
    );
    $stmt->execute(['ref' => $sig['external_ref']]);
    $rec = $stmt->fetch();

    if (!$rec) {
        $pdo->prepare("UPDATE consent_signals SET status='unmatched' WHERE id=:id")->execute(['id' => $signal_id]);
        return ['matched' => false, 'record_id' => null];
    }

    $days = (int) get_setting($pdo, 'consent_disposal_days', '30');
    $pdo->prepare(
        "UPDATE data_records SET consent_withdrawn_at = NOW(), retention_end_date = DATE_ADD(CURDATE(), INTERVAL :d DAY) WHERE id = :id"
    )->execute(['d' => $days, 'id' => $rec['id']]);
    $pdo->prepare("UPDATE consent_signals SET status='processed', record_id=:r, processed_at=NOW() WHERE id=:id")
        ->execute(['r' => $rec['id'], 'id' => $signal_id]);
    log_audit($pdo, 'consent_withdrawn', 'data_record', (int) $rec['id'], null, ['source' => 'enterprise_signal', 'external_ref' => $sig['external_ref']], null);
    return ['matched' => true, 'record_id' => (int) $rec['id']];
}

/** Retry all unmatched consent signals from the last 7 days. Returns count newly matched. */
function retry_unmatched_consent_signals(PDO $pdo): int {
    $rows = $pdo->query("SELECT id FROM consent_signals WHERE status='unmatched' AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)")->fetchAll();
    $n = 0;
    foreach ($rows as $r) { if (match_consent_signal($pdo, (int) $r['id'])['matched']) { $n++; } }
    return $n;
}

/* ----------------------------- Outbound disposal dispatch (E3) ----------------------------- */

/**
 * Queue outbound disposal instructions for a record to every connected system that originally
 * synced it (resolved via intake_queue). Returns number of dispatch rows queued. Called from
 * execute_disposal() when adrs_tier = 'enterprise'.
 */
function queue_disposal_dispatch(PDO $pdo, int $record_id, string $method): int {
    $rec = $pdo->query("SELECT record_reference FROM data_records WHERE id = " . (int) $record_id)->fetch();
    if (!$rec) { return 0; }
    $systems = $pdo->prepare(
        "SELECT DISTINCT iq.system_id, cs.base_url FROM intake_queue iq
         JOIN connected_systems cs ON cs.id = iq.system_id
         WHERE iq.record_id = :r AND cs.is_active = 1"
    );
    $systems->execute(['r' => $record_id]);
    $n = 0;
    foreach ($systems->fetchAll() as $s) {
        $endpoint = $s['base_url'] ? rtrim($s['base_url'], '/') . '/adrs/disposal' : null;
        $pdo->prepare(
            "INSERT INTO disposal_dispatches (record_id, system_id, dispatch_type, external_ref, endpoint_url, payload, status)
             VALUES (:rec,:sys,:t,:ref,:url,:pl,'pending')"
        )->execute([
            'rec' => $record_id, 'sys' => $s['system_id'], 't' => $method, 'ref' => $rec['record_reference'],
            'url' => $endpoint, 'pl' => json_encode(['action' => $method, 'external_ref' => $rec['record_reference']]),
        ]);
        $n++;
    }
    return $n;
}

/**
 * Send pending disposal dispatches via webhook POST (cURL). $sender is an optional callable
 * (url, payload) => [http_code, body] to allow tests to inject a stub instead of real HTTP.
 * Returns ['sent'=>int,'failed'=>int].
 */
function process_disposal_dispatches(PDO $pdo, int $limit = 50, ?callable $sender = null): array {
    $retryLimit = (int) get_setting($pdo, 'webhook_retry_limit', '3');
    $rows = $pdo->query("SELECT * FROM disposal_dispatches WHERE status='pending' AND attempts < " . $retryLimit . " ORDER BY id ASC LIMIT " . (int) $limit)->fetchAll();
    $sender = $sender ?? 'enterprise_http_post';
    $sent = 0; $failed = 0;
    foreach ($rows as $d) {
        if (!$d['endpoint_url']) { // No webhook configured — mark confirmed (internal-only disposal)
            $pdo->prepare("UPDATE disposal_dispatches SET status='confirmed', confirmed_at=NOW() WHERE id=:id")->execute(['id' => $d['id']]);
            $sent++;
            continue;
        }
        [$code, $body] = $sender($d['endpoint_url'], json_decode($d['payload'], true) ?: []);
        if ($code >= 200 && $code < 300) {
            $pdo->prepare("UPDATE disposal_dispatches SET status='confirmed', response_code=:c, response_body=:b, sent_at=NOW(), confirmed_at=NOW(), attempts=attempts+1 WHERE id=:id")
                ->execute(['c' => $code, 'b' => substr((string) $body, 0, 2000), 'id' => $d['id']]);
            log_integration($pdo, (int) $d['system_id'], null, 'outbound', '/adrs/disposal', 'POST', (int) $code, null, null, 1);
            $sent++;
        } else {
            $newStatus = ((int) $d['attempts'] + 1) >= $retryLimit ? 'failed' : 'pending';
            $pdo->prepare("UPDATE disposal_dispatches SET status=:s, response_code=:c, response_body=:b, sent_at=NOW(), attempts=attempts+1 WHERE id=:id")
                ->execute(['s' => $newStatus, 'c' => $code ?: null, 'b' => substr((string) $body, 0, 2000), 'id' => $d['id']]);
            $failed++;
        }
    }
    return ['sent' => $sent, 'failed' => $failed];
}

/* ----------------------------- Enterprise daily engine steps (A/B/C) ----------------------------- */

/** Step C: purge integration_logs older than api_log_retention_days. Returns rows deleted. */
function purge_integration_logs(PDO $pdo): int {
    $days = (int) get_setting($pdo, 'api_log_retention_days', '90');
    $stmt = $pdo->prepare("DELETE FROM integration_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL :d DAY)");
    $stmt->execute(['d' => $days]);
    return $stmt->rowCount();
}

/**
 * Run the Enterprise additions to the daily engine:
 *  A — process any pending intake queue items (fallback if the 5-min cron is not configured)
 *  B — retry unmatched consent signals from the last 7 days
 *  C — purge old integration logs
 * Returns a summary. No-op-safe; caller should only invoke when adrs_tier = 'enterprise'.
 */
function run_enterprise_engine_steps(PDO $pdo): array {
    $intake = (get_setting($pdo, 'intake_queue_enabled', '1') === '1') ? process_intake_queue($pdo, 100) : ['created' => 0];
    $consentRetried = (get_setting($pdo, 'consent_signal_enabled', '1') === '1') ? retry_unmatched_consent_signals($pdo) : 0;
    $purged = purge_integration_logs($pdo);
    return ['intake_created' => $intake['created'] ?? 0, 'consent_retried' => $consentRetried, 'logs_purged' => $purged];
}

/** Real webhook sender via cURL (used in production; tests inject a stub). Returns [http_code, body]. */
function enterprise_http_post(string $url, array $payload): array {
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($payload),
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 15,
        CURLOPT_CONNECTTIMEOUT => 8,
    ]);
    $body = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    if ($body === false) { $body = curl_error($ch); $code = 0; }
    return [$code, $body]; // curl_close() is a no-op since PHP 8.0 and deprecated in 8.5

}
