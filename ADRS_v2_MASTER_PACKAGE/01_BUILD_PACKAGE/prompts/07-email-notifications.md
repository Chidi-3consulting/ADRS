# Prompt 07 — Email Notification System v3


> **Implementation Note:** This specification was originally written with PHP code examples.
> The ADRS codebase has been fully implemented in **Python (FastAPI + SQLAlchemy + Jinja2)**.
> The business logic, rules, and requirements documented below remain the authoritative
> specification. See `retention_py/` for the Python implementation.

---
## Context
PHPMailer — 3 files manually included (no Composer). Mailpit on local.
All SMTP config from `database.php` constants (not the DB settings table).
N1 fallback and N2 bell integration applied.

---

## `src/includes/mailer.php`

```php
function send_notification(string $to_email, string $to_name, string $subject, string $html_body, ?string $plain_body = null): bool
```

Config from constants:
```php
$mail->Host       = SMTP_HOST;
$mail->Port       = SMTP_PORT;
$mail->From       = SMTP_FROM_EMAIL;
$mail->FromName   = SMTP_FROM_NAME;
$mail->SMTPDebug  = SMTP_DEBUG;

// Handle local Mailpit (no auth, no encryption)
if (!empty(SMTP_USER)) {
    $mail->SMTPAuth   = true;
    $mail->Username   = SMTP_USER;
    $mail->Password   = SMTP_PASS;
}
if (!empty(SMTP_ENCRYPTION)) {
    $mail->SMTPSecure = SMTP_ENCRYPTION;
}
```

On exception: log to `LOG_PATH . 'mail_errors.log'`, return false — never throw.

---

## `src/includes/email_templates.php`

Master layout: 600px table, inline CSS only.
Brand: header `#1A6187` (teal), CTA button `#C85C1A` (orange), body `#F7F7F7`.

```php
function email_layout(string $title, string $content, string $footer_note = ''): string
```
Footer always includes:
- "Automated message from 3Consulting Data Retention System"
- `https://retention.3consult-ng.com`
- "This is an internal system notification. If you believe you received this in error, contact your system administrator."
(No unsubscribe link — this is an internal compliance tool, not marketing)

---

### Template functions (implement all in full):

**`email_review_due(array $records, string $recipient_name, bool $owner_missing = false): string`**
- Subject: "Action Required: {N} Data Record(s) Due for Review"
- N1: if `$owner_missing = true` — show amber box:
  "⚠️ Note: The following category has no assigned Data Owner. Please assign one in the Data Category Register."
- Table of records: Reference | Category | Retention End | Days Remaining
- CTA: "Review Records Now"

**`email_disposal_confirmation(string $reference, string $category, string $method, string $disposed_at, string $performed_by, bool $automated = false): string`**
- Subject: "Disposal Confirmed: {reference}"
- `$automated = true` → show "🤖 Automated by retention engine" as performed_by

**`email_legal_hold_set(string $reference, string $category, string $reason, string $set_by, string $set_at): string`**
- Subject: "🔒 Legal Hold Applied: {reference}"

**`email_legal_hold_lifted(string $reference, string $category, string $lifted_at, string $new_status): string`**
- Subject: "🔓 Legal Hold Lifted: {reference}"

**`email_disposal_requested(string $reference, string $category, string $requested_by, string $requested_at, string $approve_url): string`**
- Subject: "⏳ Dual Approval Required: Disposal of {reference}"
- B5: Explains that a second approver is needed
- CTA: "Review and Approve Disposal"
- Note: "You cannot approve this if you are the same person who requested it."

**`email_disposal_rejected(string $reference, string $category, string $rejected_by, string $reason): string`**
- Subject: "❌ Disposal Request Rejected: {reference}"

**`email_quarterly_review(array $summary, string $dashboard_url, int $year, int $quarter): string`**
- Subject: "Quarterly Retention Review — Q{quarter} {year} — Action Required"
- Summary stats table (see Prompt 08 dashboard for fields)
- GDPR Art. 5 + NDPR compliance reminder

**`email_welcome_user(string $name, string $email, string $temp_password, string $role, string $login_url): string`**
- Subject: "Welcome to 3Consulting Data Retention System"
- Role explanation, credentials box, "change password on first login" warning

**`email_escalation_alert(array $records, int $days, string $dashboard_url): string`**
- Subject: "🚨 ESCALATION: {N} Records Overdue for Review — {days}+ Days Unactioned"
- B7: Red alert header, list of unactioned records
- CTA: "Review Now"

**`email_consent_withdrawal_disposal_due(string $reference, string $category, string $withdrawal_date, string $disposal_date): string`**
- Subject: "⏰ Consent-Based Disposal Due: {reference}"
- B1: Reminder that consent was withdrawn and disposal is imminent

**`email_recalculation_pending(string $category_name, int $count, string $queue_url): string`**
- Subject: "⏳ {N} Records Pending Retention Date Review — {category_name}"
- B2: Explains that DPO needs to review recalculations queue

**`email_bulk_import_complete(int $imported, int $skipped, string $imported_by, string $download_url): string`**
- Subject: "✅ Bulk Import Complete: {imported} Records Imported"
- B8: Summary, error report download link if skipped > 0

**`email_record_created_by_owner(string $reference, string $category, string $owner_name, string $collection_date, string $record_url): string`**
- Subject: "📋 New Record Added by Data Owner: {reference}"
- B4: DPO awareness notification

**`email_password_reset(string $name, string $reset_url, int $expires_minutes = 60): string`**
- Subject: "Password Reset Request — 3Consulting DRS"
- S1: Time-limited reset link, security notice

**DSAR templates (C1):**
- `email_dsar_received(...)` — see Prompt 09
- `email_dsar_due_soon(...)` — see Prompt 09
- `email_dsar_overdue(...)` — see Prompt 09

---

## `src/pages/notifications/index.php`
Two tabs: Sent | Failed/Pending.

**Sent table:** Sent At | Type | Recipient | Subject | Related Record | Owner Missing | Status
- `owner_missing = 1` rows: show amber "No Owner" badge (N1)

**Failed/Pending table:** + Attempts column + Retry button

---

## Notification helper functions (add to `helpers.php`)

```php
/**
 * Insert notification record to DB + send immediately
 * N1: if owner_id is NULL, automatically sends to all DPOs with owner_missing=1
 */
function notify_user(PDO $pdo, int $recipient_id, string $type, string $subject,
    string $message, ?int $record_id = null, ?int $dsar_id = null,
    bool $owner_missing = false): void

/**
 * Notify all users with given role(s)
 */
function notify_role(PDO $pdo, array $roles, string $type, string $subject, string $message, ...): void

/**
 * N1: Notify category owner, or all DPOs if no owner
 * Returns true if owner existed, false if fell back to DPOs
 */
function notify_category_owner_or_dpos(PDO $pdo, int $category_id, string $type, string $subject, string $html_body, ?int $record_id = null): bool
```
