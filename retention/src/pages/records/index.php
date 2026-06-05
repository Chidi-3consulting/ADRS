<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_login();
$pdo = get_db();
$me = current_user();
$ownerFilter = has_role('data_owner') ? ' AND dc.owner_id = ' . (int) $me['id'] : '';

// Global KPI summary (unfiltered).
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

// Filters
$q        = trim($_GET['q'] ?? '');
$status   = $_GET['status'] ?? '';
$catId    = (int) ($_GET['category_id'] ?? 0);
$statuses = ['active','due_review','disposal_requested','legal_hold','disposed','overdue'];
$where = []; $params = [];
// Disposed view includes soft-deleted (delete-method) records; everything else excludes them.
if ($status !== 'disposed') { $where[] = 'dr.deleted_at IS NULL'; }
if ($q !== '')    { $where[] = '(dr.record_reference LIKE :q OR dr.data_subject_type LIKE :q)'; $params['q'] = '%' . $q . '%'; }
if ($catId > 0)   { $where[] = 'dr.category_id = :cat'; $params['cat'] = $catId; }
if ($status === 'overdue')      { $where[] = "dr.retention_end_date < CURDATE() AND dr.status != 'disposed'"; }
elseif (in_array($status, $statuses, true)) { $where[] = 'dr.status = :st'; $params['st'] = $status; }
if (has_role('data_owner'))     { $where[] = 'dc.owner_id = ' . (int) $me['id']; }
$whereSql = $where ? (' WHERE ' . implode(' AND ', $where)) : '';

$countStmt = $pdo->prepare("SELECT COUNT(*) FROM data_records dr JOIN data_categories dc ON dc.id = dr.category_id$whereSql");
$countStmt->execute($params);
$total = (int) $countStmt->fetchColumn();
$pg = paginate($total, 25, (int) ($_GET['page'] ?? 1));

$listStmt = $pdo->prepare(
    "SELECT dr.*, dc.name AS category_name, dc.disposal_trigger
     FROM data_records dr JOIN data_categories dc ON dc.id = dr.category_id$whereSql
     ORDER BY dr.created_at DESC LIMIT {$pg['per_page']} OFFSET {$pg['offset']}"
);
$listStmt->execute($params);
$rows = $listStmt->fetchAll();
$catOptions = $pdo->query("SELECT id, name FROM data_categories WHERE deleted_at IS NULL ORDER BY name")->fetchAll();

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
<form class="card shadow-sm mb-3" method="get"><div class="card-body row g-2 align-items-end">
  <div class="col-md-4"><label class="form-label small mb-1">Search reference / subject</label>
    <input name="q" class="form-control form-control-sm" value="<?= escape_html($q) ?>" placeholder="e.g. CUST-001"></div>
  <div class="col-md-3"><label class="form-label small mb-1">Status</label>
    <select name="status" class="form-select form-select-sm"><option value="">All active</option>
      <?php foreach ($statuses as $s): ?><option value="<?= $s ?>" <?= $status===$s?'selected':'' ?>><?= escape_html(ucwords(str_replace('_',' ',$s))) ?></option><?php endforeach; ?>
    </select></div>
  <div class="col-md-3"><label class="form-label small mb-1">Category</label>
    <select name="category_id" class="form-select form-select-sm"><option value="0">All categories</option>
      <?php foreach ($catOptions as $c): ?><option value="<?= (int)$c['id'] ?>" <?= $catId===(int)$c['id']?'selected':'' ?>><?= escape_html($c['name']) ?></option><?php endforeach; ?>
    </select></div>
  <div class="col-md-2 d-flex gap-1"><button class="btn btn-primary btn-sm flex-grow-1">Filter</button>
    <a href="<?= APP_URL ?>/records" class="btn btn-outline-secondary btn-sm">Reset</a></div>
</div></form>
<div class="card shadow-sm"><div class="card-body">
  <div class="d-flex justify-content-between align-items-center mb-2">
    <span class="text-muted small"><?= $total ?> record<?= $total === 1 ? '' : 's' ?></span>
    <?= pagination_links($pg, APP_URL . '/records', array_filter(['q' => $q, 'status' => $status, 'category_id' => $catId ?: null])) ?>
  </div>
  <?php if (empty($rows)): ?>
    <p class="text-muted mb-0">No records match your filters.</p>
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
  <div class="d-flex justify-content-end mt-2"><?= pagination_links($pg, APP_URL . '/records', array_filter(['q' => $q, 'status' => $status, 'category_id' => $catId ?: null])) ?></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
