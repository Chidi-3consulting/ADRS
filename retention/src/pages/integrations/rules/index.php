<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);
$orgId = require_org_id();
$ruleStmt = $pdo->prepare(
    "SELECT r.*, cs.name AS system_name, dc.name AS category_name
     FROM auto_categorization_rules r
     JOIN connected_systems cs ON cs.id = r.system_id AND cs.organization_id = :o
     JOIN data_categories dc ON dc.id = r.category_id AND dc.organization_id = :o2
     WHERE r.organization_id = :o3
     ORDER BY cs.name, r.priority ASC"
);
$ruleStmt->execute(['o' => $orgId, 'o2' => $orgId, 'o3' => $orgId]);
$rules = $ruleStmt->fetchAll();
$page_title = 'Auto-categorisation Rules';
$active_nav = 'integrations';
require __DIR__ . '/../../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Auto-categorisation Rules</h1>
  <a href="<?= APP_URL ?>/integrations/rules/create" class="btn btn-primary"><i class="bi bi-plus-lg"></i> New rule</a>
</div>
<p class="text-muted">When a record arrives via the API, the first active matching rule (lowest priority number) decides its category.</p>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($rules)): ?><p class="text-muted mb-0">No rules yet. Inbound records without a matching rule are rejected with <code>no_matching_rule</code>.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Priority</th><th>System</th><th>Object type</th><th>Condition</th><th>→ Category</th><th>Active</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($rules as $r): ?>
      <tr>
        <td><?= (int)$r['priority'] ?></td>
        <td><?= escape_html($r['system_name']) ?></td>
        <td><code><?= escape_html($r['object_type']) ?></code></td>
        <td class="small"><?= $r['condition_field'] ? escape_html($r['condition_field'].' = '.$r['condition_value']) : '<span class="text-muted">any</span>' ?></td>
        <td><?= escape_html($r['category_name']) ?></td>
        <td><?= (int)$r['is_active'] ? '✅' : '—' ?></td>
        <td><form method="post" action="<?= APP_URL ?>/integrations/rules/delete" data-confirm="Delete this rule?"><?= csrf_field() ?><input type="hidden" name="id" value="<?= (int)$r['id'] ?>"><button class="btn btn-sm btn-outline-danger">Delete</button></form></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../../includes/layout_footer.php'; ?>
