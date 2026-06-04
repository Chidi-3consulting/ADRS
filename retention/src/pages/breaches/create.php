<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/compliance_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    if (trim($_POST['title'] ?? '') === '') { $error = 'Title is required.'; }
    else {
        $r = create_breach($pdo, [
            'title' => trim($_POST['title']), 'description' => trim($_POST['description'] ?? ''),
            'discovered_at' => $_POST['discovered_at'] ? str_replace('T', ' ', $_POST['discovered_at']) . ':00' : date('Y-m-d H:i:s'),
            'occurred_at' => $_POST['occurred_at'] ? str_replace('T', ' ', $_POST['occurred_at']) . ':00' : '',
            'severity' => in_array($_POST['severity'] ?? '', ['low','medium','high','critical'], true) ? $_POST['severity'] : 'medium',
            'affected_records' => $_POST['affected_records'] ?? '',
        ], (int) current_user()['id']);
        require_once __DIR__ . '/../../includes/webhooks_lib.php';
        fire_ops_event($pdo, 'breach.created', ['reference' => $r['reference'], 'title' => trim($_POST['title']), 'severity' => $_POST['severity'] ?? 'medium', 'deadline' => $r['notify_deadline']]);
        flash('success', "Breach {$r['reference']} logged. 72-hour deadline: " . format_datetime($r['notify_deadline']) . '.');
        redirect(APP_URL . '/breaches');
    }
}
$page_title = 'Log Breach';
$active_nav = 'breaches';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:680px"><div class="card-body">
  <h1 class="h4 mb-3">Log a Data Breach</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Title *</label><input name="title" class="form-control" required value="<?= escape_html($_POST['title'] ?? '') ?>"></div>
    <div class="mb-3"><label class="form-label">Description</label><textarea name="description" class="form-control" rows="3"><?= escape_html($_POST['description'] ?? '') ?></textarea></div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Discovered at *</label><input type="datetime-local" name="discovered_at" class="form-control" value="<?= escape_html($_POST['discovered_at'] ?? date('Y-m-d\TH:i')) ?>"><div class="form-text">The 72-hour clock starts here.</div></div>
      <div class="col-md-6 mb-3"><label class="form-label">Occurred at (if known)</label><input type="datetime-local" name="occurred_at" class="form-control" value="<?= escape_html($_POST['occurred_at'] ?? '') ?>"></div>
    </div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Severity</label><select name="severity" class="form-select"><?php foreach (['low','medium','high','critical'] as $s): ?><option <?= ($_POST['severity'] ?? 'medium')===$s?'selected':'' ?>><?= $s ?></option><?php endforeach; ?></select></div>
      <div class="col-md-6 mb-3"><label class="form-label">Affected records (estimate)</label><input type="number" name="affected_records" class="form-control" value="<?= escape_html($_POST['affected_records'] ?? '') ?>"></div>
    </div>
    <button class="btn btn-danger">Log breach</button>
    <a href="<?= APP_URL ?>/breaches" class="btn btn-secondary ms-2">Cancel</a>
  </form>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
