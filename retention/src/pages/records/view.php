<?php
$pdo = get_pdo();
$id = (int)($_GET['id'] ?? 0);

if ($id <= 0) {
    http_response_code(404);
    echo 'Record not found.';
    exit;
}

$stmt = $pdo->prepare(
    'SELECT dr.*, dc.name AS category_name, dc.disposal_method, dc.disposal_trigger,
            u.name AS created_by_name
     FROM data_records dr
     LEFT JOIN data_categories dc ON dr.category_id = dc.id
     LEFT JOIN users u ON dr.created_by = u.id
     WHERE dr.id = :id AND dr.deleted_at IS NULL'
);
$stmt->execute(['id' => $id]);
$record = $stmt->fetch();

if (!$record) {
    http_response_code(404);
    echo 'Record not found.';
    exit;
}

$attachmentsStmt = $pdo->prepare('SELECT * FROM attachments WHERE record_id = :id AND deleted_at IS NULL ORDER BY created_at DESC');
$attachmentsStmt->execute(['id' => $id]);
$attachments = $attachmentsStmt->fetchAll();
$attachmentCount = count($attachments);
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Record details</h1>
    <p class="text-muted mb-0">Reference <?= escape_html($record['record_reference']) ?> — category <?= escape_html($record['category_name'] ?? 'Unknown') ?></p>
  </div>
  <div>
    <a href="/retention/records/edit?id=<?= escape_html($record['id']) ?>" class="btn btn-outline-primary me-2">Edit record</a>
    <a href="/retention/records" class="btn btn-secondary">Back to records</a>
  </div>
</div>
<div class="row">
  <div class="col-lg-8">
    <div class="card shadow-sm mb-3">
      <div class="card-body">
        <h5 class="card-title">Core details</h5>
        <dl class="row">
          <dt class="col-sm-4">Reference</dt>
          <dd class="col-sm-8"><?= escape_html($record['record_reference']) ?></dd>

          <dt class="col-sm-4">Category</dt>
          <dd class="col-sm-8"><?= escape_html($record['category_name'] ?? 'Unknown') ?></dd>

          <dt class="col-sm-4">Status</dt>
          <dd class="col-sm-8"><?= escape_html($record['status']) ?></dd>

          <dt class="col-sm-4">Collection date</dt>
          <dd class="col-sm-8"><?= escape_html($record['collection_date']) ?></dd>

          <dt class="col-sm-4">Retention end</dt>
          <dd class="col-sm-8"><?= escape_html($record['retention_end_date'] ?? 'N/A') ?></dd>

          <dt class="col-sm-4">Disposal method</dt>
          <dd class="col-sm-8"><?= escape_html($record['disposal_method']) ?></dd>

          <dt class="col-sm-4">Disposal trigger</dt>
          <dd class="col-sm-8"><?= escape_html($record['disposal_trigger']) ?></dd>

          <dt class="col-sm-4">Created by</dt>
          <dd class="col-sm-8"><?= escape_html($record['created_by_name'] ?? 'System') ?></dd>
        </dl>
      </div>
    </div>
  </div>
  <div class="col-lg-4">
    <div class="card shadow-sm mb-3">
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-start mb-3">
          <div>
            <h5 class="card-title">Attachments</h5>
            <p class="text-muted mb-0">Files linked to this record</p>
          </div>
          <a href="/retention/attachments/upload?record_id=<?= escape_html($record['id']) ?>" class="btn btn-sm btn-primary">Upload file</a>
        </div>
        <p class="display-6 mb-1"><?= escape_html($attachmentCount) ?></p>
        <?php if (!empty($attachments)): ?>
        <div class="list-group list-group-flush">
          <?php foreach ($attachments as $attachment): ?>
          <div class="list-group-item d-flex justify-content-between align-items-center">
            <div>
              <strong><?= escape_html($attachment['original_filename']) ?></strong>
              <div class="small text-muted"><?= escape_html(number_format($attachment['file_size'])) ?> bytes · <?= escape_html($attachment['created_at']) ?></div>
            </div>
            <a href="/retention/attachments/download?id=<?= escape_html($attachment['id']) ?>" class="btn btn-sm btn-outline-primary">Download</a>
          </div>
          <?php endforeach; ?>
        </div>
        <?php endif; ?>
      </div>
    </div>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
