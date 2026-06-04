<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/dsar_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
$id = (int) ($_GET['id'] ?? 0);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $do = $_POST['do'] ?? '';
    try {
        if ($do === 'verify') { verify_dsar_identity($pdo, $id, (int) current_user()['id']); flash('success', 'Identity verified.'); }
        elseif ($do === 'status') { update_dsar_status($pdo, $id, $_POST['status'] ?? 'open', (int) current_user()['id'], trim($_POST['response_notes'] ?? '') ?: null); flash('success', 'DSAR updated.'); }
    } catch (Throwable $e) { flash('error', $e->getMessage()); }
    redirect(APP_URL . '/dsar/view?id=' . $id);
}

$d = fetch_dsar($pdo, $id);
if ($d === null) { http_response_code(404); require __DIR__ . '/../../../404.php'; exit; }
$page_title = 'DSAR ' . $d['reference'];
$active_nav = 'dsar';
require __DIR__ . '/../../includes/layout_header.php';
$overdue = $d['due_date'] < date('Y-m-d') && !in_array($d['status'], ['completed','rejected'], true);
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0"><?= escape_html($d['reference']) ?> <span class="badge bg-secondary"><?= escape_html(str_replace('_',' ',$d['status'])) ?></span></h1>
  <a href="<?= APP_URL ?>/dsar" class="btn btn-secondary">Back</a>
</div>
<?php if ($overdue): ?><div class="alert alert-danger">⚠️ This DSAR is overdue (due <?= escape_html(format_date($d['due_date'])) ?>).</div><?php endif; ?>
<div class="row g-3">
  <div class="col-lg-7"><div class="card shadow-sm"><div class="card-body">
    <h5 class="card-title">Request details</h5>
    <dl class="row mb-0">
      <dt class="col-sm-4">Type</dt><dd class="col-sm-8"><?= escape_html(ucfirst($d['request_type'])) ?> (<?= escape_html($d['compliance_framework']) ?>)</dd>
      <dt class="col-sm-4">Data subject</dt><dd class="col-sm-8"><?= escape_html($d['data_subject_name']) ?></dd>
      <dt class="col-sm-4">Email / phone</dt><dd class="col-sm-8"><?= escape_html($d['data_subject_email'] ?? '—') ?> / <?= escape_html($d['data_subject_phone'] ?? '—') ?></dd>
      <dt class="col-sm-4">Received</dt><dd class="col-sm-8"><?= escape_html(format_date($d['received_date'])) ?></dd>
      <dt class="col-sm-4">Due (30 days)</dt><dd class="col-sm-8"><?= escape_html(format_date($d['due_date'])) ?></dd>
      <dt class="col-sm-4">Identity verified</dt><dd class="col-sm-8"><?= (int)$d['identity_verified'] ? '✅ Yes' : '❌ No' ?></dd>
      <dt class="col-sm-4">Description</dt><dd class="col-sm-8"><?= nl2br(escape_html($d['description'] ?? '—')) ?></dd>
      <dt class="col-sm-4">Response notes</dt><dd class="col-sm-8"><?= nl2br(escape_html($d['response_notes'] ?? '—')) ?></dd>
    </dl>
  </div></div></div>
  <div class="col-lg-5">
    <?php if (!(int)$d['identity_verified']): ?>
    <div class="card shadow-sm mb-3"><div class="card-body">
      <h6>Identity verification</h6>
      <form method="post"><?= csrf_field() ?><input type="hidden" name="do" value="verify">
        <button class="btn btn-outline-primary btn-sm">Mark identity verified</button></form>
    </div></div>
    <?php endif; ?>
    <div class="card shadow-sm"><div class="card-body">
      <h6>Update status</h6>
      <form method="post"><?= csrf_field() ?><input type="hidden" name="do" value="status">
        <select name="status" class="form-select form-select-sm mb-2">
          <?php foreach (['open','identity_check','in_progress','extended','completed','rejected'] as $s): ?>
            <option value="<?= $s ?>" <?= $d['status']===$s?'selected':'' ?>><?= ucfirst(str_replace('_',' ',$s)) ?></option>
          <?php endforeach; ?>
        </select>
        <textarea name="response_notes" class="form-control form-control-sm mb-2" rows="3" placeholder="Response notes"><?= escape_html($d['response_notes'] ?? '') ?></textarea>
        <button class="btn btn-primary btn-sm">Save</button>
      </form>
    </div></div>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
