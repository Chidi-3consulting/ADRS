<?php
$pdo = get_pdo();
$stmt = $pdo->query(
    'SELECT a.*, u.name AS uploader_name, dr.record_reference
     FROM attachments a
     LEFT JOIN users u ON a.uploaded_by = u.id
     LEFT JOIN data_records dr ON a.record_id = dr.id
     WHERE a.deleted_at IS NULL
     ORDER BY a.created_at DESC
     LIMIT 200'
);
$attachments = $stmt->fetchAll();
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Attachments</h1>
    <p class="text-muted mb-0">Manage record attachments and stored evidence files.</p>
  </div>
  <a href="/retention/attachments/upload" class="btn btn-primary">Upload attachment</a>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if (empty($attachments)): ?>
      <p class="text-muted">No attachments have been uploaded yet.</p>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-hover">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Record</th>
              <th>Uploader</th>
              <th>Size</th>
              <th>Uploaded</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($attachments as $attachment): ?>
            <tr>
              <td><?= escape_html($attachment['original_filename']) ?></td>
              <td><?= escape_html($attachment['record_reference'] ?? 'Unknown') ?></td>
              <td><?= escape_html($attachment['uploader_name'] ?? 'System') ?></td>
              <td><?= escape_html(number_format($attachment['file_size'])) ?> bytes</td>
              <td><?= escape_html($attachment['created_at']) ?></td>
              <td>
                <a href="/retention/attachments/download?id=<?= escape_html($attachment['id']) ?>" class="btn btn-sm btn-outline-primary">Download</a>
              </td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
