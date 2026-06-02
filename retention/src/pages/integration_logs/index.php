<?php
$pdo = get_pdo();
$stmt = $pdo->query(
    'SELECT il.*, s.name AS system_name
     FROM integration_logs il
     LEFT JOIN connected_systems s ON il.system_id = s.id
     ORDER BY il.created_at DESC
     LIMIT 200'
);
$logs = $stmt->fetchAll();
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Integration logs</h1>
    <p class="text-muted mb-0">Audit inbound/outbound API activity for enterprise integration and ingestion.</p>
  </div>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if (empty($logs)): ?>
      <p class="text-muted">No integration log entries are available.</p>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-hover">
          <thead>
            <tr>
              <th>Time</th>
              <th>Direction</th>
              <th>Endpoint</th>
              <th>Method</th>
              <th>Status</th>
              <th>System</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($logs as $log): ?>
            <tr>
              <td><?= escape_html($log['created_at']) ?></td>
              <td><?= escape_html($log['direction']) ?></td>
              <td><?= escape_html($log['endpoint']) ?></td>
              <td><?= escape_html($log['method']) ?></td>
              <td><?= escape_html($log['status_code']) ?></td>
              <td><?= escape_html($log['system_name'] ?? 'Unknown') ?></td>
              <td><?= escape_html($log['duration_ms'] !== null ? $log['duration_ms'] . ' ms' : '—') ?></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
