# Prompt 13 — Enterprise REST API Layer (Inbound Data Capture)
# ENTERPRISE TIER ONLY — only build if adrs_tier = 'enterprise'

## Context
This prompt builds the REST API that external systems call to push data into ADRS.
It is the core of the Enterprise tier — the entry point for all automatic data capture.
Refer to `.github/copilot-instructions.md` for all base rules.

All API files live in `src/api/v1/`. This is a SEPARATE directory from
`src/api/get_category.php` (which is Core tier AJAX only).

---

## Architecture Overview

```
External System (CRM / Core Banking / HR)
    │
    │  POST /api/v1/ingest        ← single record
    │  POST /api/v1/ingest/batch  ← up to 500 records
    │  POST /api/v1/consent/withdraw  ← consent signal
    │  GET  /api/v1/categories    ← available categories
    │  GET  /api/v1/health        ← ping / health check
    │
    ▼
src/api/v1/router.php  ← routes all /api/v1/* requests
    │
    ├── authenticate() via X-API-Key header
    ├── rate_limit() per key per minute
    ├── validate_tier()  ← returns 403 if adrs_tier != 'enterprise'
    │
    ▼
Endpoint handler  →  intake_queue table  →  queue processor cron
                                              │
                                              ▼
                                        data_records table
```

---

## Step 1: Create `.htaccess` rule for API routing

In the production `.htaccess`, add BEFORE the main RewriteRule:
```apache
# Enterprise API — route /api/v1/* to router.php
RewriteRule ^api/v1/(.*)$ src/api/v1/router.php?_route=$1 [QSA,L]
```

In `.htaccess.local` (local dev), add the same rule with the local RewriteBase.

---

## Step 2: Create `src/api/v1/bootstrap.php`

Shared bootstrap for all API endpoints. Loaded by router.php.

```php
<?php
// No session_start() here — API uses key-based auth, not sessions
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/db.php';
require_once __DIR__ . '/../../includes/helpers.php';

// Set JSON response headers
header('Content-Type: application/json');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store, no-cache');
header('X-API-Version: 1.0');

/**
 * Send JSON response and exit
 */
function api_response(int $status, array $data): never {
    http_response_code($status);
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

/**
 * Verify adrs_tier = 'enterprise' — gate ALL Enterprise API calls
 */
function require_enterprise_tier(PDO $pdo): void {
    $tier = get_setting($pdo, 'adrs_tier', 'core');
    if ($tier !== 'enterprise') {
        api_response(403, [
            'error' => 'enterprise_tier_required',
            'message' => 'This endpoint requires ADRS Enterprise tier. Current tier: ' . $tier
        ]);
    }
}

/**
 * Authenticate via X-API-Key header
 * Returns the api_keys row on success
 */
function authenticate_api_key(PDO $pdo): array {
    $raw_key = $_SERVER['HTTP_X_API_KEY'] ?? '';
    if (empty($raw_key)) {
        api_response(401, ['error' => 'missing_api_key', 'message' => 'X-API-Key header is required.']);
    }

    $hash = hash('sha256', $raw_key);
    $stmt = $pdo->prepare(
        "SELECT ak.*, cs.name AS system_name, cs.is_active AS system_active
         FROM api_keys ak
         JOIN connected_systems cs ON cs.id = ak.system_id
         WHERE ak.key_hash = ?
           AND ak.is_active = 1
           AND ak.revoked_at IS NULL
           AND (ak.expires_at IS NULL OR ak.expires_at > NOW())"
    );
    $stmt->execute([$hash]);
    $key = $stmt->fetch();

    if (!$key) {
        api_response(401, ['error' => 'invalid_api_key', 'message' => 'API key is invalid, revoked, or expired.']);
    }
    if (!$key['system_active']) {
        api_response(403, ['error' => 'system_inactive', 'message' => 'The connected system for this API key is inactive.']);
    }

    // Update last_used_at
    $pdo->prepare("UPDATE api_keys SET last_used_at = NOW() WHERE id = ?")
        ->execute([$key['id']]);

    return $key;
}

/**
 * Rate limit check: max N requests per minute per key
 * Uses integration_logs count — lightweight, no Redis needed on shared hosting
 */
function check_rate_limit(PDO $pdo, int $api_key_id, int $limit_per_min): void {
    $stmt = $pdo->prepare(
        "SELECT COUNT(*) FROM integration_logs
         WHERE api_key_id = ?
           AND direction = 'inbound'
           AND created_at >= DATE_SUB(NOW(), INTERVAL 1 MINUTE)"
    );
    $stmt->execute([$api_key_id]);
    $count = (int)$stmt->fetchColumn();

    if ($count >= $limit_per_min) {
        header('Retry-After: 60');
        api_response(429, [
            'error'   => 'rate_limit_exceeded',
            'message' => "Rate limit of {$limit_per_min} requests/minute exceeded.",
            'retry_after_seconds' => 60
        ]);
    }
}

/**
 * Log every API call to integration_logs
 */
function log_api_call(
    PDO $pdo,
    ?int $system_id,
    ?int $api_key_id,
    string $direction,
    string $endpoint,
    string $method,
    int $status_code,
    ?array $request_body,
    ?array $response_body,
    int $records_affected,
    int $duration_ms,
    ?string $error = null
): void {
    try {
        $pdo->prepare(
            "INSERT INTO integration_logs
             (system_id, api_key_id, direction, endpoint, method, status_code,
              request_body, response_body, records_affected, duration_ms, ip_address, error_message)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
        )->execute([
            $system_id, $api_key_id, $direction, $endpoint, $method, $status_code,
            $request_body ? json_encode($request_body) : null,
            $response_body ? json_encode($response_body) : null,
            $records_affected, $duration_ms,
            get_client_ip(), $error
        ]);
    } catch (Exception $e) {
        // Never let logging break the API response
        error_log('API log failure: ' . $e->getMessage());
    }
}
```

---

## Step 3: Create `src/api/v1/router.php`

```php
<?php
require_once __DIR__ . '/bootstrap.php';

$route  = $_GET['_route'] ?? '';
$method = $_SERVER['REQUEST_METHOD'];
$pdo    = get_db();

require_enterprise_tier($pdo);
$api_key = authenticate_api_key($pdo);
check_rate_limit($pdo, $api_key['id'], $api_key['rate_limit_per_min']);

$permissions = json_decode($api_key['permissions'] ?? '[]', true) ?: [];

// Route dispatch
match(true) {
    $method === 'POST' && $route === 'ingest'          => require __DIR__ . '/endpoints/ingest.php',
    $method === 'POST' && $route === 'ingest/batch'    => require __DIR__ . '/endpoints/ingest_batch.php',
    $method === 'POST' && $route === 'consent/withdraw'=> require __DIR__ . '/endpoints/consent_withdraw.php',
    $method === 'GET'  && $route === 'categories'      => require __DIR__ . '/endpoints/categories.php',
    $method === 'GET'  && str_starts_with($route, 'records/') => require __DIR__ . '/endpoints/record_status.php',
    $method === 'GET'  && $route === 'health'          => require __DIR__ . '/endpoints/health.php',
    default => api_response(404, ['error' => 'not_found', 'message' => "Route not found: {$method} /api/v1/{$route}"])
};
```

---

## Step 4: Create `src/api/v1/endpoints/ingest.php`

Receives a single record from an external system.

```
POST /api/v1/ingest
Headers: X-API-Key: adrs_k1_xxxxxxxx
Content-Type: application/json

{
  "object_type": "customer_kyc",
  "external_ref": "CUST-00042",
  "data_subject_type": "Customer",
  "collection_date": "2025-08-01",
  "metadata": {
    "full_name": "Adaeze Okonkwo",
    "channel": "mobile_app"
  }
}
```

**Logic:**
1. Validate `object_type` (required) and `external_ref` (required)
2. Validate `collection_date` format (YYYY-MM-DD, not in future)
3. Run auto-categorisation rules for this system + object_type
4. If no rule matches → return 422 with `error: no_matching_rule`
5. Check for duplicate: `record_reference = external_ref` AND `category_id = resolved_category`
   → If duplicate: return 409 with `error: duplicate_record`
6. Insert to `intake_queue` with `status = 'pending'`
7. If `intake_queue_enabled = '0'`: process immediately (sync mode)
8. If `intake_queue_enabled = '1'`: return 202 Accepted (async mode)

**Success response (async):**
```json
{
  "status": "queued",
  "queue_id": 1847,
  "message": "Record accepted for processing.",
  "estimated_category": "Customer KYC & Onboarding Data"
}
```

**Success response (sync):**
```json
{
  "status": "created",
  "record_id": 304,
  "retention_end_date": "2030-08-01",
  "category": "Customer KYC & Onboarding Data",
  "message": "Record created and retention schedule started."
}
```

---

## Step 5: Create `src/api/v1/endpoints/ingest_batch.php`

Receives up to 500 records in one call.

```
POST /api/v1/ingest/batch
{
  "records": [
    {"object_type": "customer_kyc", "external_ref": "CUST-001", ...},
    {"object_type": "customer_kyc", "external_ref": "CUST-002", ...}
  ]
}
```

**Logic:**
1. Validate array length ≤ 500 (match `max_import_rows` setting)
2. Generate a `batch_id = uniqid('batch_', true)`
3. Validate each record (same rules as single ingest)
4. Insert valid records to `intake_queue` with the shared `batch_id`
5. Insert invalid records to response `failed` array (don't abort whole batch)
6. Return 202 with summary

**Response:**
```json
{
  "status": "queued",
  "batch_id": "batch_66abc123def",
  "accepted": 498,
  "rejected": 2,
  "failed": [
    {"index": 3, "external_ref": "CUST-004", "error": "no_matching_rule"},
    {"index": 7, "external_ref": null,        "error": "external_ref_required"}
  ]
}
```

---

## Step 6: Create `src/api/v1/endpoints/consent_withdraw.php`

Receives a consent withdrawal signal from an external system.

```
POST /api/v1/consent/withdraw
{
  "external_ref": "CUST-00042",
  "signal_type": "withdrawal",
  "category_hint": "Marketing Consent Records"
}
```

**Logic:**
1. Insert to `consent_signals` with `status = 'pending'`
2. Attempt to match to a `data_records` row:
   - `record_reference = external_ref`
   - `category.disposal_trigger = 'consent_withdrawal'`
3. If matched: set `consent_withdrawn_at = NOW()`, `retention_end_date = NOW()+30days`
   Set signal `status = 'processed'`, `record_id = matched record`
4. If not matched: set `status = 'unmatched'` — cron will retry
5. Log to audit_log: `consent_withdrawn`
6. Return 200

---

## Step 7: Create `src/api/v1/endpoints/health.php`

```
GET /api/v1/health
```

Returns system health for monitoring:
```json
{
  "status": "healthy",
  "tier": "enterprise",
  "timestamp": "2025-08-01T01:00:00+01:00",
  "queue_pending": 0,
  "queue_failed": 2,
  "last_cron_run": "2025-08-01T01:00:04+01:00",
  "connected_system": "Salesforce CRM",
  "api_version": "1.0"
}
```

---

## Step 8: Create `src/api/v1/endpoints/categories.php`

Returns available categories for the calling system (for field mapping UI):
```
GET /api/v1/categories
```
Returns JSON array of `{id, name, framework, disposal_trigger, retention_period_label}`.
Used by the external system's integration team when configuring field mappings.

---

## Step 9: Create `src/engine/intake_queue_processor.php`

CLI script added to cPanel cron (runs every 5 minutes):
```
*/5 * * * * /usr/local/bin/php /path/to/intake_queue_processor.php
```

**Logic:**
1. Fetch up to 100 `intake_queue` rows with `status = 'pending'`
2. For each row: run auto-categorisation, create `data_records` row
3. Mark queue row `status = 'completed'`, set `record_id`
4. Log `record_created` to audit_log with `details.source = 'enterprise_api'`
5. On error: increment `attempts`, set `status = 'failed'` if `attempts >= 3`
6. Log completion summary

---

## Security Rules
- API keys never logged in plaintext — only `key_prefix` for display
- `X-API-Key` header only — never in URL query params
- All inputs validated before touching DB
- `integration_logs` entries older than `api_log_retention_days` purged by cron
- `src/api/v1/` NOT blocked by `.htaccess` DirectoryMatch (unlike other includes)
  — it must be reachable. But it has its own auth layer.
