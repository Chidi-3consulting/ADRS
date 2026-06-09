<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/records_lib.php';
require_role('admin', 'dpo', 'data_owner');
$pdo = get_db();
$me = current_user();
$isOwner = has_role('data_owner');
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    try {
        $res = create_data_record($pdo, [
            'category_id' => (int) ($_POST['category_id'] ?? 0),
            'record_reference' => trim($_POST['record_reference'] ?? ''),
            'data_subject_type' => trim($_POST['data_subject_type'] ?? ''),
            'collection_date' => trim($_POST['collection_date'] ?? ''),
            'notes' => trim($_POST['notes'] ?? ''),
        ], ['id' => (int) $me['id'], 'role' => $me['role']]);
        $msg = 'Record created.' . ($res['retention_end'] ? ' Retention end: ' . format_date($res['retention_end']) . '.' : ' Disposal triggered by consent withdrawal.');
        flash('success', $msg);
        redirect(APP_URL . '/records');
    } catch (Throwable $e) {
        $error = $e->getMessage();
    }
}

$orgId = require_org_id();
$catSql = "SELECT id, name, compliance_framework FROM data_categories WHERE organization_id = :org AND deleted_at IS NULL AND is_active = 1";
if ($isOwner) { $catSql .= ' AND owner_id = ' . (int) $me['id']; }
$catSql .= ' ORDER BY name';
$catStmt = $pdo->prepare($catSql);
$catStmt->execute(['org' => $orgId]);
$categories = $catStmt->fetchAll();

$page_title = 'Register Record';
$active_nav = 'records';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:760px"><div class="card-body">
  <h1 class="h4 mb-3">Register Data Record</h1>
  <?php if ($isOwner): ?><div class="alert alert-info">As a Data Owner you may register records in your assigned categories. Your DPO is notified automatically. Collection date is set to today.</div><?php endif; ?>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <?php if (empty($categories)): ?>
    <div class="alert alert-warning">No categories are available to you yet.</div>
  <?php else: ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Data Category *</label>
      <select name="category_id" id="category_id" class="form-select" required>
        <option value="">Select category…</option>
        <?php foreach ($categories as $c): ?><option value="<?= (int)$c['id'] ?>"><?= escape_html($c['name']) ?> (<?= escape_html($c['compliance_framework']) ?>)</option><?php endforeach; ?>
      </select></div>
    <div class="mb-3"><label class="form-label">Record reference *</label>
      <input name="record_reference" class="form-control" required value="<?= escape_html($_POST['record_reference'] ?? '') ?>"></div>
    <div class="mb-3"><label class="form-label">Data subject type</label>
      <input name="data_subject_type" class="form-control" value="<?= escape_html($_POST['data_subject_type'] ?? '') ?>" placeholder="e.g. Customer, Employee"></div>
    <div class="mb-3">
      <label class="form-label">Collection date *</label>
      <?php if ($isOwner): ?>
        <input type="text" class="form-control" value="<?= date('Y-m-d') ?> (today)" disabled>
        <input type="hidden" name="collection_date" value="<?= date('Y-m-d') ?>">
      <?php else: ?>
        <input type="date" name="collection_date" id="collection_date" class="form-control" required value="<?= escape_html($_POST['collection_date'] ?? date('Y-m-d')) ?>">
      <?php endif; ?>
    </div>
    <div id="retentionPreview" class="alert alert-info d-none">
      Retention end date: <strong id="calcDate"></strong> <span id="calcLabel" class="text-muted"></span>
      <div id="consentNotice" class="d-none text-warning mt-1">⚠️ Consent-based category — no fixed end date until consent is withdrawn.</div>
      <div id="dualWarn" class="d-none text-danger mt-1">🔐 Sensitive category — disposal requires two-person approval.</div>
    </div>
    <div class="mb-3"><label class="form-label">Notes</label><textarea name="notes" class="form-control" rows="2"><?= escape_html($_POST['notes'] ?? '') ?></textarea></div>
    <button class="btn btn-primary">Create record</button>
    <a href="<?= APP_URL ?>/records" class="btn btn-secondary ms-2">Cancel</a>
  </form>
  <?php endif; ?>
</div></div>
<script nonce="<?= csp_nonce() ?>">
const APP_URL = '<?= APP_URL ?>';
async function updatePreview(){
  const sel = document.getElementById('category_id');
  if (!sel || !sel.value) return;
  const res = await fetch(`${APP_URL}/src/api/get_category.php?id=${sel.value}`);
  if (!res.ok) return;
  const cat = await res.json();
  if (cat.error) return;
  const box = document.getElementById('retentionPreview');
  const calcDate = document.getElementById('calcDate');
  const consent = document.getElementById('consentNotice');
  const dual = document.getElementById('dualWarn');
  box.classList.remove('d-none');
  dual.classList.toggle('d-none', !cat.requires_dual_approval || cat.requires_dual_approval == 0);
  if (cat.disposal_trigger === 'consent_withdrawal') {
    calcDate.textContent = 'Not set';
    document.getElementById('calcLabel').textContent = '';
    consent.classList.remove('d-none');
  } else {
    consent.classList.add('d-none');
    const cd = (document.getElementById('collection_date') && document.getElementById('collection_date').value) || '<?= date('Y-m-d') ?>';
    const d = new Date(cd); d.setDate(d.getDate() + parseInt(cat.retention_period_days || 0));
    calcDate.textContent = d.toLocaleDateString('en-GB', {day:'2-digit',month:'short',year:'numeric'});
    document.getElementById('calcLabel').textContent = '(' + (cat.retention_period_label || '') + ')';
  }
}
document.getElementById('category_id')?.addEventListener('change', updatePreview);
document.getElementById('collection_date')?.addEventListener('change', updatePreview);
</script>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
