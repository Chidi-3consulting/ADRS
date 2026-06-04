<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_role('admin', 'dpo');
$pdo = get_db();
$attachments = $pdo->query(
    "SELECT a.*, u.name AS uploader_name, dr.record_reference
     FROM attachments a
     LEFT JOIN users u ON a.uploaded_by = u.id
     LEFT JOIN data_records dr ON a.record_id = dr.id
     WHERE a.deleted_at IS NULL ORDER BY a.created_at DESC LIMIT 200"
)->fetchAll();
$page_title = 'Attachments';
$active_nav = '';
require __DIR__ . '/../../includes/layout_header.php';
?>
<h1 class="h4 mb-3">Attachments</h1>
<p class="text-muted">Evidence files linked to records. Files are stored outside the web root; download is access-controlled.</p>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($attachments)): ?><p class="text-muted mb-0">No attachments uploaded yet. Use a record's page to attach files.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Filename</th><th>Record</th><th>Uploader</th><th>Size</th><th>Uploaded</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($attachments as $a): ?>
      <tr>
        <td><?= escape_html($a['original_filename']) ?></td>
        <td><?= escape_html($a['record_reference'] ?? '—') ?></td>
        <td><?= escape_html($a['uploader_name'] ?? 'System') ?></td>
        <td><?= escape_html(number_format((int)$a['file_size'])) ?> bytes</td>
        <td class="small"><?= escape_html(format_datetime($a['created_at'])) ?></td>
        <td><a href="<?= APP_URL ?>/attachments/download?id=<?= (int)$a['id'] ?>" class="btn btn-sm btn-outline-primary">Download</a></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
