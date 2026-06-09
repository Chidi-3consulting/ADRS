<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/compliance_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    if (($_POST['action'] ?? '') === 'status') {
        try { update_breach_status($pdo, (int) $_POST['id'], $_POST['status'] ?? 'open', (int) current_user()['id']); flash('success', 'Breach status updated.'); }
        catch (Throwable $e) { flash('error', $e->getMessage()); }
    }
    redirect(APP_URL . '/breaches');
}
$orgId = require_org_id();
$stmt = $pdo->prepare('SELECT * FROM breach_incidents WHERE organization_id = :o ORDER BY id DESC');
$stmt->execute(['o' => $orgId]);
$rows = $stmt->fetchAll();
$page_title = 'Breach Register';
$active_nav = 'breaches';
require __DIR__ . '/../../includes/layout_header.php';
$sevBadge = fn($s) => '<span class="badge bg-' . (['low'=>'secondary','medium'=>'warning','high'=>'danger','critical'=>'dark'][$s] ?? 'secondary') . '">' . escape_html($s) . '</span>';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Data Breach Register</h1>
  <a href="<?= APP_URL ?>/breaches/create" class="btn btn-danger btn-sm">Log breach</a>
</div>
<p class="text-muted">GDPR Art. 33 requires notifying the supervisory authority within <strong>72 hours</strong> of becoming aware of a breach.</p>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($rows)): ?><p class="text-muted mb-0">No breaches recorded. 🎉</p><?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Ref</th><th>Title</th><th>Severity</th><th>Status</th><th>72h deadline</th><th>Set status</th></tr></thead>
    <tbody>
    <?php foreach ($rows as $b): $hrs = breach_hours_remaining($b['notify_deadline']); $notified = $b['notified_authority_at'] !== null; ?>
      <tr>
        <td><code><?= escape_html($b['reference']) ?></code></td>
        <td><?= escape_html($b['title']) ?></td>
        <td><?= $sevBadge($b['severity']) ?></td>
        <td><span class="badge bg-secondary"><?= escape_html($b['status']) ?></span></td>
        <td><?php if ($notified): ?><span class="text-success">notified</span><?php elseif ($hrs < 0): ?><span class="text-danger fw-bold">OVERDUE (<?= abs($hrs) ?>h ago)</span><?php else: ?><span class="<?= $hrs<=24?'text-danger':'text-warning' ?>"><?= $hrs ?>h left</span><?php endif; ?></td>
        <td>
          <form method="post" class="d-flex gap-1"><?= csrf_field() ?><input type="hidden" name="action" value="status"><input type="hidden" name="id" value="<?= (int)$b['id'] ?>">
            <select name="status" class="form-select form-select-sm" style="width:auto"><?php foreach (['open','contained','notified','closed'] as $s): ?><option value="<?= $s ?>" <?= $b['status']===$s?'selected':'' ?>><?= $s ?></option><?php endforeach; ?></select>
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
