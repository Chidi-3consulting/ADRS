<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/compliance_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    if (trim($_POST['data_subject_ref'] ?? '') === '' || trim($_POST['purpose'] ?? '') === '') { $error = 'Data subject reference and purpose are required.'; }
    else {
        issue_consent_receipt($pdo, [
            'record_id' => (int) ($_POST['record_id'] ?? 0),
            'data_subject_ref' => trim($_POST['data_subject_ref']),
            'purpose' => trim($_POST['purpose']),
            'lawful_basis' => trim($_POST['lawful_basis'] ?? 'consent'),
            'channel' => trim($_POST['channel'] ?? ''),
            'given_at' => $_POST['given_at'] ? str_replace('T', ' ', $_POST['given_at']) . ':00' : date('Y-m-d H:i:s'),
        ], (int) current_user()['id']);
        flash('success', 'Consent receipt issued.');
        redirect(APP_URL . '/consent-receipts');
    }
}
$page_title = 'New Consent Receipt';
$active_nav = 'consent_receipts';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:620px"><div class="card-body">
  <h1 class="h4 mb-3">Issue Consent Receipt</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Data subject reference *</label><input name="data_subject_ref" class="form-control" required value="<?= escape_html($_POST['data_subject_ref'] ?? '') ?>"></div>
    <div class="mb-3"><label class="form-label">Purpose *</label><input name="purpose" class="form-control" required value="<?= escape_html($_POST['purpose'] ?? '') ?>"></div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Lawful basis</label><input name="lawful_basis" class="form-control" value="<?= escape_html($_POST['lawful_basis'] ?? 'consent') ?>"></div>
      <div class="col-md-6 mb-3"><label class="form-label">Channel</label><input name="channel" class="form-control" placeholder="web / paper / phone" value="<?= escape_html($_POST['channel'] ?? '') ?>"></div>
    </div>
    <div class="mb-3"><label class="form-label">Given at</label><input type="datetime-local" name="given_at" class="form-control" value="<?= escape_html($_POST['given_at'] ?? date('Y-m-d\TH:i')) ?>"></div>
    <button class="btn btn-primary">Issue receipt</button>
    <a href="<?= APP_URL ?>/consent-receipts" class="btn btn-secondary ms-2">Cancel</a>
  </form>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
