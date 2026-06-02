# Prompt 03 — Data Category Register v3 (All Decisions Applied)

## Context
Refer to `.github/copilot-instructions.md`. Decisions B1, B2, B5 directly affect this module.
Foundation (Prompt 01) and Auth (Prompt 02) are complete.

---

## Key decisions affecting this module
- **B1:** Categories have a `disposal_trigger` field — `date_based` or `consent_withdrawal`
- **B2:** Editing retention period triggers `pending_recalculations` queue, NOT immediate updates
- **B5:** Categories have `requires_dual_approval` flag for sensitive categories

---

## `src/pages/categories/index.php`
Access: Admin + DPO (all), Data Owner (own categories only).

**Stats row (5 cards):**
Total | GDPR | NDPR | Dual Approval | Due for Review This Quarter

**Filter bar:** Name search | Framework | Legal Basis | Disposal Trigger | Disposal Method | Status

**Table columns:**
| # | Name | Framework | Legal Basis | Retention | Trigger | Disposal | Owner | Dual Approval | Status | Actions |

- **Disposal Trigger badge:** date_based=blue "📅 Date", consent_withdrawal=purple "👤 Consent"
- **Dual Approval badge:** `requires_dual_approval=1` → orange "🔐 Dual" badge (B5)
- **Seeded rows:** show 📚 icon

**Seeded library banner:**
"This register includes 30 pre-built GDPR and NDPR categories. Seeded entries show 📚 and can be customised."

---

## `src/pages/categories/create.php`
Access: Admin + DPO.

**Form fields:**
- Name*, Description
- Framework* (GDPR / NDPR / Both)
- Legal Basis*
- Disposal Trigger* (B1):
  - "📅 Date-based — dispose after fixed retention period"
  - "👤 Consent withdrawal — dispose 30 days after consent is withdrawn"
  - Selecting "Consent withdrawal" HIDES the retention period fields and shows:
    "Retention end date will be set when consent is withdrawn."
- Retention Period* (number + unit — hidden if consent_withdrawal)
- Human-readable Label (auto-populated, editable — hidden if consent_withdrawal)
- Disposal Method*
- Requires Dual Approval (B5): checkbox "🔐 Require two-person approval for disposal"
  - Show info tooltip: "Enable for sensitive data (health, biometric, children's). Two different Admin/DPO users must approve disposal."
- Data Owner (select from data_owner users)
- Review Frequency*
- Status

**JavaScript:** toggle retention period section visibility based on disposal_trigger select

On save: insert, log `category_created`, flash success.

---

## `src/pages/categories/edit.php`
Access: Admin + DPO.

**B2 — Retention period change detection:**
On POST, before saving:
```php
if ($new_retention_days !== $old_retention_days) {
    // Count affected active/due_review records
    $affected = count_active_records_for_category($pdo, $category_id);
    if ($affected > 0) {
        // Show confirmation modal BEFORE saving:
        // "Changing the retention period will affect {N} existing records.
        //  They will be added to the DPO Recalculations Queue for review.
        //  No record dates will change until you review and confirm them."
        // Buttons: "Proceed and Queue for Review" / "Cancel"
        // On confirm: save category, INSERT to pending_recalculations for each affected record
        // Send notification to all DPOs
    }
}
```
- Store `old_retention_days` in hidden field for comparison
- `pending_recalculations` rows: status='pending', old_date, new_date, triggered_by

Show "Seeded from library" notice if `source = 'seeded'`.
Show read-only Created / Last Modified timestamps.
If owner changes: notify new owner via email.

---

## `src/pages/categories/view.php`
Read-only for all roles. Shows all fields plus:
- Active Records count
- Due for Review count
- On Legal Hold count
- **Consent-based records without withdrawal** (B1): count where consent_withdrawn_at IS NULL
- Dual approval indicator (B5)
- Last 5 audit entries for this category
- "View All Records" button

---

## `src/pages/categories/delete.php`
POST handler. Admin only.
- Block if active non-disposed records exist
- Soft-delete
- Log `category_deleted`

---

## Updated seed file: `sql/seed_gdpr_ndpr.sql`
Apply B1 and B5 to seeded categories:

```sql
-- B1: Marketing Consent → consent_withdrawal trigger, retention_period_days = 0
UPDATE data_categories SET disposal_trigger = 'consent_withdrawal', retention_period_days = 0
WHERE name = 'Marketing Consent Records';

UPDATE data_categories SET disposal_trigger = 'consent_withdrawal', retention_period_days = 0
WHERE name = 'Biometric Data';

UPDATE data_categories SET disposal_trigger = 'consent_withdrawal', retention_period_days = 0
WHERE name = "Children's Data (Under 13/18)";

UPDATE data_categories SET disposal_trigger = 'consent_withdrawal', retention_period_days = 0
WHERE name = 'Consent Records (NDPR)';

-- B5: Sensitive categories → dual approval required
UPDATE data_categories SET requires_dual_approval = 1
WHERE name IN (
  'Health & Medical Records (Employees)',
  'Biometric Data',
  "Children's Data (Under 13/18)",
  'Health Data (Employees — Nigeria)'
);
```
