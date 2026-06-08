<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $action = $_POST['action'] ?? '';
    if ($action === 'process') {
        $r = process_intake_queue($pdo, 200);
        flash('success', "Processed {$r['processed']}: created {$r['created']}, duplicate {$r['duplicate']}, failed {$r['failed']}.");
    } elseif ($action === 'retry_failed') {
        $n = $pdo->exec("UPDATE intake_queue SET status='pending', attempts=0, error=NULL WHERE status='failed'");
        flash('success', "Re-queued {$n} failed item(s).");
    }
    redirect(APP_URL . '/integrations/queue');
}

$pg = paginate((int) $pdo->query("SELECT COUNT(*) FROM intake_queue")->fetchColumn(), 50, (int) ($_GET['page'] ?? 1));
$rows = $pdo->query(
    "SELECT iq.*, cs.name AS system_name FROM intake_queue iq LEFT JOIN connected_systems cs ON cs.id=iq.system_id ORDER BY iq.id DESC LIMIT {$pg['per_page']} OFFSET {$pg['offset']}"
)->fetchAll();
$counts = $pdo->query("SELECT status, COUNT(*) c FROM intake_queue GROUP BY status")->fetchAll(PDO::FETCH_KEY_PAIR);
$page_title = 'Intake Queue';
$active_nav = 'integrations';
require __DIR__ . '/../../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Intake Queue</h1>
  <div class="d-flex gap-2">
    <form method="post"><?= csrf_field() ?><input type="hidden" name="action" value="process"><button class="btn btn-primary btn-sm">Process now</button></form>
    <form method="post" data-confirm="Re-queue all failed items?"><?= csrf_field() ?><input type="hidden" name="action" value="retry_failed"><button class="btn btn-outline-warning btn-sm">Retry failed</button></form>
  </div>
</div>
<p class="text-muted">
  <?php foreach (['pending','completed','failed','duplicate'] as $st): ?>
    <span class="badge bg-secondary"><?= $st ?>: <?= (int)($counts[$st] ?? 0) ?></span>
  <?php endforeach; ?>
</p>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($rows)): ?><p class="text-muted mb-0">Queue is empty.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-sm table-hover align-middle">
    <thead><tr><th>#</th><th>System</th><th>Status</th><th>Record</th><th>Error</th><th>Attempts</th><th>Created</th></tr></thead>
    <tbody>
    <?php foreach ($rows as $r): ?>
      <tr>
        <td><?= (int)$r['id'] ?></td>
        <td class="small"><?= escape_html($r['system_name'] ?? '—') ?></td>
        <td><span class="badge bg-<?= $r['status']==='completed'?'success':($r['status']==='failed'?'danger':'secondary') ?>"><?= escape_html($r['status']) ?></span></td>
        <td><?= $r['record_id'] ? '#'.(int)$r['record_id'] : '—' ?></td>
        <td class="small text-danger"><?= escape_html($r['error'] ?? '') ?></td>
        <td><?= (int)$r['attempts'] ?></td>
        <td class="small"><?= escape_html(format_datetime($r['created_at'])) ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <div class="d-flex justify-content-end mt-2"><?= pagination_links($pg, APP_URL . '/integrations/queue') ?></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../../includes/layout_footer.php'; ?>
