<?php
$pdo = get_pdo();
$stmt = $pdo->query(
    'SELECT ak.*, cs.name AS system_name, u.name AS created_by_name
     FROM api_keys ak
     LEFT JOIN connected_systems cs ON ak.system_id = cs.id
     LEFT JOIN users u ON ak.created_by = u.id
     ORDER BY ak.created_at DESC'
);
$keys = $stmt->fetchAll(PDO::FETCH_ASSOC);
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">API keys</h1>
    <p class="text-muted mb-0">Manage external system credentials used by enterprise API integrations.</p>
  </div>
  <a href="/retention/api-keys/create" class="btn btn-primary">Create API key</a>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if (empty($keys)): ?>
      <p class="text-muted">No API keys have been created yet.</p>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-hover align-middle">
          <thead>
            <tr>
              <th>Name</th>
              <th>System</th>
              <th>Prefix</th>
              <th>Permissions</th>
              <th>Rate limit</th>
              <th>Status</th>
              <th>Expires</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($keys as $key): ?>
            <?php $permissions = json_decode($key['permissions'] ?? '[]', true) ?: []; ?>
            <tr>
              <td><?= escape_html($key['key_name']) ?></td>
              <td><?= escape_html($key['system_name'] ?? 'Unknown') ?></td>
              <td><?= escape_html($key['key_prefix']) ?></td>
              <td><?= escape_html(implode(', ', $permissions)) ?></td>
              <td><?= escape_html((int)$key['rate_limit_per_min']) ?>/min</td>
              <td><?= escape_html($key['is_active'] ? 'Active' : 'Revoked') ?></td>
              <td><?= escape_html($key['expires_at'] ?? 'Never') ?></td>
              <td><?= escape_html($key['created_at']) ?></td>
              <td><a href="/retention/api-keys/edit?id=<?= escape_html($key['id']) ?>" class="btn btn-sm btn-outline-secondary">Edit</a></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
