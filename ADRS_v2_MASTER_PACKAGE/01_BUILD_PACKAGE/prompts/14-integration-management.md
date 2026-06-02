# Prompt 14 — Integration Management (Connected Systems, Field Mapping, Auto-Categorisation)
# ENTERPRISE TIER ONLY

## Context
This module is the admin control centre for all Enterprise integrations.
It lets Admins register connected systems, manage API keys, configure field mappings,
and define auto-categorisation rules. Data Owners and DPOs cannot access this module.
Refer to `.github/copilot-instructions.md`.

---

## Pages to build

### `src/pages/integrations/index.php` — Integration Dashboard
Access: Admin only. Show 403 + "Enterprise feature" if `adrs_tier != 'enterprise'`.

**Page header:** "Integration Management — Connected Systems"

**Summary cards (4):**
- Total Connected Systems
- Active API Keys
- Records Ingested Today (from integration_logs, today, inbound, status 200)
- Queue Items Pending (intake_queue status=pending)

**Connected Systems table:**
| System Name | Type | Status | Last Ping | Records Total | API Keys | Actions |
- Status badge: 🟢 Healthy / 🟡 Degraded / 🔴 Offline / ⬜ Unknown
- "Last Ping": relative time from `last_ping_at`
- Actions: Configure, View Logs, Ping Now, Disable

**"Add Connected System" button** → `create.php`

---

### `src/pages/integrations/create.php`
Admin only. Register a new external system.

**Fields:**
- System Name* (e.g. "Salesforce CRM Production")
- System Type* (select: CRM / Core Banking / HR Platform / Customer DB / Loan Management / eCommerce / Custom)
- Base URL (text — the webhook callback URL, for outbound dispatch)
- Description (textarea)

**On save:**
- Insert to `connected_systems`
- Redirect to `api_keys/create.php?system_id=X` with flash:
  "System registered. Now create an API key for it."

---

### `src/pages/integrations/api_keys/index.php`
List all API keys for a system.

**Table:** Key Name | Prefix | Permissions | Rate Limit | Last Used | Expires | Status | Actions
- Actions: Revoke (POST handler, sets revoked_at), Copy prefix only (never full key)
- Warning banner: "API keys are shown once at creation. If lost, create a new key."

---

### `src/pages/integrations/api_keys/create.php`
Admin only. Create a new API key for a connected system.

**Fields:**
- Key Name* (e.g. "Production Key")
- Permissions* (checkboxes): ingest / batch / consent / health / categories
- Rate Limit Per Minute (number, default 60)
- Expiry Date (date picker, optional)

**On save:**
```php
// Generate raw key — shown ONCE, then only hash stored
$raw_key = 'adrs_' . bin2hex(random_bytes(24)); // ~56 chars
$prefix  = substr($raw_key, 0, 12);
$hash    = hash('sha256', $raw_key);

// Insert to api_keys
$pdo->prepare("INSERT INTO api_keys (system_id, key_name, key_hash, key_prefix, permissions, rate_limit_per_min, expires_at, created_by)
               VALUES (?,?,?,?,?,?,?,?)")
    ->execute([$system_id, $name, $hash, $prefix, json_encode($permissions), $rate_limit, $expires_at, current_user()['id']]);

// Log to audit_log: user_updated (entity_type=system)
```

**Display raw key ONCE** — full-page alert:
```html
<div class="alert alert-warning border-warning">
  <h5>⚠️ Save this API key now — it will not be shown again</h5>
  <div class="api-key-display" style="font-family:monospace;font-size:1.1rem;background:#f8f9fa;padding:16px;border-radius:4px;">
    adrs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  </div>
  <button onclick="navigator.clipboard.writeText(this.dataset.key)" class="btn btn-sm btn-secondary mt-2">
    📋 Copy to clipboard
  </button>
  <p class="mt-3 small text-muted">
    Store this key in your connected system's environment variables.
    It begins with "adrs_" and is 56 characters long.
  </p>
</div>
```
After this page is navigated away from, the raw key is gone forever.

---

### `src/pages/integrations/field_mappings/index.php`
Admin only. Shows all field mappings for a selected connected system.

**Explanation banner:**
"Field mappings tell ADRS how to read data from [System Name]. When a record
arrives with object_type = 'customer', ADRS uses these mappings to extract
the record reference, data subject type, and collection date."

**Mappings table:**
| Object Type | External Field | ADRS Field | Required | Transform | Actions |

**Group by `external_object_type`** — collapsible sections per object type.

**"Add Mapping" button** → `create.php?system_id=X`

---

### `src/pages/integrations/field_mappings/create.php`
Admin only.

**Fields:**
- Object Type* (text — matches what external system sends as `object_type`)
- External Field* (text — field name in the external JSON payload)
- Maps To ADRS Field* (select):
  - record_reference ← the primary identifier
  - data_subject_type
  - collection_date
  - notes
  - [custom metadata field]
- Required (checkbox)
- Transform (optional — simple PHP expression: `strtoupper({value})`, `date('Y-m-d', strtotime({value}))`)

**Help text:** Show a live example based on the external field + transform entered.

---

### `src/pages/integrations/rules/index.php`
Auto-categorisation rules for a connected system.

**Explanation banner:**
"When ADRS receives a record from [System Name], it uses these rules to automatically
assign the correct data category. Rules are evaluated in priority order (lowest number = first).
The first matching rule wins."

**Rules table:**
| Priority | Rule Name | Object Type | Condition | → Category | Active | Actions |

**Example displayed:**
```
Priority 10 | "Rejected Loans"
  When: object_type = "loan_application" AND status = "rejected"
  → Assign: Recruitment & Application Data (6 months)

Priority 20 | "All Customers"  
  When: object_type = "customer"
  → Assign: Customer KYC & Onboarding Data (5 years)
```

**"Add Rule" button** → `create.php`

---

### `src/pages/integrations/rules/create.php`
Admin only. Build an auto-categorisation rule.

**Fields:**
- Rule Name* (text)
- Object Type* (text — must match `object_type` values sent by external system)
- Condition Field (text — optional, e.g. "status")
- Condition Value (text — optional, e.g. "rejected")
- Assign to Category* (select — all active categories, grouped by framework)
- Priority* (number, 1–100, default 10)
- Active (checkbox)

**On save:** Insert to `auto_categorization_rules`. Redirect to rules list.

**Visual rule preview:** As fields are filled, show a plain-English summary:
"When [System Name] sends an object_type of [X] where [field] = [value],
ADRS will assign it to [Category Name] ([retention_period_label] / [disposal_method])."

---

### `src/pages/integrations/logs/index.php`
Integration log viewer for a connected system.

**Filters:** Direction (All/Inbound/Outbound) | Status Code | Date range | Endpoint

**Table:**
| Timestamp | Direction | Endpoint | Status | Records | Duration | Error | Details |

- Status: colour-coded (2xx=green, 4xx=amber, 5xx=red, 429=purple)
- "Details" → Bootstrap modal showing full request + response JSON
- Auto-purge notice: "Logs older than [api_log_retention_days] days are automatically deleted."

**Export CSV** → filename: `integration-logs-[system]-[date].csv`

---

### `src/pages/integrations/queue/index.php`
Intake queue monitor.

**KPI cards:** Pending | Processing | Completed Today | Failed

**Table:**
| Queue ID | System | Batch ID | Object Type | Status | Attempts | Created | Actions |

- Failed rows: red background, "Retry" button
- Pending rows: show estimated processing time

**"Process Now" button** (Admin): Triggers `intake_queue_processor.php` via PHP CLI
```php
// Trigger via shell_exec if available, or set a flag for next cron run
$flag_file = LOG_PATH . 'process_queue_now.flag';
file_put_contents($flag_file, time());
flash('info', 'Queue processing will begin within 5 minutes.');
```
Alternatively: redirect to a page that processes the queue inline (sync mode).

---

### `src/pages/integrations/ping.php` (POST handler)
Pings a connected system's `base_url/health` endpoint.
Updates `connected_systems.health_status` and `last_ping_at`.
Returns JSON: `{status, response_time_ms, http_code}`.
Called via AJAX from integration dashboard.

---

## Integration Management in Sidebar Navigation

Add to `layout_header.php` (Admin only, Enterprise tier only):
```php
<?php if (has_role('admin') && get_setting($pdo, 'adrs_tier') === 'enterprise'): ?>
<li class="nav-item">
  <a class="nav-link <?= $active_nav === 'integrations' ? 'active' : '' ?>"
     href="<?= APP_URL ?>/src/pages/integrations/">
    <i class="bi bi-diagram-3"></i> Integrations
    <?php if ($queue_pending > 0): ?>
      <span class="badge bg-warning text-dark"><?= $queue_pending ?></span>
    <?php endif; ?>
  </a>
</li>
<?php endif; ?>
```
