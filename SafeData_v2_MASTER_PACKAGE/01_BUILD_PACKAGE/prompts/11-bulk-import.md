# Prompt 11 — Bulk CSV Import Module (B8)


> **Implementation Note:** This specification was originally written with PHP code examples.
> The SafeData codebase has been fully implemented in **Python (FastAPI + SQLAlchemy + Jinja2)**.
> The business logic, rules, and requirements documented below remain the authoritative
> specification. See `retention_py/` for the Python implementation.

---
## Context
Two-pass validated CSV import for data records. Max 500 rows per upload.
Admin + DPO only. Reference: `import_jobs` table in schema.sql.

---

## CSV Template

### `src/pages/import/template.php` (GET — triggers download)
Sends a CSV file with headers + 3 example rows:

```
record_reference,category_name,data_subject_type,collection_date,notes
CONTRACT-2024-001,Customer Contracts & Agreements,Customer,2024-01-15,Annual service agreement
EMP-HR-0042,Employee Personnel Records,Employee,2023-06-01,
KYC-NG-0099,Customer KYC & Onboarding Data,Customer,2024-03-10,BVN verified
```

Rules (shown in comments at top of template file and on the UI):
- `record_reference`: required, max 255 chars
- `category_name`: must exactly match a category name in the system
- `data_subject_type`: optional free text
- `collection_date`: required, format YYYY-MM-DD, cannot be in the future
- `notes`: optional

---

## `src/pages/import/index.php`

**Layout:**
1. Page title: "Bulk Import Data Records"
2. Info panel: instructions + download template button + link to compliance library
3. Upload form:
   - File input (accept=".csv")
   - "Upload & Validate" button
4. After Pass 1: show validation preview (see below)
5. Import history table at bottom: last 10 `import_jobs` with status badges

---

## `src/pages/import/validate.php` (POST — Pass 1)

**Process:**
1. CSRF verify
2. Accept uploaded CSV file
3. Check file extension and MIME type (`text/csv` or `text/plain`)
4. Read with `fgetcsv()` — handle UTF-8 BOM if present
5. Check row count ≤ 500 (reject entire file immediately if exceeded)
6. Build category lookup map: `[name => id, retention_period_days, disposal_trigger]`
7. Validate every row:

| Field | Validation |
|---|---|
| record_reference | Required, max 255, not empty |
| category_name | Must exist in `data_categories` (active, not deleted) |
| collection_date | Required, valid date, not in future |
| data_subject_type | Optional, max 100 chars |
| notes | Optional, max 1000 chars |
| Duplicate | `record_reference` + `category_id` combo not already in `data_records` |

8. Build result arrays: `$valid_rows[]`, `$error_rows[]`
9. Store validated data in `$_SESSION['import_preview']` (serialised — cleared after import or abandon)
10. Insert `import_jobs` row with `status = 'validated'`
11. Render preview table (do NOT redirect — show on same page)

**Preview table:**
```
Row | Reference | Category | Subject Type | Collection Date | Ret. End Date | Status
 1  | CONTRACT-001 | Customer Contracts | Customer | 15 Jan 2024 | 15 Jan 2031 | ✅ Valid
 2  | EMP-HR-BAD | [Invalid Category] | - | - | - | ❌ Unknown category
 3  | EMP-HR-0042 | Employee Records | Employee | 01 Jun 2023 | 01 Jun 2029 | ⚠️ Duplicate
```

Show summary: "47 valid rows ready to import. 3 rows have errors and will be skipped."

Two buttons:
- ✅ **Confirm Import** (POST to `import.php`)
- ❌ **Cancel** (clears session preview, redirects to index)

---

## `src/pages/import/import.php` (POST — Pass 2)

1. CSRF verify
2. Load `$_SESSION['import_preview']` — abort if missing
3. Filter to only `$valid_rows`
4. Open DB transaction
5. For each valid row:
   - Insert to `data_records`:
     - `category_id` from lookup
     - `collection_date`
     - `retention_end_date` = `retention_end_date($collection_date, $category_days)`
     - `status = 'active'`
     - `created_by = current_user_id`
     - If category `disposal_trigger = 'consent_withdrawal'`: set `retention_end_date = NULL`
   - Log `record_created` to audit_log with `details = {source: 'bulk_import', job_id: X}`
6. Commit transaction
7. Update `import_jobs`: set `imported_rows`, `skipped_rows`, `error_rows`, `status = 'imported'`, `completed_at`
8. If error rows exist: generate error report CSV and offer download
9. Clear `$_SESSION['import_preview']`
10. Log single `bulk_import` to audit_log with summary
11. Notify all DPOs: "Bulk import complete: X records imported by [user]"
12. Flash: "Import complete. {N} records imported. {M} rows skipped — download error report."

---

## Error Report CSV Download
Filename: `import-errors-{job_id}-{date}.csv`
Columns: `row_number, record_reference, category_name, collection_date, error_reason`
Offered as a download link on the success page and in `import_jobs` history table.

---

## Import Job History Table (on index.php)
| Date | Filename | Total | Imported | Skipped | Errors | Status | Error Report |
- Status badges: pending/validated=info, imported=success, failed=danger
- "Download Error Report" link if `error_rows > 0`
