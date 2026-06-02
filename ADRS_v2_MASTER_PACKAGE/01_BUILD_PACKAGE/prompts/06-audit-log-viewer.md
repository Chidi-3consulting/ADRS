# Prompt 06 — Audit Log Viewer

## Context
Refer to `.github/copilot-instructions.md`. The `audit_log` table is append-only and is populated by all previous modules.

---

## Task: Build the Audit Log Viewer — the immutable evidence trail

This module is critical for GDPR and NDPR compliance. The audit log is the system's tamper-evident record of every action. It must NEVER allow edits or deletions.

---

### 1. Create `src/pages/audit/index.php`

Access: Admin + DPO only. Data Owners are explicitly BLOCKED.

**Compliance banner at top:**
> "This audit log is an immutable record of all system activity. It cannot be edited or deleted. It supports your obligations under GDPR Article 5(2) (accountability principle) and NDPR Article 4.1 (record-keeping requirement)."

**Filter panel:**
- Date range: From / To (default: last 30 days)
- Action type (multi-select dropdown with all enum values, human-readable labels)
- Entity type (All / Data Record / Category / User / System)
- Performed by (select from users + "System / Automated")
- Search by Entity ID or details keyword

**Summary tiles above the table:**
- Total log entries (all time)
- Actions today
- System-automated actions (this month)
- Exports generated (this month)

**Table columns:**
| Timestamp | Action | Entity Type | Entity ID | Performed By | IP Address | Details |

- **Timestamp**: format `d M Y H:i:s` — never truncate
- **Action**: human-readable label with colour-coded icon:
  - 🔴 Disposal actions (delete/anonymise/archive)
  - 🔒 Legal hold set/lifted
  - ✅ Review/schedule actions
  - 👤 User actions
  - ⚙️ System actions
- **Performed By**: User name + role badge, or "🤖 Automated (Cron)" for NULL
- **IP Address**: show partial mask for privacy if needed (`192.168.x.x`)
- **Details**: truncated JSON with "View Full" link that opens a Bootstrap modal showing formatted JSON

**Table behaviour:**
- Newest entries first (ORDER BY `created_at` DESC)
- Pagination: 50 rows per page (audit logs are read-heavy)
- No edit or delete buttons — none. Not even for Admin.
- Row hover highlight only (no clickable rows)

---

### 2. Create `src/pages/audit/export.php`

CSV export for compliance reporting. Access: Admin + DPO only.

**Two export types (shown as two buttons on `index.php`):**

**A) Filtered Export:**
- Exports whatever the current filter shows
- CSV includes all columns including full `details` JSON
- Filename: `audit-log-[from]-to-[to]-[timestamp].csv`
- Log `export_generated` to audit_log (note: this creates a log entry in the log itself — this is correct and intentional)

**B) Annual NDPR Compliance Export:**
- Dedicated button: "Export Annual NDPR Report (CSV)"
- Prompts for Year (select: current and previous 5 years)
- Exports only disposal actions, legal holds, and schedule reviews for that calendar year
- Adds a header row: "3Consulting Data Retention Audit — NDPR Annual Report — [Year]"
- Useful for NITDA submission
- Filename: `ndpr-annual-audit-[year].csv`

**Both exports must:**
- Use PHP `fputcsv()` for proper CSV escaping
- Set `Content-Type: text/csv; charset=utf-8`
- Set `Content-Disposition: attachment; filename="[name].csv"`
- Add UTF-8 BOM (`\xEF\xBB\xBF`) at start of file for Excel compatibility
- Log the export to audit_log

---

### 3. Action Labels Mapping

Create a function `get_audit_action_label($action)` in `helpers.php`:

```
record_created              → "Data Record Created"
record_updated              → "Data Record Updated"
record_flagged_review       → "Record Flagged for Review"
record_disposed_delete      → "Record Disposed — Deleted"
record_disposed_anonymise   → "Record Disposed — Anonymised"
record_disposed_archive     → "Record Disposed — Archived"
legal_hold_set              → "Legal Hold Applied"
legal_hold_lifted           → "Legal Hold Lifted"
category_created            → "Data Category Created"
category_updated            → "Data Category Updated"
category_deleted            → "Data Category Deleted"
user_created                → "User Account Created"
user_updated                → "User Account Updated"
user_deleted                → "User Account Deleted"
notification_sent           → "Notification Sent"
schedule_reviewed           → "Retention Schedule Reviewed"
user_login                  → "User Login"
user_logout                 → "User Logout"
export_generated            → "Audit Log Exported"
```

---

### 4. Audit Log Integrity Notice

On the `index.php` page, add a footer note:
> "Audit log integrity is maintained at the database level. The `audit_log` table has no UPDATE or DELETE privileges granted to the application database user. All entries are permanent."

This is aspirational — also add a comment in the schema instructions file telling the developer to run:
```sql
-- Restrict application DB user from modifying audit_log
REVOKE UPDATE, DELETE ON data_retention.audit_log FROM 'app_user'@'localhost';
```

---

## UI Requirements
- The audit log page must feel "serious" and compliance-focused
- Dark teal (`--3c-teal`) header card for the log table
- Monospace font for the details JSON in the modal (`font-family: monospace`)
- Print stylesheet: when printing the page, hide sidebar, filters, and export buttons — show only the table with all rows
- Add "🖨️ Print View" button that triggers `window.print()`
