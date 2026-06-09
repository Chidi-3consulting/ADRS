<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_role('admin', 'dpo');
$pdo = get_db();
$orgId = require_org_id();
$cstmt = $pdo->prepare('SELECT COUNT(*) FROM dsar_requests WHERE organization_id = :o');
$cstmt->execute(['o' => $orgId]);
$pg = paginate((int) $cstmt->fetchColumn(), 25, (int) ($_GET['page'] ?? 1));
$stmt = $pdo->prepare("SELECT * FROM dsar_requests WHERE organization_id = :o ORDER BY id DESC LIMIT {$pg['per_page']} OFFSET {$pg['offset']}");
$stmt->execute(['o' => $orgId]);
$rows = $stmt->fetchAll();
$page_title = 'DSAR Requests';
$active_nav = 'dsar';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div><h1 class="h4 mb-0">DSAR Requests</h1><p class="text-muted mb-0 small">Right of access, erasure, rectification and more — 30-day GDPR/NDPR clock.</p></div>
  <a href="<?= APP_URL ?>/dsar/create" class="btn btn-primary"><i class="bi bi-plus-lg"></i> New DSAR</a>
</div>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($rows)): ?><p class="text-muted mb-0">No DSARs logged yet.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Reference</th><th>Type</th><th>Subject</th><th>Received</th><th>Due</th><th>Status</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($rows as $d):
      $overdue = $d['due_date'] < date('Y-m-d') && !in_array($d['status'], ['completed','rejected'], true); ?>
      <tr class="<?= $overdue ? 'table-danger' : '' ?>">
        <td><?= escape_html($d['reference']) ?></td>
        <td><?= escape_html(ucfirst($d['request_type'])) ?></td>
        <td><?= escape_html($d['data_subject_name']) ?></td>
        <td><?= escape_html(format_date($d['received_date'])) ?></td>
        <td><?= escape_html(format_date($d['due_date'])) ?><?= $overdue ? ' ⚠️' : '' ?></td>
        <td><span class="badge bg-secondary"><?= escape_html(str_replace('_',' ',$d['status'])) ?></span></td>
        <td><a href="<?= APP_URL ?>/dsar/view?id=<?= (int)$d['id'] ?>" class="btn btn-sm btn-outline-secondary">Open</a></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <div class="d-flex justify-content-between align-items-center mt-2"><span class="text-muted small"><?= (int) $pg['total'] ?> total</span><?= pagination_links($pg, APP_URL . '/dsar') ?></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
