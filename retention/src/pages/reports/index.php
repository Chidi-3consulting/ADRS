<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/analytics_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
$m = compliance_metrics($pdo);
$byMonth = disposals_by_month($pdo, 12);
$byCat = records_by_category($pdo, 8);

if (($_GET['export'] ?? '') === 'csv') {
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="adrs_management_report_' . date('Y-m-d') . '.csv"');
    echo "\xEF\xBB\xBF";
    $out = fopen('php://output', 'w');
    fputcsv($out, ['Metric', 'Value']);
    foreach ($m as $k => $v) { fputcsv($out, [ucwords(str_replace('_', ' ', $k)), $v]); }
    fputcsv($out, []); fputcsv($out, ['Month', 'Disposals']);
    foreach ($byMonth as $ym => $c) { fputcsv($out, [$ym, $c]); }
    fclose($out);
    exit;
}

$page_title = 'Analytics & Reports';
$active_nav = 'reports';
require __DIR__ . '/../../includes/layout_header.php';
function rcard($label, $val, $cls = '') { echo '<div class="col-md-3 col-6"><div class="card shadow-sm"><div class="card-body py-3"><div class="text-muted small">' . escape_html($label) . '</div><div class="h3 mb-0 ' . $cls . '">' . (int) $val . '</div></div></div></div>'; }
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Compliance Analytics</h1>
  <div>
    <a href="<?= APP_URL ?>/reports?export=csv" class="btn btn-outline-primary btn-sm">Export CSV</a>
    <button onclick="window.print()" class="btn btn-outline-secondary btn-sm">Print board report</button>
  </div>
</div>
<div class="row g-3 mb-3">
  <?php rcard('Categories', $m['categories']); rcard('Records', $m['records_total']); rcard('Active', $m['records_active']);
        rcard('Disposed', $m['records_disposed']); rcard('Due review', $m['records_due'], 'text-warning');
        rcard('Overdue', $m['overdue'], $m['overdue'] ? 'text-danger' : ''); rcard('Due in 30d', $m['upcoming_30d']);
        rcard('Legal holds', $m['records_hold']); ?>
</div>
<div class="row g-3 mb-3">
  <?php rcard('DSARs open', $m['dsar_open']); rcard('Breaches open', $m['breaches_open'], $m['breaches_open'] ? 'text-danger' : '');
        rcard('High-risk DPIAs', $m['dpia_high'], $m['dpia_high'] ? 'text-danger' : ''); rcard('Audit events', $m['audit_events']); ?>
</div>
<div class="row g-3">
  <div class="col-lg-7"><div class="card shadow-sm"><div class="card-body"><h5 class="card-title">Disposals — last 12 months</h5><canvas id="disposalsChart" height="120"></canvas></div></div></div>
  <div class="col-lg-5"><div class="card shadow-sm"><div class="card-body"><h5 class="card-title">Records by category</h5><canvas id="catChart" height="160"></canvas></div></div></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" integrity="sha384-9nhczxUqK87bcKHh20fSQcTGD4qq5GhayNYSYWqwBkINBhOfQLg/P5HG5lF1urn4" crossorigin="anonymous"></script>
<script>
const dm = <?= json_encode($byMonth) ?>, bc = <?= json_encode($byCat) ?>;
new Chart(document.getElementById('disposalsChart'), {type:'line', data:{labels:Object.keys(dm), datasets:[{label:'Disposals', data:Object.values(dm), borderColor:'#C85C1A', backgroundColor:'rgba(200,92,26,.15)', fill:true, tension:.3}]}, options:{plugins:{legend:{display:false}}}});
new Chart(document.getElementById('catChart'), {type:'bar', data:{labels:Object.keys(bc), datasets:[{label:'Records', data:Object.values(bc), backgroundColor:'#1A6187'}]}, options:{indexAxis:'y', plugins:{legend:{display:false}}}});
</script>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
