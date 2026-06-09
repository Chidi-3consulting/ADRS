<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);
$error = null;
$systems = list_org_systems($pdo, true);
$cats = list_org_categories($pdo);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $sid = (int) ($_POST['system_id'] ?? 0);
    $cid = (int) ($_POST['category_id'] ?? 0);
    $objectType = trim($_POST['object_type'] ?? '');
    $name = trim($_POST['rule_name'] ?? '');
    $condField = trim($_POST['condition_field'] ?? '');
    $condValue = trim($_POST['condition_value'] ?? '');
    $priority = (int) ($_POST['priority'] ?? 10);
    if ($sid <= 0 || $cid <= 0 || $objectType === '' || $name === '') { $error = 'System, category, object type and rule name are required.'; }
    else {
        $orgId = require_org_id();
        $pdo->prepare(
            "INSERT INTO auto_categorization_rules (organization_id, system_id, rule_name, object_type, condition_field, condition_value, category_id, priority, created_by)
             VALUES (:oid,:s,:n,:ot,:cf,:cv,:c,:p,:by)"
        )->execute(['oid'=>$orgId,'s'=>$sid,'n'=>$name,'ot'=>$objectType,'cf'=>$condField ?: null,'cv'=>$condField ? $condValue : null,'c'=>$cid,'p'=>$priority,'by'=>(int)current_user()['id']]);
        flash('success', 'Rule created.');
        redirect(APP_URL . '/integrations/rules');
    }
}
$page_title = 'New Rule';
$active_nav = 'integrations';
require __DIR__ . '/../../../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:640px"><div class="card-body">
  <h1 class="h4 mb-3">New Auto-categorisation Rule</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <?php if (empty($systems) || empty($cats)): ?>
    <div class="alert alert-warning">You need at least one connected system and one category first.</div>
  <?php else: ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Connected system *</label>
      <select name="system_id" class="form-select" required><option value="">Select…</option><?php foreach ($systems as $s): ?><option value="<?= (int)$s['id'] ?>"><?= escape_html($s['name']) ?></option><?php endforeach; ?></select></div>
    <div class="mb-3"><label class="form-label">Rule name *</label><input name="rule_name" class="form-control" required></div>
    <div class="mb-3"><label class="form-label">Object type *</label><input name="object_type" class="form-control" required placeholder="e.g. customer, loan_application"></div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Condition field (optional)</label><input name="condition_field" class="form-control" placeholder="e.g. status"></div>
      <div class="col-md-6 mb-3"><label class="form-label">Condition value</label><input name="condition_value" class="form-control" placeholder="e.g. rejected"></div>
    </div>
    <div class="mb-3"><label class="form-label">→ Assign category *</label>
      <select name="category_id" class="form-select" required><option value="">Select…</option><?php foreach ($cats as $c): ?><option value="<?= (int)$c['id'] ?>"><?= escape_html($c['name']) ?></option><?php endforeach; ?></select></div>
    <div class="mb-3"><label class="form-label">Priority (lower wins)</label><input type="number" name="priority" class="form-control" value="10"></div>
    <button class="btn btn-primary">Create rule</button>
    <a href="<?= APP_URL ?>/integrations/rules" class="btn btn-secondary ms-2">Cancel</a>
  </form>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../../includes/layout_footer.php'; ?>
