<?php
$pdo = get_pdo();
$records = $pdo->query('SELECT id, record_reference FROM data_records WHERE deleted_at IS NULL ORDER BY record_reference')->fetchAll();
$selectedRecordId = (int)($_GET['record_id'] ?? 0);
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $selectedRecordId = (int)($_POST['record_id'] ?? $selectedRecordId);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validate_csrf($_POST['csrf_token'] ?? '')) {
        $error = 'Invalid CSRF token.';
    } elseif (empty($_FILES['attachment_file']) || $_FILES['attachment_file']['error'] !== UPLOAD_ERR_OK) {
        $error = 'Please choose a file to upload.';
    } else {
        $recordId = (int)($_POST['record_id'] ?? 0);
        $file = $_FILES['attachment_file'];
        $originalFilename = trim($file['name']);
        $extension = strtolower(pathinfo($originalFilename, PATHINFO_EXTENSION));
        $mimeType = $file['type'] ?: 'application/octet-stream';
        $fileSize = (int)$file['size'];
        $uploadDir = attachment_storage_path();

        if ($recordId <= 0) {
            $error = 'Please select a record for this attachment.';
        } elseif (!in_array($extension, attachment_allowed_extensions(), true)) {
            $error = 'Unsupported file type. Allowed: ' . implode(', ', attachment_allowed_extensions()) . '.';
        } elseif ($fileSize > attachment_max_size_bytes()) {
            $error = 'File is too large. Maximum size is ' . (attachment_max_size_bytes() / 1024 / 1024) . ' MB.';
        } else {
            $storedFilename = bin2hex(random_bytes(16)) . '.' . $extension;
            $destination = $uploadDir . DIRECTORY_SEPARATOR . $storedFilename;

            if (!move_uploaded_file($file['tmp_name'], $destination)) {
                $error = 'Unable to save uploaded file.';
            } else {
                $uploaderId = current_user()['id'] ?? null;
                $stmt = $pdo->prepare(
                    'INSERT INTO attachments (record_id, original_filename, stored_filename, file_size, mime_type, uploaded_by, created_at)
                     VALUES (:record_id, :original_filename, :stored_filename, :file_size, :mime_type, :uploaded_by, CURRENT_TIMESTAMP)'
                );
                $stmt->execute([
                    'record_id' => $recordId,
                    'original_filename' => $originalFilename,
                    'stored_filename' => $storedFilename,
                    'file_size' => $fileSize,
                    'mime_type' => $mimeType,
                    'uploaded_by' => $uploaderId,
                ]);

                flash_set('success', 'Attachment uploaded successfully.');
                if (!empty($_POST['return_to_record'])) {
                    redirect('/retention/records/view?id=' . $recordId);
                }
                redirect('/retention/attachments');
            }
        }
    }
}
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="card shadow-sm">
  <div class="card-body">
    <h1 class="h4 mb-3">Upload Attachment</h1>
    <?php if ($error): ?>
      <div class="alert alert-danger"><?= escape_html($error) ?></div>
    <?php endif; ?>
    <form method="post" enctype="multipart/form-data">
      <input type="hidden" name="csrf_token" value="<?= escape_html(csrf_token()) ?>">
      <div class="mb-3">
        <label class="form-label">Record</label>
        <select name="record_id" class="form-select" required>
          <option value="">Select a record</option>
          <?php foreach ($records as $record): ?>
            <option value="<?= escape_html($record['id']) ?>" <?= $selectedRecordId === (int)$record['id'] ? 'selected' : '' ?>><?= escape_html($record['record_reference']) ?></option>
          <?php endforeach; ?>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">File</label>
        <input type="file" name="attachment_file" class="form-control" required accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png">
      </div>
      <div class="mb-3 text-muted">
        Allowed types: <?= escape_html(implode(', ', attachment_allowed_extensions())) ?>. Maximum size: <?= escape_html(attachment_max_size_bytes() / 1024 / 1024) ?> MB.
      </div>
      <input type="hidden" name="return_to_record" value="<?= escape_html($selectedRecordId ? '1' : '') ?>">
      <button class="btn btn-primary">Upload attachment</button>
      <a href="/retention/attachments" class="btn btn-secondary ms-2">Cancel</a>
    </form>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>