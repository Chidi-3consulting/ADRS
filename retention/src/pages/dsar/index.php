<?php
$pdo = get_pdo();
$stmt = $pdo->query('SELECT dr.* FROM dsar_requests dr ORDER BY dr.created_at DESC LIMIT 200');
$dsars = $stmt->fetchAll();
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">DSAR Requests</h1>
    <p class="text-muted mb-0">Manage right of access, rectification, erasure and other DSAR cases.</p>
  </div>
  <a href="/retention/dsar/create" class="btn btn-primary">New DSAR</a>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if (empty($dsars)): ?>
      <p class="text-muted">No DSAR requests have been logged yet.</p>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-striped table-hover">
          <thead>
            <tr>
              <th>Reference</th>
              <th>Type</th>
              <th>Subject</th>
              <th>Due date</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($dsars as $dsar): ?>
            <tr>
              <td><?= escape_html($dsar['reference']) ?></td>
              <td><?= escape_html($dsar['request_type']) ?></td>
              <td><?= escape_html($dsar['data_subject_name']) ?></td>
              <td><?= escape_html($dsar['due_date']) ?></td>
              <td><?= escape_html($dsar['status']) ?></td>
              <td><a href="/retention/dsar/view?id=<?= escape_html($dsar['id']) ?>" class="btn btn-sm btn-outline-primary">View</a></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
