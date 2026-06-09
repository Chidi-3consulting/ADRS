<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);
$orgId = require_org_id();
$mapStmt = $pdo->prepare(
    "SELECT fm.*, cs.name AS system_name, dc.name AS category_name
     FROM field_mappings fm
     JOIN connected_systems cs ON cs.id = fm.system_id AND cs.organization_id = :o
     JOIN data_categories dc ON dc.id = fm.category_id AND dc.organization_id = :o2
     WHERE fm.organization_id = :o3
     ORDER BY cs.name, fm.external_object_type"
);
$mapStmt->execute(['o' => $orgId, 'o2' => $orgId, 'o3' => $orgId]);
$maps = $mapStmt->fetchAll();
$page_title = 'Field Mappings';
$active_nav = 'integrations';
require __DIR__ . '/../../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Field Mappings</h1>
  <a href="<?= APP_URL ?>/integrations/mappings/create" class="btn btn-primary"><i class="bi bi-plus-lg"></i> New mapping</a>
</div>
<p class="text-muted">Document how external system fields map onto ADRS record fields (used by integration teams when configuring a connector).</p>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($maps)): ?><p class="text-muted mb-0">No field mappings yet.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>System</th><th>Object type</th><th>External field</th><th>→ ADRS field</th><th>Category</th><th>Required</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($maps as $m): ?>
      <tr>
        <td><?= escape_html($m['system_name']) ?></td>
        <td><code><?= escape_html($m['external_object_type']) ?></code></td>
        <td><code><?= escape_html($m['external_field']) ?></code></td>
        <td><code><?= escape_html($m['adrs_field']) ?></code></td>
        <td><?= escape_html($m['category_name']) ?></td>
        <td><?= (int)$m['is_required'] ? '✅' : '—' ?></td>
        <td><form method="post" action="<?= APP_URL ?>/integrations/mappings/delete" data-confirm="Delete mapping?"><?= csrf_field() ?><input type="hidden" name="id" value="<?= (int)$m['id'] ?>"><button class="btn btn-sm btn-outline-danger">Delete</button></form></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../../includes/layout_footer.php'; ?>
