<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/dsar_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
$error = null;
$assignees = $pdo->query("SELECT id, name FROM users WHERE role IN ('admin','dpo') AND is_active=1 AND deleted_at IS NULL ORDER BY name")->fetchAll();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    try {
        if (trim($_POST['data_subject_name'] ?? '') === '') { throw new InvalidArgumentException('Data subject name is required.'); }
        $res = create_dsar($pdo, [
            'request_type' => $_POST['request_type'] ?? 'access',
            'compliance_framework' => $_POST['compliance_framework'] ?? 'GDPR',
            'data_subject_name' => trim($_POST['data_subject_name']),
            'data_subject_email' => trim($_POST['data_subject_email'] ?? ''),
            'data_subject_phone' => trim($_POST['data_subject_phone'] ?? ''),
            'received_date' => trim($_POST['received_date'] ?? ''),
            'assigned_to' => $_POST['assigned_to'] ?? '',
            'description' => trim($_POST['description'] ?? ''),
        ], (int) current_user()['id']);
        flash('success', 'DSAR ' . $res['reference'] . ' logged.');
        redirect(APP_URL . '/dsar/view?id=' . $res['id']);
    } catch (Throwable $e) { $error = $e->getMessage(); }
}
$page_title = 'New DSAR';
$active_nav = 'dsar';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:760px"><div class="card-body">
  <h1 class="h4 mb-3">Log a Data Subject Request</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Request type *</label>
        <select name="request_type" class="form-select">
          <?php foreach (['access','rectification','erasure','restriction','portability','objection'] as $t): ?><option value="<?= $t ?>"><?= ucfirst($t) ?></option><?php endforeach; ?>
        </select></div>
      <div class="col-md-6 mb-3"><label class="form-label">Framework</label>
        <select name="compliance_framework" class="form-select"><?php foreach (['GDPR','NDPR','BOTH'] as $f): ?><option><?= $f ?></option><?php endforeach; ?></select></div>
    </div>
    <div class="mb-3"><label class="form-label">Data subject name *</label><input name="data_subject_name" class="form-control" required value="<?= escape_html($_POST['data_subject_name'] ?? '') ?>"></div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Email</label><input type="email" name="data_subject_email" class="form-control" value="<?= escape_html($_POST['data_subject_email'] ?? '') ?>"></div>
      <div class="col-md-6 mb-3"><label class="form-label">Phone</label><input name="data_subject_phone" class="form-control" value="<?= escape_html($_POST['data_subject_phone'] ?? '') ?>"></div>
    </div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Received date *</label><input type="date" name="received_date" class="form-control" required value="<?= escape_html($_POST['received_date'] ?? date('Y-m-d')) ?>"></div>
      <div class="col-md-6 mb-3"><label class="form-label">Assign to</label>
        <select name="assigned_to" class="form-select"><option value="">— unassigned —</option>
          <?php foreach ($assignees as $a): ?><option value="<?= (int)$a['id'] ?>"><?= escape_html($a['name']) ?></option><?php endforeach; ?>
        </select></div>
    </div>
    <div class="mb-3"><label class="form-label">Description</label><textarea name="description" class="form-control" rows="3"><?= escape_html($_POST['description'] ?? '') ?></textarea></div>
    <button class="btn btn-primary">Create DSAR</button>
    <a href="<?= APP_URL ?>/dsar" class="btn btn-secondary ms-2">Cancel</a>
  </form>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
