<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/compliance_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    if (($_POST['action'] ?? '') === 'status') {
        try { set_dpia_status($pdo, (int) $_POST['id'], $_POST['status'] ?? 'draft', (int) current_user()['id']); flash('success', 'DPIA status updated.'); }
        catch (Throwable $e) { flash('error', $e->getMessage()); }
    }
    redirect(APP_URL . '/dpia');
}
$rows = $pdo->query("SELECT d.*, c.name AS category_name FROM dpia_assessments d LEFT JOIN data_categories c ON c.id=d.category_id ORDER BY d.id DESC")->fetchAll();
$page_title = 'DPIA';
$active_nav = 'dpia';
require __DIR__ . '/../../includes/layout_header.php';
$riskBadge = fn($l) => '<span class="badge bg-' . (['low'=>'success','medium'=>'warning','high'=>'danger'][$l] ?? 'secondary') . '">' . escape_html(ucfirst($l)) . '</span>';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Data Protection Impact Assessments</h1>
  <a href="<?= APP_URL ?>/dpia/create" class="btn btn-primary btn-sm">New DPIA</a>
</div>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($rows)): ?><p class="text-muted mb-0">No DPIAs yet.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Title</th><th>Category</th><th>Risk</th><th>Score</th><th>Status</th><th>Set status</th></tr></thead>
    <tbody>
    <?php foreach ($rows as $d): ?>
      <tr>
        <td><?= escape_html($d['title']) ?></td>
        <td class="small"><?= escape_html($d['category_name'] ?? '—') ?></td>
        <td><?= $riskBadge($d['risk_level']) ?></td>
        <td><?= (int)$d['risk_score'] ?>/25</td>
        <td><span class="badge bg-secondary"><?= escape_html(str_replace('_',' ',$d['status'])) ?></span></td>
        <td>
          <form method="post" class="d-flex gap-1"><?= csrf_field() ?><input type="hidden" name="action" value="status"><input type="hidden" name="id" value="<?= (int)$d['id'] ?>">
            <select name="status" class="form-select form-select-sm" style="width:auto"><?php foreach (['draft','in_review','approved','rejected'] as $s): ?><option value="<?= $s ?>" <?= $d['status']===$s?'selected':'' ?>><?= str_replace('_',' ',$s) ?></option><?php endforeach; ?></select>
            <button class="btn btn-sm btn-outline-primary">Set</button>
          </form>
        </td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
