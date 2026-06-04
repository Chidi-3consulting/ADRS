<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/compliance_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    if (($_POST['action'] ?? '') === 'withdraw') {
        withdraw_consent_receipt($pdo, (int) $_POST['id'], (int) current_user()['id']);
        flash('success', 'Consent receipt marked withdrawn.');
    }
    redirect(APP_URL . '/consent-receipts');
}
$rows = $pdo->query("SELECT * FROM consent_receipts ORDER BY id DESC LIMIT 300")->fetchAll();
$page_title = 'Consent Receipts';
$active_nav = 'consent_receipts';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Consent Receipts</h1>
  <a href="<?= APP_URL ?>/consent-receipts/create" class="btn btn-primary btn-sm">New receipt</a>
</div>
<p class="text-muted">Evidence of consent given (and withdrawn) by data subjects — each receipt has a tamper-evident hash.</p>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($rows)): ?><p class="text-muted mb-0">No consent receipts yet.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Subject</th><th>Purpose</th><th>Basis</th><th>Channel</th><th>Given</th><th>Status</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($rows as $r): ?>
      <tr>
        <td><?= escape_html($r['data_subject_ref']) ?></td>
        <td><?= escape_html($r['purpose']) ?></td>
        <td class="small"><?= escape_html($r['lawful_basis'] ?? '—') ?></td>
        <td class="small"><?= escape_html($r['channel'] ?? '—') ?></td>
        <td class="small"><?= escape_html(format_datetime($r['given_at'])) ?></td>
        <td><?= $r['withdrawn_at'] ? '<span class="badge bg-secondary">withdrawn</span>' : '<span class="badge bg-success">active</span>' ?></td>
        <td><?php if (!$r['withdrawn_at']): ?><form method="post" onsubmit="return confirm('Mark consent withdrawn?')"><?= csrf_field() ?><input type="hidden" name="action" value="withdraw"><input type="hidden" name="id" value="<?= (int)$r['id'] ?>"><button class="btn btn-sm btn-outline-warning">Withdraw</button></form><?php endif; ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
