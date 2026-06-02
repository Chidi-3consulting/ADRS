<?php
$pdo = get_pdo();
$stmt = $pdo->query(
    'SELECT dr.*, dc.name AS category_name, dc.disposal_method
     FROM data_records dr
     LEFT JOIN data_categories dc ON dr.category_id = dc.id
     WHERE dr.deleted_at IS NULL
     ORDER BY dr.created_at DESC
     LIMIT 200'
);
$records = $stmt->fetchAll();
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Records</h1>
    <p class="text-muted mb-0">Track intake, retention schedules and disposal status.</p>
  </div>
  <a href="/retention/records/create" class="btn btn-primary">New record</a>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if (empty($records)): ?>
      <p class="text-muted">No records have been created yet.</p>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-hover align-middle">
          <thead>
            <tr>
              <th>Reference</th>
              <th>Category</th>
              <th>Status</th>
              <th>Collection</th>
              <th>Retention end</th>
              <th>Disposal</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($records as $record): ?>
            <tr>
              <td><?= escape_html($record['record_reference']) ?></td>
              <td><?= escape_html($record['category_name'] ?? 'Unknown') ?></td>
              <td><?= escape_html($record['status']) ?></td>
              <td><?= escape_html($record['collection_date']) ?></td>
              <td><?= escape_html($record['retention_end_date'] ?? '—') ?></td>
              <td><?= escape_html($record['disposal_method'] ?? '—') ?></td>
              <td><a href="/retention/records/view?id=<?= escape_html($record['id']) ?>" class="btn btn-sm btn-outline-primary">View</a></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
