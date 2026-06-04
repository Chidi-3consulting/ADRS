<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/compliance_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
$error = null;
$cats = $pdo->query("SELECT id, name FROM data_categories WHERE deleted_at IS NULL ORDER BY name")->fetchAll();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    if (trim($_POST['activity_name'] ?? '') === '') { $error = 'Activity name is required.'; }
    else {
        create_ropa_entry($pdo, [
            'category_id' => (int) ($_POST['category_id'] ?? 0),
            'activity_name' => trim($_POST['activity_name']),
            'controller_name' => trim($_POST['controller_name'] ?? ''),
            'controller_contact' => trim($_POST['controller_contact'] ?? ''),
            'dpo_contact' => trim($_POST['dpo_contact'] ?? ''),
            'purpose' => trim($_POST['purpose'] ?? ''),
            'lawful_basis' => trim($_POST['lawful_basis'] ?? ''),
            'data_subjects' => trim($_POST['data_subjects'] ?? ''),
            'data_categories' => trim($_POST['data_categories'] ?? ''),
            'recipients' => trim($_POST['recipients'] ?? ''),
            'third_country_transfers' => trim($_POST['third_country_transfers'] ?? ''),
            'retention_summary' => trim($_POST['retention_summary'] ?? ''),
            'security_measures' => trim($_POST['security_measures'] ?? ''),
        ], (int) current_user()['id']);
        flash('success', 'RoPA entry created.');
        redirect(APP_URL . '/ropa');
    }
}
$page_title = 'New RoPA Entry';
$active_nav = 'ropa';
require __DIR__ . '/../../includes/layout_header.php';
$f = fn($k) => escape_html($_POST[$k] ?? '');
?>
<div class="card shadow-sm" style="max-width:820px"><div class="card-body">
  <h1 class="h4 mb-3">New Processing Activity (Art. 30)</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Activity name *</label><input name="activity_name" class="form-control" required value="<?= $f('activity_name') ?>"></div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Linked category</label><select name="category_id" class="form-select"><option value="">—</option><?php foreach ($cats as $c): ?><option value="<?= (int)$c['id'] ?>"><?= escape_html($c['name']) ?></option><?php endforeach; ?></select></div>
      <div class="col-md-6 mb-3"><label class="form-label">Lawful basis</label><input name="lawful_basis" class="form-control" value="<?= $f('lawful_basis') ?>"></div>
    </div>
    <div class="mb-3"><label class="form-label">Purpose</label><textarea name="purpose" class="form-control" rows="2"><?= $f('purpose') ?></textarea></div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Controller name</label><input name="controller_name" class="form-control" value="<?= $f('controller_name') ?>"></div>
      <div class="col-md-6 mb-3"><label class="form-label">DPO contact</label><input name="dpo_contact" class="form-control" value="<?= $f('dpo_contact') ?>"></div>
    </div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Data subjects</label><input name="data_subjects" class="form-control" value="<?= $f('data_subjects') ?>"></div>
      <div class="col-md-6 mb-3"><label class="form-label">Data categories</label><input name="data_categories" class="form-control" value="<?= $f('data_categories') ?>"></div>
    </div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Recipients</label><input name="recipients" class="form-control" value="<?= $f('recipients') ?>"></div>
      <div class="col-md-6 mb-3"><label class="form-label">Third-country transfers</label><input name="third_country_transfers" class="form-control" value="<?= $f('third_country_transfers') ?>"></div>
    </div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Retention summary</label><input name="retention_summary" class="form-control" value="<?= $f('retention_summary') ?>"></div>
      <div class="col-md-6 mb-3"><label class="form-label">Security measures</label><input name="security_measures" class="form-control" value="<?= $f('security_measures') ?>"></div>
    </div>
    <button class="btn btn-primary">Create entry</button>
    <a href="<?= APP_URL ?>/ropa" class="btn btn-secondary ms-2">Cancel</a>
  </form>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
