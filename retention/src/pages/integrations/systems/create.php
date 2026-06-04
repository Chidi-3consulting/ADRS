<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);
$error = null;
$types = ['crm','core_banking','hr_platform','customer_db','loan_management','ecommerce','custom'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $name = trim($_POST['name'] ?? '');
    $type = in_array($_POST['system_type'] ?? '', $types, true) ? $_POST['system_type'] : 'custom';
    $baseUrl = trim($_POST['base_url'] ?? '');
    if ($name === '') { $error = 'Name is required.'; }
    else {
        $pdo->prepare("INSERT INTO connected_systems (name, system_type, base_url, description, created_by) VALUES (:n,:t,:u,:d,:b)")
            ->execute(['n'=>$name,'t'=>$type,'u'=>$baseUrl ?: null,'d'=>trim($_POST['description'] ?? '') ?: null,'b'=>(int)current_user()['id']]);
        log_audit($pdo, 'user_updated', 'system', (int)$pdo->lastInsertId(), (int)current_user()['id'], ['connected_system_created'=>$name], get_client_ip());
        flash('success', 'Connected system registered.');
        redirect(APP_URL . '/integrations/systems');
    }
}
$page_title = 'Register System';
$active_nav = 'integrations';
require __DIR__ . '/../../../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:640px"><div class="card-body">
  <h1 class="h4 mb-3">Register Connected System</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Name *</label><input name="name" class="form-control" required value="<?= escape_html($_POST['name'] ?? '') ?>"></div>
    <div class="mb-3"><label class="form-label">System type</label>
      <select name="system_type" class="form-select"><?php foreach ($types as $t): ?><option value="<?= $t ?>"><?= escape_html(str_replace('_',' ',$t)) ?></option><?php endforeach; ?></select></div>
    <div class="mb-3"><label class="form-label">Base URL (for outbound disposal webhooks)</label>
      <input name="base_url" class="form-control" placeholder="https://system.example/api" value="<?= escape_html($_POST['base_url'] ?? '') ?>">
      <div class="form-text">Disposal instructions POST to <code>{base_url}/adrs/disposal</code>.</div></div>
    <div class="mb-3"><label class="form-label">Description</label><textarea name="description" class="form-control" rows="2"><?= escape_html($_POST['description'] ?? '') ?></textarea></div>
    <button class="btn btn-primary">Register</button>
    <a href="<?= APP_URL ?>/integrations/systems" class="btn btn-secondary ms-2">Cancel</a>
  </form>
</div></div>
<?php require __DIR__ . '/../../../includes/layout_footer.php'; ?>
