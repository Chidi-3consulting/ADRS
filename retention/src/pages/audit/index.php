<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_role('admin', 'dpo');
$pdo = get_db();

$action = trim($_GET['action'] ?? '');
$entity = trim($_GET['entity_type'] ?? '');
$from   = trim($_GET['from'] ?? '');
$to     = trim($_GET['to'] ?? '');

$where = []; $params = [];
if ($action !== '') { $where[] = 'al.action = :action'; $params['action'] = $action; }
if ($entity !== '') { $where[] = 'al.entity_type = :entity'; $params['entity'] = $entity; }
if ($from !== '')   { $where[] = 'al.created_at >= :from'; $params['from'] = $from . ' 00:00:00'; }
if ($to !== '')     { $where[] = 'al.created_at <= :to'; $params['to'] = $to . ' 23:59:59'; }
$sql = 'SELECT al.*, u.name AS performed_by_name FROM audit_log al LEFT JOIN users u ON al.performed_by = u.id';
if ($where) { $sql .= ' WHERE ' . implode(' AND ', $where); }
$sql .= ' ORDER BY al.id DESC LIMIT 300';
$stmt = $pdo->prepare($sql);
$stmt->execute($params);
$rows = $stmt->fetchAll();

$actions = $pdo->query("SELECT DISTINCT action FROM audit_log ORDER BY action")->fetchAll(PDO::FETCH_COLUMN);
$integrity = isset($_GET['verify']) ? verify_audit_chain($pdo) : null;

$page_title = 'Audit Log';
$active_nav = 'audit';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div><h1 class="h4 mb-0">Audit Log</h1><p class="text-muted mb-0 small">Immutable, append-only compliance evidence — tamper-evident hash chain.</p></div>
  <div>
    <a href="<?= APP_URL ?>/audit?verify=1" class="btn btn-outline-secondary"><i class="bi bi-shield-check"></i> Verify integrity</a>
    <a href="<?= APP_URL ?>/audit/export" class="btn btn-outline-primary"><i class="bi bi-download"></i> NDPR Annual Report</a>
  </div>
</div>
<?php if ($integrity !== null): ?>
  <?php if ($integrity['ok']): ?>
    <div class="alert alert-success">✅ <strong>Integrity verified.</strong> All <?= (int) $integrity['checked'] ?> audit entries form an unbroken hash chain — no record has been altered or deleted.</div>
  <?php else: ?>
    <div class="alert alert-danger">🔴 <strong>Integrity check FAILED.</strong> The hash chain breaks at audit entry #<?= (int) $integrity['broken_at'] ?> — a record may have been altered or deleted. Investigate immediately.</div>
  <?php endif; ?>
<?php endif; ?>
<form class="card shadow-sm mb-3" method="get"><div class="card-body row g-2 align-items-end">
  <div class="col-md-3"><label class="form-label small">Action</label>
    <select name="action" class="form-select form-select-sm"><option value="">All</option>
      <?php foreach ($actions as $a): ?><option value="<?= escape_html($a) ?>" <?= $a===$action?'selected':'' ?>><?= escape_html($a) ?></option><?php endforeach; ?>
    </select></div>
  <div class="col-md-3"><label class="form-label small">Entity</label>
    <select name="entity_type" class="form-select form-select-sm"><option value="">All</option>
      <?php foreach (['data_record','data_category','user','dsar','attachment','notification','system'] as $e): ?><option value="<?= $e ?>" <?= $e===$entity?'selected':'' ?>><?= $e ?></option><?php endforeach; ?>
    </select></div>
  <div class="col-md-2"><label class="form-label small">From</label><input type="date" name="from" class="form-control form-control-sm" value="<?= escape_html($from) ?>"></div>
  <div class="col-md-2"><label class="form-label small">To</label><input type="date" name="to" class="form-control form-control-sm" value="<?= escape_html($to) ?>"></div>
  <div class="col-md-2"><button class="btn btn-primary btn-sm w-100">Filter</button></div>
</div></form>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($rows)): ?><p class="text-muted mb-0">No matching audit entries.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle small">
    <thead><tr><th>When</th><th>Action</th><th>Entity</th><th>By</th><th>IP</th><th>Details</th></tr></thead>
    <tbody>
    <?php foreach ($rows as $r): ?>
      <tr>
        <td class="text-nowrap"><?= escape_html(format_datetime($r['created_at'])) ?></td>
        <td><code><?= escape_html($r['action']) ?></code></td>
        <td><?= escape_html($r['entity_type']) ?><?= $r['entity_id'] ? ' #' . (int)$r['entity_id'] : '' ?></td>
        <td><?= escape_html($r['performed_by_name'] ?? 'Automated') ?></td>
        <td><?= escape_html($r['ip_address'] ?? '—') ?></td>
        <td><?= $r['details'] ? '<code class="small">' . escape_html($r['details']) . '</code>' : '—' ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
