<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_login();
$pdo = get_db();
$me = current_user();
$ownerFilter = has_role('data_owner') ? ' AND dc.owner_id = ' . (int) $me['id'] : '';

$kpi = $pdo->query(
    "SELECT
       SUM(status != 'disposed') AS total_active,
       SUM(status = 'due_review') AS due_review,
       SUM(retention_end_date < CURDATE() AND status != 'disposed') AS overdue,
       SUM(legal_hold = 1 OR status = 'legal_hold') AS on_hold,
       SUM(status = 'disposal_requested') AS awaiting_approval,
       SUM(status = 'disposed' AND MONTH(disposed_at)=MONTH(CURDATE()) AND YEAR(disposed_at)=YEAR(CURDATE())) AS disposed_month
     FROM data_records dr JOIN data_categories dc ON dc.id = dr.category_id AND dc.deleted_at IS NULL
     WHERE dr.deleted_at IS NULL{$ownerFilter}"
)->fetch();

$rows = $pdo->query(
    "SELECT dr.*, dc.name AS category_name, dc.disposal_trigger
     FROM data_records dr JOIN data_categories dc ON dc.id = dr.category_id AND dc.deleted_at IS NULL
     WHERE dr.deleted_at IS NULL{$ownerFilter}
     ORDER BY dr.created_at DESC LIMIT 300"
)->fetchAll();

$page_title = 'Retention Schedule';
$active_nav = 'records';
require __DIR__ . '/../../includes/layout_header.php';
function kpi_card(string $label, $val, string $cls = ''): string {
    return '<div class="col"><div class="card shadow-sm"><div class="card-body py-3"><div class="text-muted small">'
        . escape_html($label) . '</div><div class="h4 mb-0 ' . $cls . '">' . (int) $val . '</div></div></div></div>';
}
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Retention Schedule</h1>
  <a href="<?= APP_URL ?>/records/create" class="btn btn-primary"><i class="bi bi-plus-lg"></i> New record</a>
</div>
<div class="row row-cols-2 row-cols-md-6 g-2 mb-3">
  <?= kpi_card('Active', $kpi['total_active']) ?>
  <?= kpi_card('Due review', $kpi['due_review'], 'text-warning') ?>
  <?= kpi_card('Overdue', $kpi['overdue'], 'text-danger') ?>
  <?= kpi_card('On hold', $kpi['on_hold']) ?>
  <?= kpi_card('Awaiting approval', $kpi['awaiting_approval']) ?>
  <?= kpi_card('Disposed (mo)', $kpi['disposed_month']) ?>
</div>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($rows)): ?>
    <p class="text-muted mb-0">No records yet.</p>
  <?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Ref</th><th>Category</th><th>Trigger</th><th>Collection</th><th>Retention end</th><th>Days left</th><th>Status</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($rows as $r): ?>
      <tr>
        <td><?= escape_html($r['record_reference']) ?><?php if ((int)$r['created_by_owner']===1): ?> <span title="Added by Data Owner">👤</span><?php endif; ?></td>
        <td><?= escape_html($r['category_name']) ?></td>
        <td><?= $r['disposal_trigger']==='consent_withdrawal' ? '👤' : '📅' ?></td>
        <td><?= escape_html(format_date($r['collection_date'])) ?></td>
        <td><?= $r['retention_end_date'] ? escape_html(format_date($r['retention_end_date'])) : '<span class="text-muted">— pending withdrawal</span>' ?></td>
        <td><?php
          if ((int)$r['legal_hold']===1) { echo '🔒'; }
          elseif ($r['retention_end_date'] && $r['status']!=='disposed') { $d = days_until($r['retention_end_date']); echo $d < 0 ? '<span class="text-danger">OVERDUE</span>' : $d; }
          else { echo '—'; }
        ?></td>
        <td><?= get_status_badge($r['status']) ?></td>
        <td><a href="<?= APP_URL ?>/records/view?id=<?= (int)$r['id'] ?>" class="btn btn-sm btn-outline-secondary">View</a></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
