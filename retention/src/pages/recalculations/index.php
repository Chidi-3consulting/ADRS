<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/categories_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    try {
        apply_recalculation($pdo, (int) ($_POST['recalc_id'] ?? 0), $_POST['decision'] ?? 'ignored', (int) current_user()['id']);
        flash('success', 'Recalculation decision applied.');
    } catch (Throwable $e) { flash('error', $e->getMessage()); }
    redirect(APP_URL . '/recalculations');
}

$rows = $pdo->query(
    "SELECT pr.*, dr.record_reference, dc.name AS category_name
     FROM pending_recalculations pr
     JOIN data_records dr ON dr.id = pr.record_id
     JOIN data_categories dc ON dc.id = pr.category_id
     WHERE pr.status='pending' ORDER BY pr.id DESC"
)->fetchAll();
$page_title = 'Recalculation Queue';
$active_nav = 'recalculations';
require __DIR__ . '/../../includes/layout_header.php';
?>
<h1 class="h4 mb-1">Recalculation Review Queue</h1>
<p class="text-muted small">When a category's retention period changes, affected records wait here for a DPO decision (B2). No record date changes until you choose.</p>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($rows)): ?><p class="text-muted mb-0">Nothing pending review.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Record</th><th>Category</th><th>Current end</th><th>Proposed end</th><th>Decision</th></tr></thead>
    <tbody>
    <?php foreach ($rows as $r): ?>
      <tr>
        <td><?= escape_html($r['record_reference']) ?></td>
        <td><?= escape_html($r['category_name']) ?></td>
        <td><?= escape_html(format_date($r['old_retention_end_date'])) ?></td>
        <td><?= escape_html(format_date($r['new_retention_end_date'])) ?></td>
        <td>
          <form method="post" class="d-flex gap-1">
            <?= csrf_field() ?><input type="hidden" name="recalc_id" value="<?= (int)$r['id'] ?>">
            <button name="decision" value="recalculate" class="btn btn-sm btn-primary">Apply new</button>
            <button name="decision" value="keep_original" class="btn btn-sm btn-outline-secondary">Keep current</button>
            <button name="decision" value="ignored" class="btn btn-sm btn-outline-secondary">Dismiss</button>
          </form>
        </td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
