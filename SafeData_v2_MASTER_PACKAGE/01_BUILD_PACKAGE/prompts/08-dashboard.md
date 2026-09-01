# Prompt 08 — Dashboard v3 (All Decisions Applied)


> **Implementation Note:** This specification was originally written with PHP code examples.
> The SafeData codebase has been fully implemented in **Python (FastAPI + SQLAlchemy + Jinja2)**.
> The business logic, rules, and requirements documented below remain the authoritative
> specification. See `retention_py/` for the Python implementation.

---
## Context
Landing page after login. Role-aware. Fetches all data in ≤ 5 SQL queries.
Refer to `.github/copilot-instructions.md`.

---

## All Roles — KPI Row (6 cards, single optimised query)
```sql
SELECT
  SUM(CASE WHEN dr.status NOT IN ('disposed') THEN 1 ELSE 0 END)                              AS total_active,
  SUM(CASE WHEN dr.status = 'due_review' THEN 1 ELSE 0 END)                                   AS due_review,
  SUM(CASE WHEN dr.retention_end_date < CURDATE() AND dr.status != 'disposed' THEN 1 ELSE 0 END) AS overdue,
  SUM(CASE WHEN dr.legal_hold = 1 OR dr.status = 'legal_hold' THEN 1 ELSE 0 END)              AS on_hold,
  SUM(CASE WHEN dr.status = 'disposal_requested' THEN 1 ELSE 0 END)                           AS awaiting_approval,
  SUM(CASE WHEN dr.status = 'disposed' AND MONTH(dr.disposed_at) = MONTH(CURDATE())
           AND YEAR(dr.disposed_at) = YEAR(CURDATE()) THEN 1 ELSE 0 END)                       AS disposed_this_month
FROM data_records dr
JOIN data_categories dc ON dc.id = dr.category_id AND dc.deleted_at IS NULL
WHERE dr.deleted_at IS NULL
-- Data Owner filter: AND dc.owner_id = :user_id
```

**6 KPI cards:**
- 🟢 Active Records
- 🟡 Due for Review → links to `?status=due_review`
- 🔴 Overdue → links to `?status=overdue`
- 🔒 On Legal Hold → links to `?status=legal_hold`
- ⏳ Awaiting Dual Approval (B5) → links to `?status=disposal_requested`
- ✅ Disposed This Month

---

## Admin/DPO — Full Dashboard

### Row 1: Compliance Health + DSAR Summary
**Left (8 cols): Compliance Health Gauge**
- CSS conic-gradient circle: `health = (active - overdue) / active * 100`
- 90–100%: green "✅ Compliant", 70–89%: amber "⚠️ Needs Attention", <70%: red "🚨 Action Required"

**Right (4 cols): DSAR Quick Stats (C1)**
- Open DSARs, Due This Week, Overdue count
- "View DSARs" button

### Row 2: Framework Breakdown
Two cards side by side:
- **GDPR**: active records / overdue / categories
- **NDPR**: active records / overdue / categories

### Row 3: Records Needing Action (table — top 10)
Columns: Reference | Category | Status | Retention End | Days Remaining | Action
- Shows: due_review + disposal_requested + overdue records
- Disposal_requested rows show "🔐 Awaiting 2nd Approval" badge
- Quick action button per row

### Row 4: Consent-Based Records Pending Withdrawal (B1)
Only shown if any exist:
- Records where `disposal_trigger = 'consent_withdrawal'` and `consent_withdrawn_at IS NULL`
- Banner: "These records have no fixed retention end date. Disposal requires manual consent withdrawal."
- Table: Reference | Category | Collection Date | Action

### Row 5: Recalculations Pending (B2)
Only shown if `pending_recalculations` has rows with `status = 'pending'`:
- Amber banner: "⏳ {N} records are pending retention date review after a category change."
- "Review Now" button → `/recalculations/`

### Row 6: Retention Schedule by Category (horizontal CSS bar chart)
Pure CSS/JS — no Chart.js. Top 10 categories by active record count.
`[Category Name] [████████░░░░] Active: 12 | Disposed: 8`

### Row 7: Recent Audit Activity (last 10 entries)
Mini audit log table. "View Full Log" link.

### Row 8: Upcoming Quarterly Review alert
If within 30 days of 1 Jan/Apr/Jul/Oct:
- Info banner with countdown: "Quarterly review due in {N} days"

---

## Data Owner Dashboard

### My Categories (card grid)
- One card per owned category
- Shows: active count, due_review count, next review date
- Card border colour: red if overdue, amber if due_review, green if healthy
- Consent-based categories show: "Manual consent withdrawal required" tag

### Records Requiring Attention
- Due_review records in their categories
- Note: "Contact your DPO to action disposal of these records."

### Recent Activity
- Last 5 audit entries for their category records

---

## Quick Actions Panel (right sidebar — Admin/DPO)
Sticky:
- ➕ Add Record
- ➕ Add Category
- ⬆️ Bulk Import
- 📋 Schedule Review
- 📊 Export Audit Log
- 🔔 View All Notifications + unread count

---

## Performance rules
- ≤ 5 total SQL queries for full Admin dashboard
- ≤ 3 queries for Data Owner dashboard
- No N+1 loops — use JOINs and GROUP BY
- Add `EXPLAIN` comment above complex queries

## Welcome message
```php
$hour = (int) date('H');
$greeting = $hour < 12 ? 'Good morning' : ($hour < 17 ? 'Good afternoon' : 'Good evening');
echo "{$greeting}, {$user['name']}.";
```

## Cron health (footer — from layout_footer.php)
```sql
SELECT MAX(created_at) FROM audit_log
WHERE performed_by IS NULL AND action IN ('record_flagged_review','record_disposed_delete','record_disposed_anonymise','record_disposed_archive')
```
- If > 25 hours: `⚠️ Automated engine last run: {time} — check your cron job`
- Never run: `⚠️ Automated engine has never run — set up your cron job`
