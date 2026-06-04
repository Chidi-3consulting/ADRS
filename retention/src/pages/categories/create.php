<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/categories_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
$error = null;

$owners = $pdo->query("SELECT id, name FROM users WHERE role='data_owner' AND is_active=1 AND deleted_at IS NULL ORDER BY name")->fetchAll();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    try {
        if (trim($_POST['name'] ?? '') === '') { throw new InvalidArgumentException('Name is required.'); }
        $id = create_category($pdo, [
            'name' => trim($_POST['name']),
            'description' => trim($_POST['description'] ?? ''),
            'compliance_framework' => $_POST['compliance_framework'] ?? 'GDPR',
            'legal_basis' => $_POST['legal_basis'] ?? 'legal_obligation',
            'retention_period_days' => (int) ($_POST['retention_period_days'] ?? 0),
            'retention_period_label' => trim($_POST['retention_period_label'] ?? ''),
            'disposal_method' => $_POST['disposal_method'] ?? 'delete',
            'disposal_trigger' => $_POST['disposal_trigger'] ?? 'date_based',
            'requires_dual_approval' => isset($_POST['requires_dual_approval']) ? 1 : 0,
            'owner_id' => ($_POST['owner_id'] ?? '') !== '' ? (int) $_POST['owner_id'] : null,
            'review_frequency' => $_POST['review_frequency'] ?? 'quarterly',
        ], (int) current_user()['id']);
        flash('success', 'Category created.');
        redirect(APP_URL . '/categories');
    } catch (Throwable $e) {
        $error = $e->getMessage();
    }
}
$page_title = 'Create Category';
$active_nav = 'categories';
require __DIR__ . '/../../includes/layout_header.php';
$v = fn($k, $d = '') => escape_html($_POST[$k] ?? $d);
?>
<div class="card shadow-sm" style="max-width:820px"><div class="card-body">
  <h1 class="h4 mb-3">Create Data Category</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Name *</label>
      <input name="name" class="form-control" required value="<?= $v('name') ?>"></div>
    <div class="mb-3"><label class="form-label">Description</label>
      <textarea name="description" class="form-control" rows="2"><?= $v('description') ?></textarea></div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Framework *</label>
        <select name="compliance_framework" class="form-select">
          <?php foreach (['GDPR','NDPR','BOTH'] as $o): ?><option <?= ($_POST['compliance_framework'] ?? '')===$o?'selected':'' ?>><?= $o ?></option><?php endforeach; ?>
        </select></div>
      <div class="col-md-6 mb-3"><label class="form-label">Legal basis *</label>
        <select name="legal_basis" class="form-select">
          <?php foreach (['legal_obligation','contract','consent','legitimate_interest','vital_interest','public_task'] as $o): ?>
            <option value="<?= $o ?>" <?= ($_POST['legal_basis'] ?? '')===$o?'selected':'' ?>><?= escape_html(get_legal_basis_label($o)) ?></option>
          <?php endforeach; ?>
        </select></div>
    </div>
    <div class="mb-3"><label class="form-label">Disposal trigger *</label>
      <select name="disposal_trigger" id="trigger" class="form-select" onchange="toggleRetention()">
        <option value="date_based" <?= ($_POST['disposal_trigger'] ?? '')==='date_based'?'selected':'' ?>>📅 Date-based — dispose after a fixed period</option>
        <option value="consent_withdrawal" <?= ($_POST['disposal_trigger'] ?? '')==='consent_withdrawal'?'selected':'' ?>>👤 Consent withdrawal — dispose 30 days after consent withdrawn</option>
      </select></div>
    <div id="retentionBlock" class="row">
      <div class="col-md-4 mb-3"><label class="form-label">Retention days</label>
        <input type="number" name="retention_period_days" class="form-control" value="<?= $v('retention_period_days','0') ?>"></div>
      <div class="col-md-8 mb-3"><label class="form-label">Retention label</label>
        <input name="retention_period_label" class="form-control" value="<?= $v('retention_period_label') ?>" placeholder="e.g. 7 years"></div>
    </div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Disposal method *</label>
        <select name="disposal_method" class="form-select">
          <?php foreach (['delete','anonymise','archive'] as $o): ?><option value="<?= $o ?>" <?= ($_POST['disposal_method'] ?? '')===$o?'selected':'' ?>><?= escape_html(get_disposal_method_label($o)) ?></option><?php endforeach; ?>
        </select></div>
      <div class="col-md-6 mb-3"><label class="form-label">Review frequency *</label>
        <select name="review_frequency" class="form-select">
          <?php foreach (['monthly','quarterly','annually'] as $o): ?><option <?= ($_POST['review_frequency'] ?? '')===$o?'selected':'' ?>><?= ucfirst($o) ?></option><?php endforeach; ?>
        </select></div>
    </div>
    <div class="mb-3"><label class="form-label">Data Owner</label>
      <select name="owner_id" class="form-select"><option value="">— none —</option>
        <?php foreach ($owners as $o): ?><option value="<?= (int)$o['id'] ?>" <?= ((int)($_POST['owner_id'] ?? 0)===(int)$o['id'])?'selected':'' ?>><?= escape_html($o['name']) ?></option><?php endforeach; ?>
      </select></div>
    <div class="form-check mb-3">
      <input type="checkbox" class="form-check-input" id="dual" name="requires_dual_approval" value="1" <?= isset($_POST['requires_dual_approval'])?'checked':'' ?>>
      <label class="form-check-label" for="dual">🔐 Require two-person approval for disposal (sensitive data: health, biometric, children's)</label>
    </div>
    <button class="btn btn-primary">Create category</button>
    <a href="<?= APP_URL ?>/categories" class="btn btn-secondary ms-2">Cancel</a>
  </form>
</div></div>
<script>
function toggleRetention(){
  var t=document.getElementById('trigger').value;
  document.getElementById('retentionBlock').style.display = (t==='consent_withdrawal')?'none':'flex';
}
toggleRetention();
</script>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
