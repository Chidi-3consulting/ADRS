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

function rcard($label, $val, $icon, $cls = '', $subText = '') {
    echo '
    <div class="col-sm-6 col-md-3 mb-3">
      <div class="card hover-lift h-100 stat-card-gradient ' . $cls . '">
        <div class="card-body d-flex justify-content-between align-items-center py-3">
          <div>
            <div class="text-muted small fw-medium">' . escape_html($label) . '</div>
            <div class="h3 mb-0 mt-1 fw-bold">' . (int)$val . '</div>
            ' . ($subText ? '<div class="small text-muted mt-1" style="font-size: 0.75rem;">' . escape_html($subText) . '</div>' : '') . '
          </div>
          <div class="fs-4 text-secondary opacity-50"><i class="bi ' . $icon . '"></i></div>
        </div>
      </div>
    </div>';
}
?>
<div class="d-flex justify-content-between align-items-center mb-4">
  <div>
    <h1 class="h3 mb-1 fw-bold">Compliance Analytics</h1>
    <p class="text-muted mb-0">Platform-wide statistics and historical retention reporting.</p>
  </div>
  <div class="d-flex gap-2 no-print">
    <a href="<?= APP_URL ?>/reports?export=csv" class="btn btn-outline-primary d-inline-flex align-items-center gap-2">
      <i class="bi bi-download"></i> Export CSV
    </a>
    <button onclick="window.print()" class="btn btn-outline-secondary d-inline-flex align-items-center gap-2">
      <i class="bi bi-printer"></i> Print Board Report
    </button>
  </div>
</div>

<!-- Primary Stats Grid -->
<div class="row g-3 mb-4">
  <?php 
    rcard('Total Categories', $m['categories'], 'bi-collection'); 
    rcard('Total Records', $m['records_total'], 'bi-database'); 
    rcard('Active Records', $m['records_active'], 'bi-check-circle-fill');
    rcard('Disposed Records', $m['records_disposed'], 'bi-trash-fill'); 
  ?>
</div>

<div class="row g-3 mb-4">
  <?php 
    rcard('Due for Review', $m['records_due'], 'bi-bell-fill', $m['records_due'] > 0 ? 'yellow' : '', 'Action required'); 
    rcard('Overdue Retention', $m['overdue'], 'bi-exclamation-octagon-fill', $m['overdue'] > 0 ? 'danger' : '', 'Requires signature'); 
    rcard('Due in 30 Days', $m['upcoming_30d'], 'bi-calendar-event', '', 'Approaching review'); 
    rcard('On Legal Hold', $m['records_hold'], 'bi-lock-fill', 'teal', 'Writers block enabled'); 
  ?>
</div>

<!-- Secondary Stats (System Audit) -->
<div class="row g-3 mb-4">
  <div class="col-md-12">
    <div class="card bg-light border-0 shadow-sm"><div class="card-body py-2 d-flex justify-content-between align-items-center">
      <span class="small text-muted font-monospace"><i class="bi bi-shield-check text-success me-2"></i> CRYPTOGRAPHIC INTEGRITY CONTROL ACTIVE</span>
      <span class="small text-dark">Total Chained Audit Events: <strong><?= (int) $m['audit_events'] ?></strong></span>
    </div></div>
  </div>
</div>

<div class="row g-4">
  <!-- Line Chart -->
  <div class="col-lg-7">
    <div class="card shadow-sm h-100">
      <div class="card-body">
        <h5 class="card-title fw-bold text-dark mb-4">Disposals Trend (Last 12 Months)</h5>
        <div style="position: relative; height: 320px;">
          <canvas id="disposalsChart"></canvas>
        </div>
      </div>
    </div>
  </div>

  <!-- Bar Chart -->
  <div class="col-lg-5">
    <div class="card shadow-sm h-100">
      <div class="card-body">
        <h5 class="card-title fw-bold text-dark mb-4">Records Distribution by Category</h5>
        <div style="position: relative; height: 320px;">
          <canvas id="catChart"></canvas>
        </div>
      </div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" integrity="sha384-9nhczxUqK87bcKHh20fSQcTGD4qq5GhayNYSYWqwBkINBhOfQLg/P5HG5lF1urn4" crossorigin="anonymous"></script>
<script nonce="<?= csp_nonce() ?>">
document.addEventListener('DOMContentLoaded', function() {
    const dm = <?= json_encode($byMonth) ?>, bc = <?= json_encode($byCat) ?>;
    
    // Line Chart
    new Chart(document.getElementById('disposalsChart'), {
        type: 'line', 
        data: {
            labels: Object.keys(dm), 
            datasets: [{
                label: 'Disposals', 
                data: Object.values(dm), 
                borderColor: '#C85C1A', 
                backgroundColor: 'rgba(200, 92, 26, 0.08)', 
                fill: true, 
                tension: 0.35,
                borderWidth: 2.5,
                pointRadius: 4,
                pointBackgroundColor: '#C85C1A'
            }]
        }, 
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    grid: { color: '#f1f5f9' },
                    ticks: { color: '#64748b', font: { family: 'Inter' } }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#64748b', font: { family: 'Inter' } }
                }
            }
        }
    });

    // Bar Chart
    new Chart(document.getElementById('catChart'), {
        type: 'bar', 
        data: {
            labels: Object.keys(bc).map(label => label.length > 20 ? label.substring(0, 17) + '...' : label), 
            datasets: [{
                label: 'Records', 
                data: Object.values(bc), 
                backgroundColor: '#1A6187',
                borderRadius: 4,
                maxBarThickness: 24
            }]
        }, 
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: '#f1f5f9' },
                    ticks: { color: '#64748b', font: { family: 'Inter' } }
                },
                y: {
                    grid: { display: false },
                    ticks: { color: '#64748b', font: { family: 'Inter' } }
                }
            }
        }
    });
});
</script>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
