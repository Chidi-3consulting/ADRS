# Prompt 04 — Retention Schedule Manager v4 (BUG-05 FIXED)
# BUG-05 FIX: api/get_category.php endpoint defined here

> **Implementation Note:** This specification was originally written with PHP code examples.
> The SafeData codebase has been fully implemented in **Python (FastAPI + SQLAlchemy + Jinja2)**.
> The business logic, rules, and requirements documented below remain the authoritative
> specification. See `retention_py/` for the Python implementation.

---

## Context
Decisions B1, B3, B4, B5 apply. Refer to copilot-instructions.md.
Prompts 01–03 complete. system_settings SMTP reads from DB via get_setting().

---

## FIRST: Create `src/api/get_category.php` (BUG-05 FIX)

This was referenced in create.php JS but never defined. Build it first.

```php
<?php
// src/api/get_category.php
// Purpose: AJAX endpoint for live retention date preview in schedule/create.php
// Auth: must be logged in (any role)
// Returns: JSON with category retention data

require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';

session_name(SESSION_NAME);
session_start();
require_login(); // 401 if not authenticated

header('Content-Type: application/json');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

$id = filter_input(INPUT_GET, 'id', FILTER_VALIDATE_INT);
if (!$id || $id < 1) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid category ID']);
    exit;
}

$pdo = get_db();

// If Data Owner: only allow their own categories
$where_extra = '';
$params = [$id];
if (has_role('data_owner')) {
    $where_extra = ' AND owner_id = ?';
    $params[] = current_user()['id'];
}

$stmt = $pdo->prepare(
    "SELECT id, name, retention_period_days, retention_period_label,
            disposal_trigger, disposal_method, requires_dual_approval,
            legal_basis, compliance_framework
     FROM data_categories
     WHERE id = ? AND is_active = 1 AND deleted_at IS NULL" . $where_extra
);
$stmt->execute($params);
$category = $stmt->fetch();

if (!$category) {
    http_response_code(404);
    echo json_encode(['error' => 'Category not found or access denied']);
    exit;
}

echo json_encode($category);
```

Add `src/api/` directory to `.htaccess` EXCEPTION — this directory
must NOT be blocked since it serves authenticated AJAX. The block rule
covers direct file access, but API responses via index routing are fine.
Actually: the `.htaccess` blocks `api/` directory listing but allows
`src/api/get_category.php` to execute via direct PHP since it enforces
its own auth. Remove `api` from the DirectoryMatch block list.

---

## `src/pages/schedule/index.php`

**KPI row (6 cards — single optimised query):**
```sql
SELECT
  SUM(CASE WHEN status NOT IN ('disposed') THEN 1 ELSE 0 END) AS total_active,
  SUM(CASE WHEN status = 'due_review' THEN 1 ELSE 0 END) AS due_review,
  SUM(CASE WHEN retention_end_date < CURDATE() AND status != 'disposed' THEN 1 ELSE 0 END) AS overdue,
  SUM(CASE WHEN legal_hold = 1 OR status = 'legal_hold' THEN 1 ELSE 0 END) AS on_hold,
  SUM(CASE WHEN status = 'disposal_requested' THEN 1 ELSE 0 END) AS awaiting_approval,
  SUM(CASE WHEN status = 'disposed' AND MONTH(disposed_at)=MONTH(CURDATE())
           AND YEAR(disposed_at)=YEAR(CURDATE()) THEN 1 ELSE 0 END) AS disposed_this_month
FROM data_records dr
JOIN data_categories dc ON dc.id = dr.category_id AND dc.deleted_at IS NULL
WHERE dr.deleted_at IS NULL
/* Data Owner: AND dc.owner_id = :uid */
```

**Filters:** Reference search | Category (grouped by framework) | Status
(All/Active/Due Review/Overdue/On Hold/Awaiting Approval/Disposed) |
Framework | Collection Date range | Retention End Date range

**Table columns:**
`Ref | Category | Trigger | Collection | Ret. End | Days Left | Status | Created By | Actions`

- Trigger badge: 📅 Date-Based (blue) | 👤 Consent (purple)
- `created_by_owner=1` → 👤 tooltip "Added by Data Owner"
- `disposal_requested` → orange "⏳ Awaiting 2nd Approval"
- Consent records with no withdrawal → "—" in Ret End + "⏳ Pending withdrawal"
- Legal hold → 🔒 icon, no countdown

**Bulk actions** (Admin/DPO): checkbox + "Mark for Review" / "Dispose Selected"

---

## `src/pages/schedule/create.php`

Access: Admin + DPO + Data Owner (own categories — B4).

**B4 guardrails:**
```php
if (has_role('data_owner')) {
    $category_filter = "AND dc.owner_id = " . current_user()['id'];
    // Force collection_date to today in hidden field
    // Show notice: "As a Data Owner, you can register records in your assigned
    //               categories. Your DPO will be notified automatically."
}
```

**Form fields:**
- Record Reference* (text, max 255)
- Data Category* (select — filtered for Data Owner)
  - If Data Owner: grouped by framework, only their categories
  - If Admin/DPO: all active categories, grouped
- Data Subject Type (text)
- Collection Date* (Data Owner: `<input type="hidden">` = today; Admin/DPO: date picker)
- Notes (textarea)

**Live retention date preview (BUG-05 FIX — uses api/get_category.php):**
```html
<div id="retentionPreview" class="alert alert-info d-none">
  Retention end date: <strong id="calcDate"></strong>
  (<span id="calcLabel"></span>)
  <span id="consentNotice" class="d-none text-warning">
    ⚠️ This is a consent-based category. No fixed end date until consent is withdrawn.
  </span>
</div>
```

```javascript
document.getElementById('category_id').addEventListener('change', async function() {
    const id = this.value;
    if (!id) return;

    const res = await fetch(`${APP_URL}/src/api/get_category.php?id=${id}`, {
        headers: { 'X-CSRF-Token': document.querySelector('[name=csrf_token]').value }
    });
    const cat = await res.json();
    if (cat.error) return;

    const preview = document.getElementById('retentionPreview');
    const calcDate = document.getElementById('calcDate');
    const consentNotice = document.getElementById('consentNotice');

    preview.classList.remove('d-none');

    if (cat.disposal_trigger === 'consent_withdrawal') {
        calcDate.textContent = 'Not set';
        consentNotice.classList.remove('d-none');
    } else {
        consentNotice.classList.add('d-none');
        const collectionDate = document.getElementById('collection_date').value || new Date().toISOString().split('T')[0];
        const endDate = new Date(collectionDate);
        endDate.setDate(endDate.getDate() + parseInt(cat.retention_period_days));
        calcDate.textContent = endDate.toLocaleDateString('en-GB', {day:'2-digit',month:'short',year:'numeric'});
        document.getElementById('calcLabel').textContent = cat.retention_period_label;
    }

    // Show dual approval warning
    if (cat.requires_dual_approval) {
        document.getElementById('dualApprovalWarning').classList.remove('d-none');
    }
});
// Also trigger on collection_date change
document.getElementById('collection_date')?.addEventListener('change', () => {
    document.getElementById('category_id').dispatchEvent(new Event('change'));
});
```

**On POST (server-side — never trust JS dates):**
```php
csrf_verify();
$category_id    = (int)$_POST['category_id'];
$record_ref     = sanitize($_POST['record_reference']);
$subject_type   = sanitize($_POST['data_subject_type'] ?? '');
$collection_date = has_role('data_owner') ? date('Y-m-d') : sanitize($_POST['collection_date']);
$notes          = sanitize($_POST['notes'] ?? '');

// Fetch category to calculate end date server-side
$cat = fetch_category($pdo, $category_id);

// B4: Data Owner can only use their own categories
if (has_role('data_owner') && $cat['owner_id'] != current_user()['id']) {
    flash('error', 'You can only create records in your assigned categories.');
    redirect(...);
}

// Calculate retention end date (D4: fixed days, server-side only)
$retention_end = null;
if ($cat['disposal_trigger'] === 'date_based' && $cat['retention_period_days'] > 0) {
    $retention_end = retention_end_date($collection_date, $cat['retention_period_days']);
}
// consent_withdrawal: retention_end stays NULL

$created_by_owner = has_role('data_owner') ? 1 : 0;

// Insert
$stmt = $pdo->prepare("INSERT INTO data_records
    (category_id, record_reference, data_subject_type, collection_date,
     retention_end_date, status, created_by_owner, created_by, notes)
    VALUES (?,?,?,?,?,'active',?,?,?)");
$stmt->execute([$category_id,$record_ref,$subject_type,$collection_date,
                $retention_end,$created_by_owner,current_user()['id'],$notes]);
$record_id = $pdo->lastInsertId();

log_audit($pdo,'record_created','data_record',$record_id,current_user()['id'],
    ['category'=>$cat['name'],'collection_date'=>$collection_date,'created_by_owner'=>$created_by_owner],
    get_client_ip());

// B4: notify DPOs if created by Data Owner
if ($created_by_owner) {
    notify_role($pdo,['admin','dpo'],'record_created_by_owner',
        'New Record Added by Data Owner: '.$record_ref,
        email_record_created_by_owner($record_ref,$cat['name'],current_user()['name'],$collection_date,APP_URL.'/src/pages/schedule/view.php?id='.$record_id),
        $record_id);
}

flash('success', "Record '{$record_ref}' created." . ($retention_end ? " Retention end date: " . format_date($retention_end) : " Disposal will be triggered by consent withdrawal."));
redirect(APP_URL.'/src/pages/schedule/index.php');
```

---

## `src/pages/schedule/view.php`
Full record detail. Timeline visualisation (CSS/JS). Consent withdrawal panel (B1).
Dual approval panel (B5). Legal hold panel. Attachments panel (S8 — Prompt 10).
Category reassignment (B3). Audit history.

---

## `src/pages/schedule/dispose.php`
B5 two-step disposal: see copilot-instructions.md for full logic.
Key checks before any disposal:
1. `legal_hold = 0` (block if set)
2. `status != 'disposed'` (idempotency guard)
3. `requires_dual_approval` check (step 1 vs step 2 flow)
4. Same-user block for step 2

---

## `src/pages/schedule/reassign.php` (POST — B3)
- Validate Admin/DPO role
- Fetch new category
- If new category shorter period: require `confirmed_shorter_period=1` in POST
- Store `original_category_id` (only on first reassignment)
- Log `record_reassigned` with full before/after JSON
- Update `retention_end_date` per user's choice (recalculate/keep)

---

## `src/pages/schedule/export.php`
CSV export. UTF-8 BOM. Includes: all filter params, `consent_withdrawn_at` column,
`disposal_trigger` column, `requires_dual_approval` column. Log `export_generated`.

---

## JavaScript — `APP_URL` global variable
Add to `layout_footer.php` (so all pages can use it in JS):
```html
<script>
  const APP_URL = '<?= APP_URL ?>';
  const csrfToken = '<?= csrf_token() ?>';
</script>
```
This makes `APP_URL` and `csrfToken` available to all inline JS,
including the `get_category.php` AJAX call.
