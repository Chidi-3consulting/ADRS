<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);
$id = (int) ($_GET['id'] ?? 0);
$sys = $pdo->prepare("SELECT * FROM connected_systems WHERE id=:id"); $sys->execute(['id'=>$id]); $system = $sys->fetch();
if (!$system) { http_response_code(404); require __DIR__ . '/../../../../404.php'; exit; }
$error = null;
$types = ['crm','core_banking','hr_platform','customer_db','loan_management','ecommerce','custom'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    if (($_POST['action'] ?? '') === 'toggle') {
        $pdo->prepare("UPDATE connected_systems SET is_active = 1 - is_active WHERE id=:id")->execute(['id'=>$id]);
        flash('success', 'System status updated.');
        redirect(APP_URL . '/integrations/systems');
    }
    $name = trim($_POST['name'] ?? '');
    $type = in_array($_POST['system_type'] ?? '', $types, true) ? $_POST['system_type'] : 'custom';
    if ($name === '') { $error = 'Name is required.'; }
    else {
        $pdo->prepare("UPDATE connected_systems SET name=:n, system_type=:t, base_url=:u, description=:d WHERE id=:id")
            ->execute(['n'=>$name,'t'=>$type,'u'=>trim($_POST['base_url'] ?? '') ?: null,'d'=>trim($_POST['description'] ?? '') ?: null,'id'=>$id]);
        flash('success', 'System updated.');
        redirect(APP_URL . '/integrations/systems');
    }
}
$page_title = 'Edit System';
$active_nav = 'integrations';
require __DIR__ . '/../../../includes/layout_header.php';
$cur = fn($k) => escape_html($_POST[$k] ?? (string)($system[$k] ?? ''));
?>
<div class="card shadow-sm" style="max-width:640px"><div class="card-body">
  <h1 class="h4 mb-3">Edit Connected System</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Name *</label><input name="name" class="form-control" required value="<?= $cur('name') ?>"></div>
    <div class="mb-3"><label class="form-label">System type</label>
      <select name="system_type" class="form-select"><?php foreach ($types as $t): ?><option value="<?= $t ?>" <?= ($_POST['system_type'] ?? $system['system_type'])===$t?'selected':'' ?>><?= escape_html(str_replace('_',' ',$t)) ?></option><?php endforeach; ?></select></div>
    <div class="mb-3"><label class="form-label">Base URL</label><input name="base_url" class="form-control" value="<?= $cur('base_url') ?>"></div>
    <div class="mb-3"><label class="form-label">Description</label><textarea name="description" class="form-control" rows="2"><?= $cur('description') ?></textarea></div>
    <button class="btn btn-primary">Save</button>
    <a href="<?= APP_URL ?>/integrations/systems" class="btn btn-secondary ms-2">Cancel</a>
  </form>
  <hr>
  <form method="post" onsubmit="return confirm('Toggle active status?')">
    <?= csrf_field() ?><input type="hidden" name="action" value="toggle">
    <button class="btn btn-sm btn-outline-<?= (int)$system['is_active'] ? 'warning">Deactivate' : 'success">Activate' ?> system</button>
  </form>
</div></div>
<?php require __DIR__ . '/../../../includes/layout_footer.php'; ?>
