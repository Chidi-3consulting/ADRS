<?php
$pdo = get_pdo();
$stmt = $pdo->query(
    'SELECT dd.*, s.name AS system_name, dr.record_reference
     FROM disposal_dispatches dd
     LEFT JOIN connected_systems s ON dd.system_id = s.id
     LEFT JOIN data_records dr ON dd.record_id = dr.id
     ORDER BY dd.created_at DESC
     LIMIT 200'
);
$dispatches = $stmt->fetchAll();
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Disposal dispatch</h1>
    <p class="text-muted mb-0">Track outbound disposal instructions sent to connected systems.</p>
  </div>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if (empty($dispatches)): ?>
      <p class="text-muted">No disposal dispatch entries are available.</p>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-hover align-middle">
          <thead>
            <tr>
              <th>Created</th>
              <th>Status</th>
              <th>Record</th>
              <th>System</th>
              <th>Dispatch</th>
              <th>Endpoint</th>
              <th>Result</th>
              <th>Attempts</th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($dispatches as $dispatch): ?>
            <tr>
              <td><?= escape_html($dispatch['created_at']) ?></td>
              <td><?= escape_html($dispatch['status']) ?></td>
              <td><?= escape_html($dispatch['record_reference'] ?? 'Unknown') ?></td>
              <td><?= escape_html($dispatch['system_name'] ?? 'Unknown') ?></td>
              <td><?= escape_html($dispatch['dispatch_type']) ?></td>
              <td><small><?= escape_html($dispatch['endpoint_url'] ?? '—') ?></small></td>
              <td><?= escape_html($dispatch['response_code'] ?? '—') ?></td>
              <td><?= escape_html($dispatch['attempts']) ?></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>