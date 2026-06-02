<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/categories_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
$id = (int) ($_GET['id'] ?? 0);
$category = $id > 0 ? fetch_category($pdo, $id) : null;
if ($category === null) { http_response_code(404); require __DIR__ . '/../../../404.php'; exit; }
$error = null;

$owners = $pdo->query("SELECT id, name FROM users WHERE role='data_owner' AND is_active=1 AND deleted_at IS NULL ORDER BY name")->fetchAll();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    try {
        if (trim($_POST['name'] ?? '') === '') { throw new InvalidArgumentException('Name is required.'); }
        $res = update_category($pdo, $id, [
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
        $msg = 'Category updated.';
        if ($res['recalc_queued'] > 0) {
            $msg .= " {$res['recalc_queued']} record(s) queued for recalculation review — no record dates changed.";
        }
        flash('success', $msg);
        redirect(APP_URL . '/categories');
    } catch (Throwable $e) {
        $error = $e->getMessage();
    }
}
$page_title = 'Edit Category';
$active_nav = 'categories';
require __DIR__ . '/../../includes/layout_header.php';
$cur = fn($k) => escape_html($_POST[$k] ?? (string) $category[$k]);
?>
<div class="card shadow-sm" style="max-width:820px"><div class="card-body">
  <h1 class="h4 mb-3">Edit Category</h1>
  <?php if ($category['source'] === 'seeded'): ?><div class="alert alert-info">📚 Seeded from the compliance library — edits are allowed.</div><?php endif; ?>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <div class="alert alert-warning small">Changing the retention period will queue affected records for DPO recalculation review (B2). No record dates change until reviewed.</div>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Name *</label><input name="name" class="form-control" required value="<?= $cur('name') ?>"></div>
    <div class="mb-3"><label class="form-label">Description</label><textarea name="description" class="form-control" rows="2"><?= $cur('description') ?></textarea></div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Framework *</label>
        <select name="compliance_framework" class="form-select">
          <?php foreach (['GDPR','NDPR','BOTH'] as $o): ?><option <?= ($_POST['compliance_framework'] ?? $category['compliance_framework'])===$o?'selected':'' ?>><?= $o ?></option><?php endforeach; ?>
        </select></div>
      <div class="col-md-6 mb-3"><label class="form-label">Legal basis *</label>
        <select name="legal_basis" class="form-select">
          <?php foreach (['legal_obligation','contract','consent','legitimate_interest','vital_interest','public_task'] as $o): ?>
            <option value="<?= $o ?>" <?= ($_POST['legal_basis'] ?? $category['legal_basis'])===$o?'selected':'' ?>><?= escape_html(get_legal_basis_label($o)) ?></option>
          <?php endforeach; ?>
        </select></div>
    </div>
    <div class="mb-3"><label class="form-label">Disposal trigger *</label>
      <select name="disposal_trigger" id="trigger" class="form-select" onchange="toggleRetention()">
        <option value="date_based" <?= ($_POST['disposal_trigger'] ?? $category['disposal_trigger'])==='date_based'?'selected':'' ?>>📅 Date-based</option>
        <option value="consent_withdrawal" <?= ($_POST['disposal_trigger'] ?? $category['disposal_trigger'])==='consent_withdrawal'?'selected':'' ?>>👤 Consent withdrawal</option>
      </select></div>
    <div id="retentionBlock" class="row">
      <div class="col-md-4 mb-3"><label class="form-label">Retention days</label><input type="number" name="retention_period_days" class="form-control" value="<?= $cur('retention_period_days') ?>"></div>
      <div class="col-md-8 mb-3"><label class="form-label">Retention label</label><input name="retention_period_label" class="form-control" value="<?= $cur('retention_period_label') ?>"></div>
    </div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Disposal method *</label>
        <select name="disposal_method" class="form-select">
          <?php foreach (['delete','anonymise','archive'] as $o): ?><option value="<?= $o ?>" <?= ($_POST['disposal_method'] ?? $category['disposal_method'])===$o?'selected':'' ?>><?= escape_html(get_disposal_method_label($o)) ?></option><?php endforeach; ?>
        </select></div>
      <div class="col-md-6 mb-3"><label class="form-label">Review frequency *</label>
        <select name="review_frequency" class="form-select">
          <?php foreach (['monthly','quarterly','annually'] as $o): ?><option <?= ($_POST['review_frequency'] ?? $category['review_frequency'])===$o?'selected':'' ?>><?= ucfirst($o) ?></option><?php endforeach; ?>
        </select></div>
    </div>
    <div class="mb-3"><label class="form-label">Data Owner</label>
      <select name="owner_id" class="form-select"><option value="">— none —</option>
        <?php foreach ($owners as $o): ?><option value="<?= (int)$o['id'] ?>" <?= ((int)($_POST['owner_id'] ?? $category['owner_id'])===(int)$o['id'])?'selected':'' ?>><?= escape_html($o['name']) ?></option><?php endforeach; ?>
      </select></div>
    <div class="form-check mb-3">
      <input type="checkbox" class="form-check-input" id="dual" name="requires_dual_approval" value="1" <?= ($_POST['requires_dual_approval'] ?? $category['requires_dual_approval'])?'checked':'' ?>>
      <label class="form-check-label" for="dual">🔐 Require two-person approval for disposal</label>
    </div>
    <button class="btn btn-primary">Save changes</button>
    <a href="<?= APP_URL ?>/categories" class="btn btn-secondary ms-2">Cancel</a>
  </form>
</div></div>
<script>
function toggleRetention(){ document.getElementById('retentionBlock').style.display = (document.getElementById('trigger').value==='consent_withdrawal')?'none':'flex'; }
toggleRetention();
</script>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
