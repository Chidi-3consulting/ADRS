<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    if (($_POST['action'] ?? '') === 'process') {
        $r = process_disposal_dispatches($pdo, 100);
        flash('success', "Dispatch run: sent {$r['sent']}, failed {$r['failed']}.");
    }
    redirect(APP_URL . '/integrations/dispatch');
}
$orgId = require_org_id();
$cntStmt = $pdo->prepare('SELECT COUNT(*) FROM disposal_dispatches WHERE organization_id = :o');
$cntStmt->execute(['o' => $orgId]);
$pg = paginate((int) $cntStmt->fetchColumn(), 50, (int) ($_GET['page'] ?? 1));
$listStmt = $pdo->prepare(
    "SELECT dd.*, cs.name AS system_name FROM disposal_dispatches dd
     LEFT JOIN connected_systems cs ON cs.id = dd.system_id
     WHERE dd.organization_id = :o ORDER BY dd.id DESC LIMIT {$pg['per_page']} OFFSET {$pg['offset']}"
);
$listStmt->execute(['o' => $orgId]);
$rows = $listStmt->fetchAll();
$page_title = 'Disposal Dispatch';
$active_nav = 'integrations';
require __DIR__ . '/../../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Outbound Disposal Dispatch</h1>
  <form method="post"><?= csrf_field() ?><input type="hidden" name="action" value="process"><button class="btn btn-primary btn-sm">Send pending now</button></form>
</div>
<p class="text-muted">When records governed by ADRS are disposed, instructions are POSTed to the originating connected system's webhook (<code>{base_url}/adrs/disposal</code>).</p>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($rows)): ?><p class="text-muted mb-0">No dispatches yet.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-sm table-hover align-middle">
    <thead><tr><th>#</th><th>Record ref</th><th>System</th><th>Type</th><th>Status</th><th>HTTP</th><th>Attempts</th><th>Created</th></tr></thead>
    <tbody>
    <?php foreach ($rows as $d): ?>
      <tr>
        <td><?= (int)$d['id'] ?></td>
        <td class="small"><?= escape_html($d['external_ref'] ?? ('#'.$d['record_id'])) ?></td>
        <td class="small"><?= escape_html($d['system_name'] ?? '—') ?></td>
        <td><?= escape_html($d['dispatch_type']) ?></td>
        <td><span class="badge bg-<?= $d['status']==='confirmed'?'success':($d['status']==='failed'?'danger':'secondary') ?>"><?= escape_html($d['status']) ?></span></td>
        <td><?= $d['response_code'] ? (int)$d['response_code'] : '—' ?></td>
        <td><?= (int)$d['attempts'] ?></td>
        <td class="small"><?= escape_html(format_datetime($d['created_at'])) ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <div class="d-flex justify-content-end mt-2"><?= pagination_links($pg, APP_URL . '/integrations/dispatch') ?></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../../includes/layout_footer.php'; ?>
