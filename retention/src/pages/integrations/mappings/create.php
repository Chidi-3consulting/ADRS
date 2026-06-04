<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);
$error = null;
$systems = $pdo->query("SELECT id, name FROM connected_systems WHERE is_active=1 ORDER BY name")->fetchAll();
$cats = $pdo->query("SELECT id, name FROM data_categories WHERE deleted_at IS NULL AND is_active=1 ORDER BY name")->fetchAll();
$adrsFields = ['record_reference','data_subject_type','collection_date','notes'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $sid = (int) ($_POST['system_id'] ?? 0); $cid = (int) ($_POST['category_id'] ?? 0);
    $obj = trim($_POST['external_object_type'] ?? ''); $ext = trim($_POST['external_field'] ?? '');
    $adrs = in_array($_POST['adrs_field'] ?? '', $adrsFields, true) ? $_POST['adrs_field'] : '';
    if ($sid<=0||$cid<=0||$obj===''||$ext===''||$adrs==='') { $error = 'All fields except "required" are mandatory.'; }
    else {
        $pdo->prepare("INSERT INTO field_mappings (system_id, external_object_type, category_id, external_field, adrs_field, is_required) VALUES (:s,:o,:c,:e,:a,:r)")
            ->execute(['s'=>$sid,'o'=>$obj,'c'=>$cid,'e'=>$ext,'a'=>$adrs,'r'=>isset($_POST['is_required'])?1:0]);
        flash('success', 'Field mapping added.');
        redirect(APP_URL . '/integrations/mappings');
    }
}
$page_title = 'New Field Mapping';
$active_nav = 'integrations';
require __DIR__ . '/../../../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:640px"><div class="card-body">
  <h1 class="h4 mb-3">New Field Mapping</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <?php if (empty($systems) || empty($cats)): ?><div class="alert alert-warning">Register a system and a category first.</div><?php else: ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">System *</label><select name="system_id" class="form-select" required><option value="">Select…</option><?php foreach ($systems as $s): ?><option value="<?= (int)$s['id'] ?>"><?= escape_html($s['name']) ?></option><?php endforeach; ?></select></div>
    <div class="mb-3"><label class="form-label">External object type *</label><input name="external_object_type" class="form-control" required placeholder="customer"></div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">External field *</label><input name="external_field" class="form-control" required placeholder="customer_id"></div>
      <div class="col-md-6 mb-3"><label class="form-label">→ ADRS field *</label><select name="adrs_field" class="form-select" required><?php foreach ($adrsFields as $f): ?><option value="<?= $f ?>"><?= $f ?></option><?php endforeach; ?></select></div>
    </div>
    <div class="mb-3"><label class="form-label">Category *</label><select name="category_id" class="form-select" required><option value="">Select…</option><?php foreach ($cats as $c): ?><option value="<?= (int)$c['id'] ?>"><?= escape_html($c['name']) ?></option><?php endforeach; ?></select></div>
    <div class="form-check mb-3"><input type="checkbox" class="form-check-input" id="req" name="is_required" value="1"><label class="form-check-label" for="req">Required field</label></div>
    <button class="btn btn-primary">Add mapping</button>
    <a href="<?= APP_URL ?>/integrations/mappings" class="btn btn-secondary ms-2">Cancel</a>
  </form>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../../includes/layout_footer.php'; ?>
