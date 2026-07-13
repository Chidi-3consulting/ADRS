<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/analytics_lib.php';
require_login();
$pdo = get_db();

$page_title = 'Dashboard';
$active_nav = 'dashboard';
require __DIR__ . '/../includes/layout_header.php';
$pdo = $__pdo;
$orgId = require_org_id();
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
     WHERE dr.organization_id = {$orgId} AND dr.deleted_at IS NULL{$ownerScope}"
)->fetch();

$isStaff = has_role('admin', 'dpo');
$pendingRecalc = $isStaff ? (int) $pdo->query("SELECT COUNT(*) c FROM pending_recalculations WHERE organization_id = {$orgId} AND status='pending'")->fetch()['c'] : 0;
$recent = $isStaff ? $pdo->query("SELECT al.*, u.name pbn FROM audit_log al LEFT JOIN users u ON u.id=al.performed_by WHERE al.organization_id = {$orgId} ORDER BY al.id DESC LIMIT 5")->fetchAll() : [];

$score = compliance_score($pdo);
$deadlines = upcoming_deadlines($pdo, 5);

function dash_card(string $label, int $val, string $cls, string $icon, string $href = ''): string {
    $inner = '
    <div class="card hover-lift h-100 stat-card-gradient ' . $cls . '">
      <div class="card-body d-flex justify-content-between align-items-center">
        <div>
          <div class="text-muted small fw-medium">' . escape_html($label) . '</div>
          <div class="h2 mb-0 mt-1 fw-bold">' . $val . '</div>
        </div>
        <div class="fs-3 text-secondary opacity-50"><i class="bi ' . $icon . '"></i></div>
      </div>
    </div>';
    return '<div class="col-sm-6 col-md-3 mb-4">' . ($href ? '<a class="text-decoration-none" href="' . $href . '">' . $inner . '</a>' : $inner) . '</div>';
}
?>

<div class="d-flex justify-content-between align-items-center mb-4">
  <div>
    <h1 class="h3 mb-1 fw-bold">Compliance Dashboard</h1>
    <p class="text-muted mb-0">
      <?php
      $__dashOrg = fetch_current_organization($pdo);
      if ($__dashOrg): ?>
        <span class="fw-semibold text-dark"><?= escape_html($__dashOrg['name']) ?></span> ·
      <?php endif; ?>
      Welcome back, <?= escape_html($__user['name']) ?> (<?= get_role_badge($__user['role']) ?>)
    </p>
  </div>
  <div class="no-print">
    <a href="<?= APP_URL ?>/records?action=create" class="btn btn-primary d-inline-flex align-items-center gap-2">
      <i class="bi bi-plus-circle"></i> Register Record
    </a>
  </div>
</div>

<?php if (has_role('admin') && !smtp_is_configured($pdo)): ?>
  <div class="alert alert-warning shadow-sm border-0 d-flex align-items-center gap-2 mb-4">
    <i class="bi bi-exclamation-triangle-fill fs-5 text-warning"></i>
    <div>
      <strong>SMTP email is not configured.</strong> Retention alerts and compliance warning escalations cannot be sent. Configure SMTP settings under 
      <a href="<?= APP_URL ?>/settings?tab=email" class="alert-link fw-semibold">Settings → Email delivery</a>.
    </div>
  </div>
<?php endif; ?>

<!-- Stat Widgets Row -->
<div class="row">
  <?= dash_card('Active records', (int)$k['active'], '', 'bi-card-list', APP_URL.'/records') ?>
  <?= dash_card('Due for review', (int)$k['due_review'], 'yellow', 'bi-bell-fill', APP_URL.'/records?status=due_review') ?>
  <?= dash_card('Overdue retention', (int)$k['overdue'], 'danger', 'bi-exclamation-octagon-fill', APP_URL.'/records') ?>
  <?= dash_card('On legal hold', (int)$k['on_hold'], 'teal', 'bi-lock-fill', APP_URL.'/records') ?>
</div>

<div class="row g-4 mb-4">
  <!-- Compliance Health Score Gauge -->
  <div class="col-lg-4">
    <div class="card h-100 shadow-sm">
      <div class="card-header bg-transparent border-0 pb-0">
        <h2 class="h6 text-muted mb-0 fw-bold uppercase">Compliance Score</h2>
      </div>
      <div class="card-body d-flex flex-column align-items-center justify-content-center py-4">
        <!-- SVG Donut Chart -->
        <div class="position-relative d-flex align-items-center justify-content-center mb-3" style="width: 140px; height: 140px;">
          <svg width="100%" height="100%" viewBox="0 0 42 42" class="donut">
            <circle class="donut-ring" cx="21" cy="21" r="15.915" fill="transparent" stroke="#f1f5f9" stroke-width="4.5"></circle>
            <circle class="donut-segment" cx="21" cy="21" r="15.915" fill="transparent" stroke="<?= $score > 80 ? 'var(--3c-primary)' : 'var(--3c-yellow)' ?>" stroke-width="4.5"
                    stroke-dasharray="<?= $score ?> <?= 100 - $score ?>" stroke-dashoffset="25" stroke-linecap="round" style="transition: stroke-dasharray 1s ease-in-out;"></circle>
          </svg>
          <div class="position-absolute text-center">
            <div class="h2 mb-0 fw-bold text-dark"><?= $score ?>%</div>
            <div class="small text-muted font-monospace" style="font-size: 0.7rem;">HEALTH</div>
          </div>
        </div>
        <p class="text-center text-muted small mb-0 px-2">
          Based on the proportion of compliant data records vs overdue items currently stored in the system.
        </p>
      </div>
    </div>
  </div>

  <!-- Upcoming Deadlines -->
  <div class="col-lg-8">
    <div class="card h-100 shadow-sm">
      <div class="card-header bg-transparent border-0 pb-0 d-flex justify-content-between align-items-center">
        <h2 class="h6 text-muted mb-0 fw-bold uppercase">Approaching Deadlines</h2>
        <a href="<?= APP_URL ?>/records" class="small text-decoration-none">View all</a>
      </div>
      <div class="card-body">
        <?php if (empty($deadlines)): ?>
          <div class="text-center py-4 text-muted">
            <i class="bi bi-calendar-check fs-2 opacity-50"></i>
            <p class="small mt-2 mb-0">No active records require retention review soon.</p>
          </div>
        <?php else: ?>
          <div class="table-responsive">
            <table class="table table-hover table-sm mb-0">
              <thead>
                <tr>
                  <th>Record Ref</th>
                  <th>Data Category</th>
                  <th>Retention End</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <?php foreach ($deadlines as $d):
                  $isOverdue = strtotime($d['retention_end_date']) < time();
                  $badgeCls = $isOverdue ? 'status-overdue' : ($d['status'] === 'due_review' ? 'status-review' : 'status-active');
                ?>
                  <tr onclick="window.location.href='<?= APP_URL ?>/records/edit?id=<?= $d['id'] ?>'">
                    <td class="font-monospace fw-semibold"><?= escape_html($d['record_reference']) ?></td>
                    <td><?= escape_html($d['category_name']) ?></td>
                    <td><?= escape_html(format_date($d['retention_end_date'])) ?></td>
                    <td>
                      <span class="badge-status-dot <?= $badgeCls ?>">
                        <?= $isOverdue ? 'Overdue' : escape_html(ucfirst(str_replace('_', ' ', $d['status']))) ?>
                      </span>
                    </td>
                  </tr>
                <?php endforeach; ?>
              </tbody>
            </table>
          </div>
        <?php endif; ?>
      </div>
    </div>
  </div>
</div>

<div class="row g-4">
  <!-- Recent Actions Log (Auditing) -->
  <?php if ($isStaff): ?>
    <div class="col-md-8">
      <div class="card shadow-sm h-100">
        <div class="card-header bg-transparent border-0 pb-0">
          <h2 class="h6 text-muted mb-0 fw-bold uppercase">Audit Activity Logs</h2>
        </div>
        <div class="card-body">
          <?php if (empty($recent)): ?>
            <p class="text-muted small mb-0">No security audit logs recorded yet.</p>
          <?php else: ?>
            <div class="table-responsive">
              <table class="table table-sm table-hover mb-0">
                <tbody>
                  <?php foreach ($recent as $a): ?>
                    <tr>
                      <td><code class="text-primary font-monospace bg-light px-2 py-1 rounded"><?= escape_html($a['action']) ?></code></td>
                      <td class="small text-muted"><?= escape_html($a['pbn'] ?? 'Automated Cron') ?></td>
                      <td class="small text-muted text-end"><?= escape_html(format_datetime($a['created_at'])) ?></td>
                    </tr>
                  <?php endforeach; ?>
                </tbody>
              </table>
            </div>
          <?php endif; ?>
        </div>
      </div>
    </div>
  <?php endif; ?>

  <!-- Queue & Recalculation Quick Links -->
  <div class="col-md-4">
    <div class="card shadow-sm h-100">
      <div class="card-header bg-transparent border-0 pb-0">
        <h2 class="h6 text-muted mb-0 fw-bold uppercase">Quick Actions</h2>
      </div>
      <div class="card-body">
        <div class="d-grid gap-2">
          <?php if ($isStaff && $pendingRecalc > 0): ?>
            <a href="<?= APP_URL ?>/recalculations" class="btn btn-warning btn-sm text-dark d-flex align-items-center justify-content-between p-2">
              <span>Recalculations pending</span>
              <span class="badge bg-dark"><?= $pendingRecalc ?></span>
            </a>
          <?php endif; ?>
          <a href="<?= APP_URL ?>/categories" class="btn btn-outline-secondary btn-sm text-start p-2"><i class="bi bi-collection me-2"></i> Manage Categories</a>
          <a href="<?= APP_URL ?>/reports" class="btn btn-outline-secondary btn-sm text-start p-2"><i class="bi bi-graph-up me-2"></i> Compliance Reports</a>
          <a href="<?= APP_URL ?>/settings" class="btn btn-outline-secondary btn-sm text-start p-2"><i class="bi bi-gear-fill me-2"></i> Tenant Settings</a>
        </div>
      </div>
    </div>
  </div>
</div>

<?php require __DIR__ . '/../includes/layout_footer.php'; ?>
