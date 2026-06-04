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
    if (trim($_POST['title'] ?? '') === '') { $error = 'Title is required.'; }
    else {
        $id = create_dpia($pdo, [
            'title' => trim($_POST['title']), 'category_id' => (int) ($_POST['category_id'] ?? 0),
            'description' => trim($_POST['description'] ?? ''),
            'necessity_score' => (int) ($_POST['necessity_score'] ?? 1),
            'proportionality_score' => (int) ($_POST['proportionality_score'] ?? 1),
            'likelihood_score' => (int) ($_POST['likelihood_score'] ?? 1),
            'severity_score' => (int) ($_POST['severity_score'] ?? 1),
            'mitigation' => trim($_POST['mitigation'] ?? ''),
        ], (int) current_user()['id']);
        flash('success', 'DPIA created (risk auto-scored).');
        redirect(APP_URL . '/dpia');
    }
}
$page_title = 'New DPIA';
$active_nav = 'dpia';
require __DIR__ . '/../../includes/layout_header.php';
$sel = function($name) { $v = (int)($_POST[$name] ?? 1); $o=''; for($i=1;$i<=5;$i++){$o.='<option value="'.$i.'" '.($v===$i?'selected':'').'>'.$i.'</option>';} return $o; };
?>
<div class="card shadow-sm" style="max-width:760px"><div class="card-body">
  <h1 class="h4 mb-3">New DPIA</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Title *</label><input name="title" class="form-control" required value="<?= escape_html($_POST['title'] ?? '') ?>"></div>
    <div class="mb-3"><label class="form-label">Linked category</label><select name="category_id" class="form-select"><option value="">—</option><?php foreach ($cats as $c): ?><option value="<?= (int)$c['id'] ?>"><?= escape_html($c['name']) ?></option><?php endforeach; ?></select></div>
    <div class="mb-3"><label class="form-label">Description</label><textarea name="description" class="form-control" rows="2"><?= escape_html($_POST['description'] ?? '') ?></textarea></div>
    <p class="text-muted small mb-1">Score each 1 (low) to 5 (high). Risk = likelihood × severity.</p>
    <div class="row">
      <div class="col-md-3 mb-3"><label class="form-label">Necessity</label><select name="necessity_score" class="form-select"><?= $sel('necessity_score') ?></select></div>
      <div class="col-md-3 mb-3"><label class="form-label">Proportionality</label><select name="proportionality_score" class="form-select"><?= $sel('proportionality_score') ?></select></div>
      <div class="col-md-3 mb-3"><label class="form-label">Likelihood</label><select name="likelihood_score" class="form-select"><?= $sel('likelihood_score') ?></select></div>
      <div class="col-md-3 mb-3"><label class="form-label">Severity</label><select name="severity_score" class="form-select"><?= $sel('severity_score') ?></select></div>
    </div>
    <div class="mb-3"><label class="form-label">Mitigation measures</label><textarea name="mitigation" class="form-control" rows="2"><?= escape_html($_POST['mitigation'] ?? '') ?></textarea></div>
    <button class="btn btn-primary">Create DPIA</button>
    <a href="<?= APP_URL ?>/dpia" class="btn btn-secondary ms-2">Cancel</a>
  </form>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
