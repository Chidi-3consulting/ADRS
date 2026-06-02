<?php
$pdo = get_pdo();
$stmt = $pdo->query(
    'SELECT n.*, u.name AS recipient_name, dr.record_reference, ds.reference AS dsar_reference
     FROM notifications n
     LEFT JOIN users u ON n.recipient_id = u.id
     LEFT JOIN data_records dr ON n.related_record_id = dr.id
     LEFT JOIN dsar_requests ds ON n.related_dsar_id = ds.id
     ORDER BY n.created_at DESC
     LIMIT 200'
);
$notifications = $stmt->fetchAll();
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Notifications</h1>
    <p class="text-muted mb-0">Review system messages and compliance alerts sent to operators.</p>
  </div>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if (empty($notifications)): ?>
      <p class="text-muted">No notifications have been recorded yet.</p>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-hover">
          <thead>
            <tr>
              <th>Recipient</th>
              <th>Type</th>
              <th>Subject</th>
              <th>Related</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($notifications as $notification): ?>
            <tr>
              <td><?= escape_html($notification['recipient_name'] ?? 'System') ?></td>
              <td><?= escape_html($notification['type']) ?></td>
              <td><?= escape_html($notification['subject']) ?></td>
              <td>
                <?php if ($notification['record_reference']): ?>
                  Record <?= escape_html($notification['record_reference']) ?>
                <?php elseif ($notification['dsar_reference']): ?>
                  DSAR <?= escape_html($notification['dsar_reference']) ?>
                <?php else: ?>
                  —
                <?php endif; ?>
              </td>
              <td><?= escape_html($notification['status']) ?></td>
              <td><?= escape_html($notification['created_at']) ?></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
