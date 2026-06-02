<?php
$pdo = get_pdo();
$stmt = $pdo->query(
    'SELECT iq.*, s.name AS system_name, dc.name AS category_name, dr.record_reference
     FROM intake_queue iq
     LEFT JOIN connected_systems s ON iq.system_id = s.id
     LEFT JOIN data_categories dc ON iq.category_id = dc.id
     LEFT JOIN data_records dr ON iq.record_id = dr.id
     ORDER BY iq.created_at DESC
     LIMIT 200'
);
$queueItems = $stmt->fetchAll();
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Intake queue</h1>
    <p class="text-muted mb-0">Monitor asynchronous ingestion requests and categorisation outcomes.</p>
  </div>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if (empty($queueItems)): ?>
      <p class="text-muted">No intake queue items are available.</p>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-hover align-middle">
          <thead>
            <tr>
              <th>Created</th>
              <th>System</th>
              <th>Batch</th>
              <th>Status</th>
              <th>Category</th>
              <th>Record</th>
              <th>Attempts</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($queueItems as $item): ?>
            <tr>
              <td><?= escape_html($item['created_at']) ?></td>
              <td><?= escape_html($item['system_name'] ?? 'Unknown') ?></td>
              <td><?= escape_html($item['batch_id'] ?? '—') ?></td>
              <td><?= escape_html($item['status']) ?></td>
              <td><?= escape_html($item['category_name'] ?? '—') ?></td>
              <td><?= escape_html($item['record_reference'] ?? '—') ?></td>
              <td><?= escape_html($item['attempts']) ?></td>
              <td><small class="text-danger"><?= escape_html($item['error'] ?? '—') ?></small></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>