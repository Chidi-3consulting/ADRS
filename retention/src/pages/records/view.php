<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/records_lib.php';
require_login();
$pdo = get_db();
$id = (int) ($_GET['id'] ?? 0);
$record = $id > 0 ? fetch_record($pdo, $id, true) : null;   // include disposed/deleted for read-only viewing
if ($record === null) { http_response_code(404); require __DIR__ . '/../../../404.php'; exit; }
assert_org_row($record);
$isDisposed = $record['status'] === 'disposed' || $record['deleted_at'] !== null;
$orgId = require_org_id();

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
$audit = $pdo->prepare("SELECT * FROM audit_log WHERE organization_id = :o AND entity_type='data_record' AND entity_id=:id ORDER BY id DESC LIMIT 10");
$audit->execute(['o' => $orgId, 'id' => $id]);
$auditRows = $audit->fetchAll();
$allCats = list_org_categories($pdo);
$attStmt = $pdo->prepare("SELECT * FROM attachments WHERE record_id=:id AND deleted_at IS NULL ORDER BY id DESC");
$attStmt->execute(['id' => $id]);
$attachments = $attStmt->fetchAll();
$canAct = has_role('admin', 'dpo') && !$isDisposed;   // no lifecycle actions on a disposed record

$page_title = 'Record ' . $record['record_reference'];
$active_nav = 'records';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0"><?= escape_html($record['record_reference']) ?> <?= get_status_badge($record['status']) ?></h1>
  <div>
    <?php if ($canAct): ?><a href="<?= APP_URL ?>/records/edit?id=<?= $id ?>" class="btn btn-outline-primary">Edit</a><?php endif; ?>
    <a href="<?= APP_URL ?>/records" class="btn btn-secondary">Back</a>
  </div>
</div>
<?php if ($isDisposed): ?>
  <div class="alert alert-secondary">This record has been <strong>disposed</strong><?= $record['disposed_at'] ? ' on ' . escape_html(format_datetime($record['disposed_at'])) : '' ?> (method: <?= escape_html(get_disposal_method_label($record['disposal_method'])) ?>). It is shown read-only as compliance evidence; the immutable audit trail below records the full history.</div>
<?php endif; ?>
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

    <?php if ($canAct): ?>
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
    <?php if ($canAct && $record['status'] !== 'disposed'): ?>
    <div class="card shadow-sm mb-3"><div class="card-body">
      <h5 class="card-title">Actions</h5>

      <?php if ($record['status'] === 'disposal_requested'): ?>
        <div class="alert alert-warning py-2 small">⏳ Awaiting second approval (requested by user #<?= (int)$record['disposal_requested_by'] ?>). A <strong>different</strong> authorised user must confirm.</div>
        <form method="post" action="<?= APP_URL ?>/records/approve" class="d-inline">
          <?= csrf_field() ?><input type="hidden" name="record_id" value="<?= $id ?>"><input type="hidden" name="decision" value="approve">
          <button class="btn btn-danger btn-sm" data-confirm="Confirm disposal of this record?">Approve disposal</button>
        </form>
        <form method="post" action="<?= APP_URL ?>/records/approve" class="d-inline">
          <?= csrf_field() ?><input type="hidden" name="record_id" value="<?= $id ?>"><input type="hidden" name="decision" value="reject">
          <button class="btn btn-outline-secondary btn-sm">Reject</button>
        </form>
      <?php elseif ((int)$record['legal_hold'] !== 1): ?>
        <form method="post" action="<?= APP_URL ?>/records/dispose" class="mb-2">
          <?= csrf_field() ?><input type="hidden" name="record_id" value="<?= $id ?>">
          <button class="btn btn-outline-danger btn-sm" data-confirm="<?= (int)$record['requires_dual_approval'] ? 'This sensitive record needs two-person approval. Submit a disposal request?' : 'Dispose this record now?' ?>">
            <?= (int)$record['requires_dual_approval'] ? 'Request disposal (dual approval)' : 'Dispose record' ?>
          </button>
        </form>
      <?php endif; ?>

      <?php if ($record['disposal_trigger'] === 'consent_withdrawal' && $record['consent_withdrawn_at'] === null && $record['status'] !== 'disposed'): ?>
        <form method="post" action="<?= APP_URL ?>/records/consent" class="mb-2">
          <?= csrf_field() ?><input type="hidden" name="record_id" value="<?= $id ?>">
          <button class="btn btn-outline-warning btn-sm">Log consent withdrawal</button>
        </form>
      <?php endif; ?>

      <?php if ((int)$record['legal_hold'] === 1): ?>
        <form method="post" action="<?= APP_URL ?>/records/legal_hold">
          <?= csrf_field() ?><input type="hidden" name="record_id" value="<?= $id ?>"><input type="hidden" name="action" value="lift">
          <button class="btn btn-outline-secondary btn-sm">Lift legal hold</button>
        </form>
      <?php else: ?>
        <form method="post" action="<?= APP_URL ?>/records/legal_hold" class="mt-2">
          <?= csrf_field() ?><input type="hidden" name="record_id" value="<?= $id ?>">
          <div class="input-group input-group-sm">
            <input name="reason" class="form-control" placeholder="Legal hold reason" required>
            <button class="btn btn-outline-dark">🔒 Hold</button>
          </div>
        </form>
      <?php endif; ?>
    </div></div>
    <?php endif; ?>

    <div class="card shadow-sm mb-3"><div class="card-body">
      <div class="d-flex justify-content-between"><h5 class="card-title">Attachments</h5></div>
      <?php if ($attachments): ?>
        <ul class="list-unstyled small mb-2">
          <?php foreach ($attachments as $a): ?>
            <li class="border-bottom py-1 d-flex justify-content-between">
              <span><?= escape_html($a['original_filename']) ?> <span class="text-muted">(<?= number_format((int)$a['file_size']) ?>b)</span></span>
              <a href="<?= APP_URL ?>/attachments/download?id=<?= (int)$a['id'] ?>">Download</a>
            </li>
          <?php endforeach; ?>
        </ul>
      <?php else: ?><p class="text-muted small">No attachments.</p><?php endif; ?>
      <?php if ($canAct): ?>
      <form method="post" action="<?= APP_URL ?>/attachments/upload" enctype="multipart/form-data" class="input-group input-group-sm">
        <?= csrf_field() ?><input type="hidden" name="record_id" value="<?= $id ?>">
        <input type="file" name="file" class="form-control" required>
        <button class="btn btn-outline-primary">Upload</button>
      </form>
      <?php endif; ?>
    </div></div>

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
