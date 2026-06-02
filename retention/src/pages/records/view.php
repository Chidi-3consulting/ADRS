<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/records_lib.php';
require_login();
$pdo = get_db();
$id = (int) ($_GET['id'] ?? 0);
$record = $id > 0 ? fetch_record($pdo, $id) : null;
if ($record === null) { http_response_code(404); require __DIR__ . '/../../../404.php'; exit; }

// Data Owners may only view records in their own categories.
if (has_role('data_owner')) {
    $own = fetch_category($pdo, (int) $record['category_id']);
    if (!$own || (int) $own['owner_id'] !== (int) current_user()['id']) { http_response_code(403); exit('Forbidden'); }
}

$creator = null;
if ($record['created_by']) {
    $cs = $pdo->prepare("SELECT name FROM users WHERE id=:i"); $cs->execute(['i' => $record['created_by']]);
    $creator = $cs->fetch()['name'] ?? null;
}
$audit = $pdo->prepare("SELECT * FROM audit_log WHERE entity_type='data_record' AND entity_id=:id ORDER BY id DESC LIMIT 10");
$audit->execute(['id' => $id]);
$auditRows = $audit->fetchAll();
$allCats = $pdo->query("SELECT id, name FROM data_categories WHERE deleted_at IS NULL AND is_active=1 ORDER BY name")->fetchAll();

$page_title = 'Record ' . $record['record_reference'];
$active_nav = 'records';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0"><?= escape_html($record['record_reference']) ?> <?= get_status_badge($record['status']) ?></h1>
  <div>
    <?php if (has_role('admin','dpo')): ?><a href="<?= APP_URL ?>/records/edit?id=<?= $id ?>" class="btn btn-outline-primary">Edit</a><?php endif; ?>
    <a href="<?= APP_URL ?>/records" class="btn btn-secondary">Back</a>
  </div>
</div>
<div class="row g-3">
  <div class="col-lg-7">
    <div class="card shadow-sm mb-3"><div class="card-body">
      <h5 class="card-title">Details</h5>
      <dl class="row mb-0">
        <dt class="col-sm-4">Category</dt><dd class="col-sm-8"><?= escape_html($record['category_name']) ?> <?= get_framework_badge($record['compliance_framework']) ?></dd>
        <dt class="col-sm-4">Legal basis</dt><dd class="col-sm-8"><?= escape_html(get_legal_basis_label($record['legal_basis'])) ?></dd>
        <dt class="col-sm-4">Disposal trigger</dt><dd class="col-sm-8"><?= $record['disposal_trigger']==='consent_withdrawal' ? '👤 Consent withdrawal' : '📅 Date-based' ?></dd>
        <dt class="col-sm-4">Data subject type</dt><dd class="col-sm-8"><?= escape_html($record['data_subject_type'] ?? '—') ?></dd>
        <dt class="col-sm-4">Collection date</dt><dd class="col-sm-8"><?= escape_html(format_date($record['collection_date'])) ?></dd>
        <dt class="col-sm-4">Retention end</dt><dd class="col-sm-8"><?= $record['retention_end_date'] ? escape_html(format_date($record['retention_end_date'])) : '<span class="text-muted">— pending consent withdrawal</span>' ?></dd>
        <dt class="col-sm-4">Dual approval</dt><dd class="col-sm-8"><?= (int)$record['requires_dual_approval'] ? 'Yes 🔐' : 'No' ?></dd>
        <dt class="col-sm-4">Legal hold</dt><dd class="col-sm-8"><?= (int)$record['legal_hold'] ? '🔒 On hold' : 'No' ?></dd>
        <dt class="col-sm-4">Created by</dt><dd class="col-sm-8"><?= escape_html($creator ?? 'System') ?><?= (int)$record['created_by_owner'] ? ' 👤 (Data Owner)' : '' ?></dd>
        <dt class="col-sm-4">Notes</dt><dd class="col-sm-8"><?= nl2br(escape_html($record['notes'] ?? '—')) ?></dd>
      </dl>
    </div></div>

    <?php if (has_role('admin','dpo')): ?>
    <div class="card shadow-sm mb-3"><div class="card-body">
      <h5 class="card-title">Reassign category (B3)</h5>
      <form method="post" action="<?= APP_URL ?>/records/reassign">
        <?= csrf_field() ?>
        <input type="hidden" name="record_id" value="<?= $id ?>">
        <div class="row g-2 align-items-end">
          <div class="col-md-6"><label class="form-label">New category</label>
            <select name="new_category_id" class="form-select" required>
              <?php foreach ($allCats as $c): ?><option value="<?= (int)$c['id'] ?>" <?= (int)$c['id']===(int)$record['category_id']?'selected':'' ?>><?= escape_html($c['name']) ?></option><?php endforeach; ?>
            </select></div>
          <div class="col-md-4"><div class="form-check mt-4"><input type="checkbox" class="form-check-input" id="recalc" name="recalculate" value="1" checked><label class="form-check-label" for="recalc">Recalculate end date</label></div></div>
          <div class="col-md-2"><button class="btn btn-outline-primary w-100">Reassign</button></div>
        </div>
      </form>
    </div></div>
    <?php endif; ?>
  </div>

  <div class="col-lg-5">
    <div class="card shadow-sm mb-3"><div class="card-body">
      <h5 class="card-title">Audit history</h5>
      <?php if (empty($auditRows)): ?><p class="text-muted mb-0">No audit entries.</p><?php else: ?>
      <ul class="list-unstyled small mb-0">
        <?php foreach ($auditRows as $a): ?>
          <li class="border-bottom py-1"><code><?= escape_html($a['action']) ?></code> · <?= escape_html(format_datetime($a['created_at'])) ?></li>
        <?php endforeach; ?>
      </ul>
      <?php endif; ?>
    </div></div>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
