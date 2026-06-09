<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);
$orgId = require_org_id();
$sysStmt = $pdo->prepare('SELECT * FROM connected_systems WHERE organization_id = :o ORDER BY name');
$sysStmt->execute(['o' => $orgId]);
$systems = $sysStmt->fetchAll();
$page_title = 'Connected Systems';
$active_nav = 'integrations';
require __DIR__ . '/../../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Connected Systems</h1>
  <a href="<?= APP_URL ?>/integrations/systems/create" class="btn btn-primary"><i class="bi bi-plus-lg"></i> Register system</a>
</div>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($systems)): ?><p class="text-muted mb-0">No systems connected yet.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Name</th><th>Type</th><th>Base URL</th><th>Health</th><th>Synced</th><th>Active</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($systems as $s): ?>
      <tr>
        <td><?= escape_html($s['name']) ?></td>
        <td><?= escape_html(str_replace('_',' ', $s['system_type'])) ?></td>
        <td class="small text-muted"><?= escape_html($s['base_url'] ?? '—') ?></td>
        <td><span class="badge bg-secondary"><?= escape_html($s['health_status']) ?></span></td>
        <td><?= (int)$s['records_synced'] ?></td>
        <td><?= (int)$s['is_active'] ? '✅' : '—' ?></td>
        <td><a href="<?= APP_URL ?>/integrations/systems/edit?id=<?= (int)$s['id'] ?>" class="btn btn-sm btn-outline-primary">Edit</a></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../../includes/layout_footer.php'; ?>
