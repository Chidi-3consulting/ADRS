# Prompt 15 — Outbound Disposal Dispatch
# ENTERPRISE TIER ONLY

## Context
When ADRS disposes of a record that was originally ingested from a connected system,
it must also instruct that connected system to delete or anonymise the same data
from ITS own storage. This is the outbound side of Enterprise — closing the loop.

Without this, ADRS could mark a record as disposed while the source system
still holds the original data indefinitely.

---

## How it works

```
ADRS disposes a record
    │
    ▼
Check: was this record ingested via Enterprise API?
(data_records.created_by = NULL AND source system known)
    │
    ├── YES → create disposal_dispatches row
    │         → cron sends webhook to connected system
    │         → connected system confirms deletion
    │
    └── NO → standard disposal only (Core behaviour)
```

---

## Step 1: Update `src/pages/schedule/dispose.php`

After the standard disposal executes (in `execute_disposal()`), add:

```php
function execute_disposal(PDO $pdo, array $record, ?int $user_id): bool {
    // ... existing disposal logic ...

    // ENTERPRISE: dispatch to connected system if applicable
    if (get_setting($pdo, 'adrs_tier') === 'enterprise' &&
        get_setting($pdo, 'disposal_dispatch_enabled') === '1') {
        dispatch_disposal_to_system($pdo, $record, $disposal_method);
    }

    return true;
}
```

---

## Step 2: Create `src/includes/enterprise_dispatch.php`

```php
/**
 * Queue a disposal instruction to the originating connected system.
 * Looks up which system ingested the record via intake_queue.
 */
function dispatch_disposal_to_system(PDO $pdo, array $record, string $method): void {
    if (get_setting($pdo, 'adrs_tier') !== 'enterprise') return;

    // Find the originating system from intake_queue
    $stmt = $pdo->prepare(
        "SELECT iq.system_id, iq.payload, cs.base_url, cs.name AS system_name
         FROM intake_queue iq
         JOIN connected_systems cs ON cs.id = iq.system_id
         WHERE iq.record_id = ? AND iq.status = 'completed'
         LIMIT 1"
    );
    $stmt->execute([$record['id']]);
    $source = $stmt->fetch();

    if (!$source || empty($source['base_url'])) return; // No dispatch if no webhook URL

    // Extract external_ref from original payload
    $payload = json_decode($source['payload'], true);
    $external_ref = $payload['external_ref'] ?? null;
    if (!$external_ref) return;

    // Build dispatch payload
    $dispatch_payload = [
        'adrs_record_id'    => $record['id'],
        'external_ref'      => $external_ref,
        'disposal_type'     => $method,
        'disposed_at'       => date('c'),
        'adrs_audit_ref'    => 'ADRS-DISP-' . $record['id'],
        'instruction'       => match($method) {
            'delete'    => 'Permanently delete all data associated with this reference.',
            'anonymise' => 'Remove all personal identifiers associated with this reference.',
            'archive'   => 'Move all data associated with this reference to your long-term archive.',
        }
    ];

    // Insert to dispatch queue
    $pdo->prepare(
        "INSERT INTO disposal_dispatches
         (record_id, system_id, dispatch_type, external_ref, endpoint_url, payload, status)
         VALUES (?,?,?,?,?,?,'pending')"
    )->execute([
        $record['id'],
        $source['system_id'],
        $method,
        $external_ref,
        rtrim($source['base_url'], '/') . '/adrs/disposal',
        json_encode($dispatch_payload)
    ]);
}
```

---

## Step 3: Create `src/engine/disposal_dispatch_cron.php`

Add to cPanel cron (runs every 10 minutes):
```
*/10 * * * * /usr/local/bin/php /path/to/disposal_dispatch_cron.php >> /home/username/logs/dispatch_cron.log 2>&1
```

**Logic:**
```php
if (php_sapi_name() !== 'cli') { http_response_code(403); exit; }

$pdo = get_db();

if (get_setting($pdo, 'disposal_dispatch_enabled') !== '1') { exit; }

$retry_limit = (int) get_setting($pdo, 'webhook_retry_limit', '3');

// Fetch pending dispatches (attempts < retry_limit)
$stmt = $pdo->prepare(
    "SELECT dd.*, cs.name AS system_name
     FROM disposal_dispatches dd
     JOIN connected_systems cs ON cs.id = dd.system_id
     WHERE dd.status IN ('pending', 'failed')
       AND dd.attempts < ?
     ORDER BY dd.created_at ASC
     LIMIT 50"
);
$stmt->execute([$retry_limit]);
$dispatches = $stmt->fetchAll();

foreach ($dispatches as $dispatch) {
    $start = microtime(true);
    $sent_ok = false;

    try {
        // Send webhook POST to connected system
        $ch = curl_init($dispatch['endpoint_url']);
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $dispatch['payload'],
            CURLOPT_HTTPHEADER     => [
                'Content-Type: application/json',
                'X-ADRS-Dispatch: 1',
                'X-ADRS-Record-ID: ' . $dispatch['record_id']
            ],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 15,
            CURLOPT_SSL_VERIFYPEER => (APP_ENV === 'production'),
        ]);
        $response_body = curl_exec($ch);
        $http_code     = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $duration_ms   = (int)((microtime(true) - $start) * 1000);
        curl_close($ch);

        $success = $http_code >= 200 && $http_code < 300;

        $pdo->prepare(
            "UPDATE disposal_dispatches
             SET status = ?, response_code = ?, response_body = ?,
                 attempts = attempts + 1,
                 sent_at = IF(? = 1, NOW(), sent_at),
                 confirmed_at = IF(? = 1, NOW(), NULL)
             WHERE id = ?"
        )->execute([
            $success ? 'confirmed' : 'failed',
            $http_code,
            substr($response_body, 0, 2000),
            $success ? 1 : 0,
            $success ? 1 : 0,
            $dispatch['id']
        ]);

        // Log to integration_logs
        log_api_call($pdo, $dispatch['system_id'], null, 'outbound',
            $dispatch['endpoint_url'], 'POST', $http_code,
            json_decode($dispatch['payload'], true),
            json_decode($response_body, true),
            1, $duration_ms,
            $success ? null : "HTTP {$http_code}");

        if ($success) {
            cron_log("Dispatch confirmed: record #{$dispatch['record_id']} → {$dispatch['system_name']}");
        }

    } catch (Exception $e) {
        $pdo->prepare("UPDATE disposal_dispatches SET attempts = attempts + 1, status = 'failed' WHERE id = ?")
            ->execute([$dispatch['id']]);
        cron_log("Dispatch error: record #{$dispatch['record_id']}: " . $e->getMessage());
    }
}
```

---

## Step 4: Disposal dispatch UI in record view

Add to `src/pages/schedule/view.php` (Enterprise tier only):

```html
<!-- Show if enterprise tier AND dispatches exist for this record -->
<?php if ($adrs_tier === 'enterprise' && !empty($dispatches)): ?>
<div class="card mt-4">
  <div class="card-header card-header-teal">
    <i class="bi bi-arrow-up-right-circle"></i>
    Outbound Disposal Dispatches
  </div>
  <div class="card-body">
    <p class="text-muted small">
      When this record was disposed, ADRS sent instructions to the
      originating system to delete or anonymise the corresponding data.
    </p>
    <table class="table table-sm">
      <thead>
        <tr><th>System</th><th>Type</th><th>Status</th><th>Sent</th><th>Confirmed</th><th>Attempts</th></tr>
      </thead>
      <tbody>
        <?php foreach ($dispatches as $d): ?>
        <tr>
          <td><?= sanitize($d['system_name']) ?></td>
          <td><?= get_disposal_method_label($d['dispatch_type']) ?></td>
          <td><?= get_status_badge($d['status']) ?></td>
          <td><?= $d['sent_at'] ? format_datetime($d['sent_at']) : '—' ?></td>
          <td><?= $d['confirmed_at'] ? format_datetime($d['confirmed_at']) : '—' ?></td>
          <td><?= $d['attempts'] ?></td>
        </tr>
        <?php endforeach; ?>
      </tbody>
    </table>
  </div>
</div>
<?php endif; ?>
```

---

## Step 5: Update main cron engine for consent signals

In `src/engine/retention_cron.php`, add a new Step (after existing Step 8):

**Step: Process unmatched consent signals**
```sql
SELECT cs.*, dr.id AS record_id
FROM consent_signals cs
LEFT JOIN data_records dr ON dr.record_reference = cs.external_ref
  AND dr.deleted_at IS NULL
WHERE cs.status = 'unmatched'
  AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
```
For each unmatched signal:
- Re-attempt matching (record may have been created after signal arrived)
- If matched: update `consent_signals.record_id`, set `status = 'processed'`
  Then set `data_records.consent_withdrawn_at = NOW()`,
  `retention_end_date = DATE_ADD(NOW(), INTERVAL consent_disposal_days DAY)`
- Log `consent_withdrawn` to audit_log
- Notify DPOs

---

## Step 6: Update audit_log action enum (if not already present)

Add to audit_log.action ENUM:
```
'disposal_dispatched',
'disposal_dispatch_confirmed',
'disposal_dispatch_failed',
'consent_signal_received',
'consent_signal_matched',
'api_key_created',
'api_key_revoked',
'connected_system_created',
'connected_system_updated'
```
Run `ALTER TABLE audit_log MODIFY COLUMN action ENUM(...)` in a migration.
