# Prompt 12 — Advanced Features: Settings, Recalculations Queue & System Tools

## Context
These are the "gap-closing" pages identified in the pre-build review.
All reference `.github/copilot-instructions.md` for base rules.

---

## A. System Settings Page (P1)

### `src/pages/settings/index.php` — Admin only

Editable settings panel for all `system_settings` rows.
Grouped into sections:

**Section 1: Application**
- App Name, App URL, Timezone (select from PHP timezone list)

**Section 2: Retention Engine**
- Review Alert Days (number, 1–90)
- Escalation Days — B7 (number, 1–30)
- Consent Disposal Days — B1 (number, 1–90)

**Section 3: Email / SMTP**
- SMTP Host, Port, Username, Password (masked input), From Name, From Email
- "Send Test Email" button → POST to `settings/test_email.php`
  → sends a test to the logged-in Admin's email
  → shows inline success/failure without page reload

**Section 4: File Attachments — S8**
- Max File Size (MB)
- Allowed File Types (comma-separated input)

**Section 5: DSAR — C1**
- DSAR Response Days (default 30)
- DSAR Extension Days (default 60)

**Section 6: Import — B8**
- Max Import Rows (default 500)

**Section 7: Display**
- Rows Per Page (select: 10 / 25 / 50 / 100)

On save:
- Loop `$_POST` settings, validate types/ranges per key
- UPDATE `system_settings` for each changed value
- Log `user_updated` to audit_log with entity_type='system', details=changed keys
- Flash: "Settings saved."

---

## B. Recalculations Queue (B2)

### `src/pages/recalculations/index.php` — Admin + DPO

Shown when a DPO has edited a category's retention period and `pending_recalculations` rows exist.

**Banner:** "⏳ {N} records require your review after a retention period change."
Shown in sidebar as badge on "Recalculations" nav item.

**Table columns:**
| Record Ref | Category | Old End Date | New End Date | Difference | Decision | Action |

- Difference: "+730 days" (green) or "-365 days" (red)
- Decision: dropdown per row — "Recalculate" / "Keep Original"
- "Save All Decisions" button (bulk POST)
- Alternatively: "Recalculate All" and "Keep All Original" bulk buttons

**On save:**
- For each row with `decision = 'recalculate'`:
  - UPDATE `data_records.retention_end_date` to new date
  - Set `pending_recalculations.status = 'recalculate'`, `reviewed_by`, `reviewed_at`
  - Log `recalculation_reviewed` to audit_log
- For `keep_original`:
  - Set `pending_recalculations.status = 'keep_original'`
  - Log `recalculation_reviewed`
- Flash: "Reviewed {N} recalculations."
- Sidebar badge disappears when queue is empty

---

## C. Consent Withdrawal UI (B1)

### `src/pages/schedule/consent_withdraw.php` (POST handler)

Triggered from record view page for consent_withdrawal category records.
Button only shown on records where:
- `dc.disposal_trigger = 'consent_withdrawal'`
- `dr.consent_withdrawn_at IS NULL`
- User is Admin or DPO

**Modal (rendered on view.php):**
```html
<div class="modal" id="consentWithdrawModal">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header bg-warning">
        <h5>Log Consent Withdrawal</h5>
      </div>
      <div class="modal-body">
        <p>This will begin the 30-day disposal countdown for <strong>{record_reference}</strong>.</p>
        <p><strong>Category:</strong> {category_name}</p>
        <p><strong>Disposal method:</strong> {disposal_method} (executed automatically after 30 days)</p>
        <p><strong>Retention end date will be set to:</strong> {today + 30 days}</p>
        <label>Withdrawal reason (optional):</label>
        <textarea name="withdrawal_reason" class="form-control"></textarea>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button type="submit" class="btn btn-warning">Confirm Withdrawal</button>
      </div>
    </div>
  </div>
</div>
```

**On confirm:**
- Set `consent_withdrawn_at = NOW()`, `consent_withdrawn_by = current_user_id`
- Calculate `retention_end_date = date('Y-m-d', strtotime('+30 days'))`
- Append withdrawal reason to `notes`
- Log `consent_withdrawn` to audit_log
- Notify DPOs
- Flash: "Consent withdrawal logged. Record will be automatically disposed on {date}."

---

## D. DB Backup Export (Advanced Admin Tool)

### `src/pages/settings/backup.php` — Admin only

Generates a SQL dump using PHP (no shell_exec — InMotion shared hosting restriction).

**Pure PHP mysqldump approach:**
```php
// Fetch all table names
// For each table: SELECT * and generate INSERT statements
// Stream as .sql file download
// Filename: backup-{date}-{time}.sql
```

Tables to include: all except `audit_log` over 1 year old (too large — offer separate export).
Maximum: 50,000 rows total before suggesting phpMyAdmin instead.

Show warning: "For large databases, use phpMyAdmin's Export feature for a complete backup."
Log `export_generated` to audit_log.

---

## E. In-app Help Page

### `src/pages/help.php` — All roles

Static reference page. Bootstrap accordion sections:

**Section 1: How the Retention Lifecycle Works**
- Visual of the 5 stages (re-use the CSS timeline from dashboard)
- Explanation of each stage

**Section 2: Role Guide**
- What each role can and cannot do (table from copilot-instructions.md)

**Section 3: Data Category Basics**
- What is a legal basis?
- What is a disposal method?
- What is a retention period?
- When should I use GDPR vs NDPR vs Both?

**Section 4: Understanding the Cron Engine**
- What it does daily
- How to check if it's running (cron health indicator)
- What to do if it hasn't run

**Section 5: DSAR Quick Reference**
- What is a DSAR?
- 30-day response requirement
- How to use the DSAR module

**Section 6: Frequently Asked Questions**
- "Why can't I delete an audit log entry?"
- "What happens when I edit a category's retention period?"
- "What is dual approval and which categories need it?"
- "Can I undo a disposal?"
- "What does Legal Hold do?"

---

## F. Notification Bell Dropdown (N2 — JavaScript)

Add to `layout_header.php` topbar:

```html
<div class="dropdown" id="notificationBell">
  <button class="btn btn-link text-white position-relative" data-bs-toggle="dropdown">
    <i class="bi bi-bell-fill fs-5"></i>
    <?php if ($unread_count > 0): ?>
      <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger">
        <?= min($unread_count, 99) ?><?= $unread_count > 99 ? '+' : '' ?>
      </span>
    <?php endif; ?>
  </button>
  <div class="dropdown-menu dropdown-menu-end notification-dropdown p-0" style="width:380px">
    <div class="d-flex justify-content-between align-items-center p-3 border-bottom">
      <strong>Notifications</strong>
      <a href="#" id="markAllRead" class="small text-muted">Mark all read</a>
    </div>
    <div id="notificationList">
      <?php foreach ($recent_notifications as $n): ?>
      <a href="<?= get_notification_url($n) ?>" class="dropdown-item notification-item py-2 px-3 border-bottom
        <?= $n['read_at'] ? '' : 'bg-light fw-semibold' ?>"
        data-id="<?= $n['id'] ?>">
        <div class="d-flex gap-2">
          <span><?= get_notification_icon($n['type']) ?></span>
          <div>
            <div class="small"><?= sanitize($n['subject']) ?></div>
            <div class="text-muted" style="font-size:0.75rem"><?= relative_time($n['created_at']) ?></div>
          </div>
        </div>
      </a>
      <?php endforeach; ?>
    </div>
    <div class="p-2 text-center border-top">
      <a href="/notifications/" class="small">View all notifications</a>
    </div>
  </div>
</div>
```

**JS (in layout_footer.php):**
```javascript
// Mark individual notification read on click
document.querySelectorAll('.notification-item').forEach(item => {
  item.addEventListener('click', () => {
    fetch('/notifications/mark_read.php', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken},
      body: JSON.stringify({id: item.dataset.id})
    });
  });
});

// Mark all read
document.getElementById('markAllRead')?.addEventListener('click', e => {
  e.preventDefault();
  fetch('/notifications/mark_all_read.php', {
    method: 'POST',
    headers: {'X-CSRF-Token': csrfToken}
  }).then(() => window.location.reload());
});
```

### `src/pages/notifications/mark_read.php` (POST)
- Accept JSON body `{id: N}`
- UPDATE `notifications SET read_at = NOW() WHERE id = ? AND recipient_id = ?`
- Return `{success: true}`

### `src/pages/notifications/mark_all_read.php` (POST)
- UPDATE `notifications SET read_at = NOW() WHERE recipient_id = ? AND read_at IS NULL`
- Return `{success: true}`
