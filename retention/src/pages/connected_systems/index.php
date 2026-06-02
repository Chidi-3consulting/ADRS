<?php
$pdo = get_pdo();
$stmt = $pdo->query(
    'SELECT cs.*, u.name AS created_by_name
     FROM connected_systems cs
     LEFT JOIN users u ON cs.created_by = u.id
     ORDER BY cs.created_at DESC'
);
$systems = $stmt->fetchAll(PDO::FETCH_ASSOC);
?>

<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Connected systems</h1>
    <p class="text-muted mb-0">Register external systems for enterprise ingestion and disposal integration.</p>
  </div>
  <a href="/retention/connected-systems/create" class="btn btn-primary">Register system</a>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if (empty($systems)): ?>
      <p class="text-muted">No connected systems are configured yet.</p>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-hover align-middle">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Base URL</th>
              <th>Status</th>
              <th>Created</th>
              <th>Created by</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($systems as $system): ?>
            <tr>
              <td><?= escape_html($system['name']) ?></td>
              <td><?= escape_html($system['system_type']) ?></td>
              <td><small><?= escape_html($system['base_url'] ?? '—') ?></small></td>
              <td><?= escape_html($system['is_active'] ? 'Active' : 'Inactive') ?></td>
              <td><?= escape_html($system['created_at']) ?></td>
              <td><?= escape_html($system['created_by_name'] ?? 'System') ?></td>
              <td><a href="/retention/connected-systems/edit?id=<?= escape_html($system['id']) ?>" class="btn btn-sm btn-outline-secondary">Edit</a></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
