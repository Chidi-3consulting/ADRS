<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);
$keys = $pdo->query(
    "SELECT ak.*, cs.name AS system_name FROM api_keys ak JOIN connected_systems cs ON cs.id = ak.system_id ORDER BY ak.id DESC"
)->fetchAll();
$page_title = 'API Keys';
$active_nav = 'integrations';
require __DIR__ . '/../../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">API Keys</h1>
  <a href="<?= APP_URL ?>/integrations/keys/create" class="btn btn-primary"><i class="bi bi-plus-lg"></i> New key</a>
</div>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($keys)): ?><p class="text-muted mb-0">No API keys yet.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Name</th><th>System</th><th>Prefix</th><th>Permissions</th><th>Rate/min</th><th>Last used</th><th>Status</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($keys as $k): $perms = json_decode($k['permissions'] ?? '[]', true) ?: []; $active = (int)$k['is_active'] && $k['revoked_at']===null; ?>
      <tr class="<?= $active ? '' : 'text-muted' ?>">
        <td><?= escape_html($k['key_name']) ?></td>
        <td><?= escape_html($k['system_name']) ?></td>
        <td><code><?= escape_html($k['key_prefix']) ?>…</code></td>
        <td class="small"><?= escape_html(implode(', ', $perms)) ?></td>
        <td><?= (int)$k['rate_limit_per_min'] ?></td>
        <td class="small"><?= escape_html(format_datetime($k['last_used_at'])) ?></td>
        <td><?= $active ? '<span class="badge bg-success">active</span>' : '<span class="badge bg-secondary">revoked</span>' ?></td>
        <td><?php if ($active): ?>
          <form method="post" action="<?= APP_URL ?>/integrations/keys/revoke" onsubmit="return confirm('Revoke this key? External systems using it will stop working.')">
            <?= csrf_field() ?><input type="hidden" name="id" value="<?= (int)$k['id'] ?>">
            <button class="btn btn-sm btn-outline-danger">Revoke</button>
          </form>
        <?php endif; ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../../includes/layout_footer.php'; ?>
