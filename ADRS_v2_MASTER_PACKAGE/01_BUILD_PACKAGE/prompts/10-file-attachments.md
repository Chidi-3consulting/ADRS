# Prompt 10 — File Attachments Module (S8)

## Context
Attach documents to data records. Files stored OUTSIDE public_html.
Served via a PHP proxy. Max 10MB. Allowed: pdf, doc, docx, xls, xlsx, jpg, jpeg, png.
Reference: `attachments` table in schema.sql.

---

## Upload path configuration
- **Production:** `/home/username/retention_uploads/{record_id}/`
- **Local (Windows):** `C:\laragon\retention_uploads\{record_id}\`
- Defined in config as `UPLOAD_PATH` constant
- Directory created on first upload per record if not exists: `mkdir($dir, 0750, true)`
- Stored filename: UUID-based — `bin2hex(random_bytes(16)) . '.' . $ext`
  (No original filename on disk — prevents path traversal and overwrites)

---

## `src/pages/attachments/upload.php` (POST handler)

**Validation chain (fail fast — check all before moving file):**
1. Record exists and user has access (role check)
2. Record is not disposed (`status != 'disposed'`) — block uploads on disposed records
3. `$_FILES['file']['error'] === UPLOAD_ERR_OK`
4. File size ≤ `attachment_max_size_mb * 1024 * 1024`
5. Extension in allowed list (from system_settings)
6. MIME type double-check with `mime_content_type()` — do NOT trust browser-sent type
7. CSRF verified

**On pass:**
- Generate UUID stored_filename
- `move_uploaded_file()` to `UPLOAD_PATH/{record_id}/{uuid}.{ext}`
- Insert to `attachments` table
- Log `attachment_uploaded` to audit_log
- Return JSON: `{success: true, attachment_id, filename, size}`
  (Upload is triggered via fetch() from the record view page — no page reload)

**Security hardening:**
- Reject PHP/phtml/phar extensions even if not in disallowed list
- Reject files where `mime_content_type()` returns `text/x-php` or `application/x-php`
- Show disclaimer: "Note: Files are not virus-scanned. Only upload trusted documents."

---

## `src/pages/attachments/download.php` (GET handler)

```php
// ?id={attachment_id}
// 1. Verify authenticated
// 2. Fetch attachment row by ID
// 3. Verify user has access to parent record (role + category ownership)
// 4. Build full file path from UPLOAD_PATH + record_id + stored_filename
// 5. Verify file exists on disk (path traversal check: realpath must start with UPLOAD_PATH)
// 6. Set headers:
//    Content-Type: {mime_type from DB}
//    Content-Disposition: attachment; filename="{original_filename}"
//    Content-Length: {file_size}
//    X-Content-Type-Options: nosniff
// 7. readfile($full_path)
// 8. exit()
```

**Never expose the stored UUID filename to the browser** — always use `original_filename` in Content-Disposition.

---

## `src/pages/attachments/delete.php` (POST handler)

- Admin/DPO only
- Soft delete: set `deleted_at = NOW()` in DB
- Do NOT delete file from disk immediately (evidence preservation for disposed records)
  → Optional: add a cron task that hard-deletes files older than 30 days after soft-delete
- Log `attachment_deleted` to audit_log with `{original_filename, record_id}`
- Return JSON: `{success: true}`

---

## UI Component: Attachment Panel on Record View

Add to `src/pages/schedule/view.php`:

```html
<!-- Attachment Panel -->
<div class="card mt-4">
  <div class="card-header card-header-teal">
    <i class="bi bi-paperclip"></i> Attachments
    <span class="badge bg-secondary">{count}</span>
  </div>
  <div class="card-body">

    <!-- Upload zone (hidden for Data Owner on disposed records) -->
    <div class="attachment-drop-zone" id="dropZone">
      <i class="bi bi-cloud-upload fs-2"></i>
      <p>Drag & drop files here or <label for="fileInput" class="text-orange fw-bold" style="cursor:pointer">browse</label></p>
      <input type="file" id="fileInput" hidden multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png">
      <small class="text-muted">Max 10MB per file. PDF, Word, Excel, Images.</small>
    </div>

    <!-- Upload progress bar (shown during upload) -->
    <div id="uploadProgress" class="d-none mt-2">
      <div class="progress"><div class="progress-bar bg-warning" id="progressBar"></div></div>
    </div>

    <!-- Existing attachments list -->
    <table class="table table-sm mt-3" id="attachmentsTable">
      <thead>
        <tr><th>Filename</th><th>Size</th><th>Uploaded By</th><th>Date</th><th></th></tr>
      </thead>
      <tbody>
        <!-- PHP loop: foreach attachments WHERE deleted_at IS NULL -->
      </tbody>
    </table>

    <p class="text-muted small">
      <i class="bi bi-shield-exclamation"></i>
      Files are not virus-scanned. Only upload documents from trusted sources.
    </p>
  </div>
</div>
```

**JavaScript for drag-and-drop upload:**
- Listen for `dragover`, `drop` on `#dropZone`
- Also handle `#fileInput` change event
- For each file: POST to `attachments/upload.php` via `fetch()` with `FormData`
- Show `#uploadProgress` with real progress via `XMLHttpRequest.upload.onprogress`
- On success: append new row to `#attachmentsTable` without page reload
- On error: show Bootstrap toast with error message
- CSRF token included in fetch headers: `X-CSRF-Token: {token}`

---

## Additional: `src/pages/attachments/api/get_csrf.php`
Returns current CSRF token as JSON for the JS upload handler:
```php
<?php
session_name(SESSION_NAME); session_start();
require_once ...auth.php;
require_login();
header('Content-Type: application/json');
echo json_encode(['token' => $_SESSION['csrf_token'] ?? csrf_token()]);
```
