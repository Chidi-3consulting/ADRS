<?php
require_once __DIR__ . '/../config/database.php';
$page_title = 'Dashboard';
$active_nav = 'dashboard';
require __DIR__ . '/../includes/layout_header.php';
$pdo = $__pdo;
$ownerScope = has_role('data_owner') ? ' AND dc.owner_id = ' . (int) $__user['id'] : '';

$k = $pdo->query(
    "SELECT
       SUM(dr.status != 'disposed') AS active,
       SUM(dr.status = 'due_review') AS due_review,
       SUM(dr.retention_end_date < CURDATE() AND dr.status != 'disposed') AS overdue,
       SUM(dr.escalation_sent_at IS NOT NULL AND dr.status='due_review') AS escalated,
       SUM(dr.legal_hold = 1) AS on_hold,
       SUM(dr.status = 'disposed' AND MONTH(dr.disposed_at)=MONTH(CURDATE()) AND YEAR(dr.disposed_at)=YEAR(CURDATE())) AS disposed_month
     FROM data_records dr JOIN data_categories dc ON dc.id = dr.category_id AND dc.deleted_at IS NULL
     WHERE dr.deleted_at IS NULL{$ownerScope}"
)->fetch();

$isStaff = has_role('admin', 'dpo');
$openDsar = $isStaff ? (int) $pdo->query("SELECT COUNT(*) c FROM dsar_requests WHERE status NOT IN ('completed','rejected')")->fetch()['c'] : 0;
$overdueDsar = $isStaff ? (int) $pdo->query("SELECT COUNT(*) c FROM dsar_requests WHERE status NOT IN ('completed','rejected') AND due_date < CURDATE()")->fetch()['c'] : 0;
$pendingRecalc = $isStaff ? (int) $pdo->query("SELECT COUNT(*) c FROM pending_recalculations WHERE status='pending'")->fetch()['c'] : 0;
$recent = $isStaff ? $pdo->query("SELECT al.*, u.name pbn FROM audit_log al LEFT JOIN users u ON u.id=al.performed_by ORDER BY al.id DESC LIMIT 8")->fetchAll() : [];

function dash_card(string $label, int $val, string $cls, string $href = ''): string {
    $inner = '<div class="card shadow-sm h-100"><div class="card-body"><div class="text-muted small">' . escape_html($label)
        . '</div><div class="h3 mb-0 ' . $cls . '">' . $val . '</div></div></div>';
    return '<div class="col-6 col-md-3 mb-3">' . ($href ? '<a class="text-decoration-none" href="' . $href . '">' . $inner . '</a>' : $inner) . '</div>';
}
?>
<h1 class="h4 mb-1">Compliance Dashboard</h1>
<p class="text-muted">Welcome, <?= escape_html($__user['name']) ?> · <?= get_role_badge($__user['role']) ?></p>

<div class="row">
  <?= dash_card('Active records', (int)$k['active'], 'text-dark', APP_URL.'/records') ?>
  <?= dash_card('Due for review', (int)$k['due_review'], 'text-warning', APP_URL.'/records') ?>
  <?= dash_card('Overdue', (int)$k['overdue'], 'text-danger') ?>
  <?= dash_card('On legal hold', (int)$k['on_hold'], 'text-dark') ?>
</div>
<div class="row">
  <?= dash_card('Escalated', (int)$k['escalated'], 'text-danger') ?>
  <?= dash_card('Disposed this month', (int)$k['disposed_month'], 'text-secondary') ?>
  <?php if ($isStaff): ?>
    <?= dash_card('Open DSARs', $openDsar, $overdueDsar > 0 ? 'text-danger' : 'text-dark', APP_URL.'/dsar') ?>
    <?= dash_card('Recalc. pending', $pendingRecalc, $pendingRecalc > 0 ? 'text-warning' : 'text-dark', APP_URL.'/recalculations') ?>
  <?php endif; ?>
</div>

<?php if ($isStaff): ?>
<div class="card shadow-sm mt-2"><div class="card-body">
  <h2 class="h6 text-muted">Recent activity</h2>
  <?php if (empty($recent)): ?><p class="text-muted mb-0">No activity yet.</p><?php else: ?>
  <ul class="list-unstyled small mb-0">
    <?php foreach ($recent as $a): ?>
      <li class="border-bottom py-1"><code><?= escape_html($a['action']) ?></code>
        — <?= escape_html($a['pbn'] ?? 'Automated') ?> · <?= escape_html(format_datetime($a['created_at'])) ?></li>
    <?php endforeach; ?>
  </ul>
  <?php endif; ?>
</div></div>
<?php endif; ?>
<?php require __DIR__ . '/../includes/layout_footer.php'; ?>
