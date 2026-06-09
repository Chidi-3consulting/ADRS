<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
require_enterprise($pdo);
$orgId = require_org_id();
$dir = in_array($_GET['direction'] ?? '', ['inbound','outbound'], true) ? $_GET['direction'] : '';
$where = ['l.organization_id = :o'];
$params = ['o' => $orgId];
if ($dir) { $where[] = 'l.direction = :dir'; $params['dir'] = $dir; }
$whereSql = ' WHERE ' . implode(' AND ', $where);
$cntStmt = $pdo->prepare("SELECT COUNT(*) FROM integration_logs l$whereSql");
$cntStmt->execute($params);
$pg = paginate((int) $cntStmt->fetchColumn(), 50, (int) ($_GET['page'] ?? 1));
$logStmt = $pdo->prepare(
    "SELECT l.*, cs.name AS system_name FROM integration_logs l
     LEFT JOIN connected_systems cs ON cs.id = l.system_id$whereSql
     ORDER BY l.id DESC LIMIT {$pg['per_page']} OFFSET {$pg['offset']}"
);
$logStmt->execute($params);
$logs = $logStmt->fetchAll();
$page_title = 'Integration Logs';
$active_nav = 'integrations';
require __DIR__ . '/../../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Integration Logs</h1>
  <div class="btn-group btn-group-sm">
    <a href="<?= APP_URL ?>/integrations/logs" class="btn btn-outline-secondary <?= $dir===''?'active':'' ?>">All</a>
    <a href="<?= APP_URL ?>/integrations/logs?direction=inbound" class="btn btn-outline-secondary <?= $dir==='inbound'?'active':'' ?>">Inbound</a>
    <a href="<?= APP_URL ?>/integrations/logs?direction=outbound" class="btn btn-outline-secondary <?= $dir==='outbound'?'active':'' ?>">Outbound</a>
  </div>
</div>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($logs)): ?><p class="text-muted mb-0">No API calls logged yet.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-sm table-hover align-middle">
    <thead><tr><th>When</th><th>Dir</th><th>System</th><th>Endpoint</th><th>Method</th><th>Status</th><th>ms</th></tr></thead>
    <tbody>
    <?php foreach ($logs as $l): ?>
      <tr>
        <td class="small text-nowrap"><?= escape_html(format_datetime($l['created_at'])) ?></td>
        <td><?= escape_html($l['direction']) ?></td>
        <td class="small"><?= escape_html($l['system_name'] ?? '—') ?></td>
        <td class="small"><code><?= escape_html($l['endpoint']) ?></code></td>
        <td><?= escape_html($l['method']) ?></td>
        <td><span class="badge bg-<?= (int)$l['status_code']<400 ? 'success':'danger' ?>"><?= (int)$l['status_code'] ?></span></td>
        <td class="small"><?= (int)$l['duration_ms'] ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <div class="d-flex justify-content-between align-items-center mt-2"><span class="text-muted small"><?= (int) $pg['total'] ?> total</span><?= pagination_links($pg, APP_URL . '/integrations/logs', $dir ? ['direction' => $dir] : []) ?></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../../includes/layout_footer.php'; ?>
