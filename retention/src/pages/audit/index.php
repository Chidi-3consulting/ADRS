<?php
$pdo = get_pdo();
$stmt = $pdo->query('SELECT al.*, u.name AS performed_by_name FROM audit_log al LEFT JOIN users u ON al.performed_by = u.id ORDER BY al.created_at DESC LIMIT 100');
$auditRows = $stmt->fetchAll();
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Audit Log</h1>
    <p class="text-muted mb-0">Immutable event history for retention actions and compliance evidence.</p>
  </div>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if (empty($auditRows)): ?>
      <p class="text-muted">Audit log is empty.</p>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-hover align-middle">
          <thead>
            <tr>
              <th>When</th>
              <th>Action</th>
              <th>Entity</th>
              <th>Performed by</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($auditRows as $row): ?>
            <tr>
              <td><?= escape_html($row['created_at']) ?></td>
              <td><?= escape_html($row['action']) ?></td>
              <td><?= escape_html($row['entity_type']) ?> #<?= escape_html($row['entity_id'] ?? '—') ?></td>
              <td><?= escape_html($row['performed_by_name'] ?? 'Automated') ?></td>
              <td><pre class="mb-0 small"><?= escape_html(json_encode(json_decode($row['details'] ?? '{}'), JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)) ?></pre></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
