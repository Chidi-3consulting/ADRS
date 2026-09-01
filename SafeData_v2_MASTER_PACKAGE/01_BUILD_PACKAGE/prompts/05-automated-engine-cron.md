# Prompt 05 — Automated Retention Engine v3 (All Decisions Applied)


> **Implementation Note:** This specification was originally written with PHP code examples.
> The SafeData codebase has been fully implemented in **Python (FastAPI + SQLAlchemy + Jinja2)**.
> The business logic, rules, and requirements documented below remain the authoritative
> specification. See `retention_py/` for the Python implementation.

---
## Context
CLI-only script. Runs via cPanel Cron (production) or Windows Task Scheduler (local).
Refer to `.github/copilot-instructions.md` for all business rules before writing code.

---

## Cron Schedule (document in file header)
```
# Production (cPanel) — Daily 01:00 AM Lagos time
0 1 * * * /usr/local/bin/php /home/username/public_html/retention/src/engine/retention_cron.php >> /home/username/logs/retention_cron.log 2>&1

# Quarterly review — 1st Jan/Apr/Jul/Oct 08:00 AM
0 8 1 1,4,7,10 * /usr/local/bin/php /home/username/public_html/retention/src/engine/retention_cron.php --task=quarterly_review >> /home/username/logs/quarterly_review.log 2>&1

# Local testing (run manually in terminal):
# php src/engine/retention_cron.php
# php src/engine/retention_cron.php --task=quarterly_review
```

---

## Bootstrap (top of file)

```php
if (php_sapi_name() !== 'cli') {
    http_response_code(403); exit('Access denied.');
}

set_time_limit(0);
ini_set('memory_limit', '128M');

require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/db.php';
require_once __DIR__ . '/../../includes/helpers.php';
require_once __DIR__ . '/../../includes/mailer.php';

date_default_timezone_set(TIMEZONE);
$pdo = get_db(); // includes SET time_zone = '+01:00'

$task = 'daily';
foreach ($argv as $arg) {
    if (str_starts_with($arg, '--task=')) {
        $task = substr($arg, 7);
    }
}

$start_time = microtime(true);
$log_file   = LOG_PATH . 'retention_cron.log';

function cron_log(string $message): void {
    global $log_file;
    $line = '[' . date('Y-m-d H:i:s') . '] ' . $message . PHP_EOL;
    file_put_contents($log_file, $line, FILE_APPEND);
    echo $line;
}

function cron_error(string $message, Throwable $e): void {
    global $log_file;
    $error_log = LOG_PATH . 'cron_errors.log';
    $line = '[' . date('Y-m-d H:i:s') . '] ERROR: ' . $message . ' | ' . $e->getMessage() . PHP_EOL;
    $line .= $e->getTraceAsString() . PHP_EOL;
    file_put_contents($error_log, $line, FILE_APPEND);
    cron_log('ERROR: ' . $message . ' — see cron_errors.log');
}
```

---

## Daily Job Steps

### Step 1: Bootstrap confirmation
```
cron_log('=== 3Consulting Retention Engine START === Task: ' . $task);
cron_log('Step 1: Bootstrap OK. TZ: Africa/Lagos. Review window: ' . $review_alert_days . ' days. Escalation: ' . $escalation_days . ' days.');
```
Read settings from DB: `review_alert_days`, `escalation_days`, `consent_disposal_days`.

---

### Step 2: Flag date-based records for review
**Query** — only `date_based` categories (B1 decision):
```sql
SELECT dr.id, dr.record_reference, dr.category_id, dr.retention_end_date
FROM data_records dr
JOIN data_categories dc ON dc.id = dr.category_id
   AND dc.deleted_at IS NULL          -- D5: exclude soft-deleted categories
   AND dc.disposal_trigger = 'date_based'   -- B1: skip consent_withdrawal
WHERE dr.status = 'active'
  AND dr.legal_hold = 0
  AND dr.deleted_at IS NULL
  AND dr.retention_end_date <= DATE_ADD(CURDATE(), INTERVAL ? DAY)
```

For each record:
- `UPDATE data_records SET status='due_review', review_flagged_at=NOW() WHERE id=?`
- `log_audit(... 'record_flagged_review' ...)`
- Queue notification (batch by owner — not one email per record)

---

### Step 3: Process consent-based disposal (B1)
**Query** — `consent_withdrawal` categories where withdrawal was 30+ days ago:
```sql
SELECT dr.id, dr.record_reference, dr.category_id, dc.disposal_method
FROM data_records dr
JOIN data_categories dc ON dc.id = dr.category_id
   AND dc.deleted_at IS NULL
   AND dc.disposal_trigger = 'consent_withdrawal'
WHERE dr.consent_withdrawn_at IS NOT NULL
  AND dr.status != 'disposed'
  AND dr.legal_hold = 0
  AND dr.deleted_at IS NULL
  AND dr.consent_withdrawn_at <= DATE_SUB(NOW(), INTERVAL ? DAY)
```
- Execute disposal per category's `disposal_method`
- Use the `execute_disposal()` function below

---

### Step 4: Auto-dispose overdue date-based records
**Query:**
```sql
SELECT dr.id, dr.record_reference, dr.category_id, dc.disposal_method, dc.requires_dual_approval
FROM data_records dr
JOIN data_categories dc ON dc.id = dr.category_id
   AND dc.deleted_at IS NULL
   AND dc.disposal_trigger = 'date_based'
WHERE dr.status = 'due_review'
  AND dr.legal_hold = 0
  AND dr.deleted_at IS NULL
  AND dr.retention_end_date < CURDATE()
```

**CRITICAL DUAL APPROVAL CHECK (B5):**
```php
if ($record['requires_dual_approval']) {
    // Do NOT auto-dispose — skip and flag for manual action
    cron_log("  SKIP (dual approval required): record #{$record['id']}");
    continue;
}
```
- Only auto-dispose `requires_dual_approval = 0` records
- Call `execute_disposal($pdo, $record)`

---

### Step 5: 14-Day Escalation (B7)
**Query:**
```sql
SELECT dr.id, dr.record_reference, dr.review_flagged_at, dc.name AS category_name
FROM data_records dr
JOIN data_categories dc ON dc.id = dr.category_id AND dc.deleted_at IS NULL
WHERE dr.status = 'due_review'
  AND dr.legal_hold = 0
  AND dr.escalation_sent_at IS NULL
  AND dr.review_flagged_at <= DATE_SUB(NOW(), INTERVAL ? DAY)
```
For each batch:
- Set `escalation_sent_at = NOW()` on each record
- Send ONE summary email to ALL Admin users listing all escalated records
- Email subject: `🚨 ESCALATION: {N} records overdue for review ({escalation_days}+ days unactioned)`
- Log `escalation_sent` to audit_log

---

### Step 6: DSAR deadline alerts (C1)
```sql
-- Due in 5 days
SELECT * FROM dsar_requests
WHERE status NOT IN ('completed','rejected')
  AND due_date = DATE_ADD(CURDATE(), INTERVAL 5 DAY)

-- Overdue today
SELECT * FROM dsar_requests
WHERE status NOT IN ('completed','rejected')
  AND due_date < CURDATE()
  AND (extended_due_date IS NULL OR extended_due_date < CURDATE())
```
- Send alert to `assigned_to` user + all DPOs
- Log `notification_sent` to audit_log

---

### Step 7: Send batched notifications
Group review notifications by owner (N1 fallback to DPOs if owner_id IS NULL):
```php
// Build map: user_id => [array of records]
$owner_records = [];
foreach ($flagged_records as $record) {
    $owner_id = get_category_owner($pdo, $record['category_id']);
    if (!$owner_id) {
        // N1: no owner — notify all DPOs
        foreach (get_all_dpos($pdo) as $dpo) {
            $owner_records[$dpo['id']][] = array_merge($record, ['owner_missing' => true]);
        }
    } else {
        $owner_records[$owner_id][] = $record;
    }
}
// Send one email per user, not one per record
foreach ($owner_records as $user_id => $records) {
    send_review_batch_notification($pdo, $user_id, $records);
}
```

---

### Step 8: Retry failed notifications (last 48h, max 3 attempts)
```sql
SELECT * FROM notifications
WHERE status IN ('failed','pending')
  AND attempts < 3
  AND created_at >= DATE_SUB(NOW(), INTERVAL 48 HOUR)
```
Re-send, update status and attempts count.

---

### Step 9: Completion log
```
cron_log('Step 2: Flagged N records for review.');
cron_log('Step 3: Consent disposal: N records.');
cron_log('Step 4: Auto-disposed N records (delete:X, anonymise:Y, archive:Z). Skipped M (dual approval).');
cron_log('Step 5: Escalated N records to Admin.');
cron_log('Step 6: DSAR alerts: N sent.');
cron_log('Step 7: Notifications sent: N. Failed: M.');
cron_log('Step 8: Retried N pending notifications.');
$duration = round(microtime(true) - $start_time, 2);
cron_log("=== Engine COMPLETE. Duration: {$duration}s ===");
```
If any errors occurred: send summary error email to all Admins.

---

## `execute_disposal()` function
```php
function execute_disposal(PDO $pdo, array $record): bool {
    // 1. Re-verify legal hold (race condition guard)
    // 2. Re-verify not already disposed (idempotency guard — D1)
    // 3. Use DB transaction: UPDATE record + INSERT audit_log atomically
    // 4. Switch on disposal_method:
    //    'delete'    → set status='disposed', disposed_at, deleted_at
    //    'anonymise' → NULL out PII fields, set status='disposed'
    //    'archive'   → set status='disposed', keep all data
    // 5. Queue disposal_confirmation notification to DPO
    // 6. Return true on success, false on exception
}
```

## Quarterly review task
- Fetch all Admin + DPO users
- Build summary: total categories, overdue-for-review categories (no review in 90+ days),
  disposals this quarter by method, records on legal hold, DSAR stats
- Send `email_quarterly_review()` template to all
- Log `notification_sent` with type `quarterly_review`

---

## ENTERPRISE ADDITIONS TO DAILY CRON

When `safedata_tier = 'enterprise'`, add these steps AFTER the standard 9 steps:

### Enterprise Step A: Process intake_queue

Check if `intake_queue_processor.php` runs separately on its own cron.
If NOT (e.g. during local dev when only one cron exists), process pending queue items:

```php
if (get_setting($pdo, 'safedata_tier') === 'enterprise' &&
    get_setting($pdo, 'intake_queue_enabled') === '1') {

    $pending = $pdo->query(
        "SELECT * FROM intake_queue WHERE status = 'pending' AND attempts < 3 LIMIT 100"
    )->fetchAll();

    $processed = 0;
    foreach ($pending as $item) {
        try {
            process_intake_item($pdo, $item);
            $processed++;
        } catch (Exception $e) {
            $pdo->prepare("UPDATE intake_queue SET status='failed', attempts=attempts+1 WHERE id=?")
                ->execute([$item['id']]);
        }
    }
    cron_log("Enterprise Step A: Processed {$processed} intake queue items.");
}
```

### Enterprise Step B: Retry unmatched consent signals

```php
if (get_setting($pdo, 'consent_signal_enabled') === '1') {
    // Find signals from last 7 days that haven't been matched yet
    $unmatched = $pdo->query(
        "SELECT cs.* FROM consent_signals cs
         WHERE cs.status = 'unmatched'
           AND cs.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
    )->fetchAll();

    foreach ($unmatched as $signal) {
        $record = $pdo->prepare(
            "SELECT dr.id FROM data_records dr
             JOIN data_categories dc ON dc.id = dr.category_id
             WHERE dr.record_reference = ?
               AND dc.disposal_trigger = 'consent_withdrawal'
               AND dr.deleted_at IS NULL LIMIT 1"
        );
        $record->execute([$signal['external_ref']]);
        $matched = $record->fetch();

        if ($matched) {
            // Apply withdrawal
            $pdo->prepare("UPDATE data_records
                SET consent_withdrawn_at = NOW(),
                    retention_end_date = DATE_ADD(NOW(), INTERVAL ? DAY)
                WHERE id = ?")
                ->execute([(int)get_setting($pdo,'consent_disposal_days',30), $matched['id']]);

            $pdo->prepare("UPDATE consent_signals SET status='processed', record_id=?, processed_at=NOW() WHERE id=?")
                ->execute([$matched['id'], $signal['id']]);

            log_audit($pdo,'consent_withdrawn','data_record',$matched['id'],null,
                ['source'=>'enterprise_signal','external_ref'=>$signal['external_ref']],null);
        }
    }
    cron_log("Enterprise Step B: Retried unmatched consent signals.");
}
```

### Enterprise Step C: Purge old integration logs

```php
$retention_days = (int) get_setting($pdo, 'api_log_retention_days', '90');
$deleted = $pdo->prepare(
    "DELETE FROM integration_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL ? DAY)"
);
$deleted->execute([$retention_days]);
cron_log("Enterprise Step C: Purged " . $deleted->rowCount() . " integration log rows older than {$retention_days} days.");
```
