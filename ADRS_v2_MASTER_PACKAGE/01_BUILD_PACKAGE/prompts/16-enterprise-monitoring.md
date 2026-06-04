# Prompt 16 — Enterprise Dashboard & Monitoring
# ENTERPRISE TIER ONLY — enhances the standard dashboard from Prompt 08

## Context
When `adrs_tier = 'enterprise'`, the dashboard gets an additional section showing
real-time integration health, queue status, and cross-system compliance metrics.
This is shown ONLY to Admin and DPO roles. The Data Owner dashboard is unchanged.

---

## Additions to `src/pages/dashboard.php`

### Addition 1: Enterprise Integration Health Banner

Shown at the very top of the dashboard, above the KPI cards, Admin/DPO only:

```php
<?php if ($adrs_tier === 'enterprise'): ?>

<?php
// Single query: all connected systems health
$systems = $pdo->query(
    "SELECT name, health_status, last_ping_at,
            (SELECT COUNT(*) FROM intake_queue iq WHERE iq.system_id = cs.id AND iq.status='pending') AS queue_pending,
            (SELECT COUNT(*) FROM intake_queue iq WHERE iq.system_id = cs.id AND iq.status='failed') AS queue_failed
     FROM connected_systems cs WHERE cs.is_active = 1"
)->fetchAll();

$any_degraded = !empty(array_filter($systems, fn($s) => $s['health_status'] !== 'healthy'));
?>

<div class="card mb-4 border-<?= $any_degraded ? 'warning' : 'success' ?>">
  <div class="card-header" style="background:<?= $any_degraded ? '#E67E22' : '#1E7E34' ?>;color:white;">
    <i class="bi bi-diagram-3"></i>
    Enterprise Integration Health
    <?php if ($any_degraded): ?>
      <span class="badge bg-white text-dark ms-2">⚠️ Attention Required</span>
    <?php else: ?>
      <span class="badge bg-white text-success ms-2">✅ All Systems Healthy</span>
    <?php endif; ?>
  </div>
  <div class="card-body p-0">
    <div class="row g-0">
      <?php foreach ($systems as $sys): ?>
      <div class="col-md-3 border-end p-3">
        <div class="d-flex align-items-center gap-2 mb-1">
          <span style="font-size:8px;color:<?= match($sys['health_status']) {
            'healthy'  => '#1E7E34',
            'degraded' => '#E67E22',
            'offline'  => '#C0392B',
            default    => '#888'
          } ?>;">●</span>
          <strong class="small"><?= sanitize($sys['name']) ?></strong>
        </div>
        <div class="small text-muted">
          Queue pending: <strong><?= $sys['queue_pending'] ?></strong>
          <?php if ($sys['queue_failed'] > 0): ?>
            | <span class="text-danger">Failed: <?= $sys['queue_failed'] ?></span>
          <?php endif; ?>
        </div>
        <div class="small text-muted">
          Last ping: <?= $sys['last_ping_at'] ? relative_time($sys['last_ping_at']) : 'Never' ?>
        </div>
      </div>
      <?php endforeach; ?>
    </div>
  </div>
</div>

<?php endif; ?>
```

---

### Addition 2: Enterprise KPI Cards (extra row after standard KPIs)

```php
<?php if ($adrs_tier === 'enterprise'): ?>

<?php
// All 4 in one query
$ent_stats = $pdo->query(
    "SELECT
       (SELECT COUNT(*) FROM intake_queue WHERE status = 'pending')      AS queue_pending,
       (SELECT COUNT(*) FROM intake_queue WHERE status = 'failed')        AS queue_failed,
       (SELECT COUNT(*) FROM intake_queue
        WHERE DATE(created_at) = CURDATE() AND status = 'completed')      AS ingested_today,
       (SELECT COUNT(*) FROM disposal_dispatches WHERE status = 'pending') AS dispatches_pending,
       (SELECT COUNT(*) FROM consent_signals WHERE status = 'unmatched')   AS signals_unmatched"
)->fetch();
?>

<div class="row g-3 mb-4">
  <div class="col">
    <div class="card text-center h-100 border-<?= $ent_stats['queue_pending'] > 0 ? 'warning' : 'secondary' ?>">
      <div class="card-body">
        <div style="font-size:2rem;font-weight:700;color:#E67E22"><?= $ent_stats['queue_pending'] ?></div>
        <div class="small text-muted">Intake Queue</div>
      </div>
    </div>
  </div>
  <div class="col">
    <div class="card text-center h-100 border-<?= $ent_stats['queue_failed'] > 0 ? 'danger' : 'secondary' ?>">
      <div class="card-body">
        <div style="font-size:2rem;font-weight:700;color:<?= $ent_stats['queue_failed'] > 0 ? '#C0392B' : '#888' ?>">
          <?= $ent_stats['queue_failed'] ?>
        </div>
        <div class="small text-muted">Queue Failed</div>
      </div>
    </div>
  </div>
  <div class="col">
    <div class="card text-center h-100 border-success">
      <div class="card-body">
        <div style="font-size:2rem;font-weight:700;color:#1E7E34"><?= $ent_stats['ingested_today'] ?></div>
        <div class="small text-muted">Ingested Today</div>
      </div>
    </div>
  </div>
  <div class="col">
    <div class="card text-center h-100 border-<?= $ent_stats['dispatches_pending'] > 0 ? 'warning' : 'secondary' ?>">
      <div class="card-body">
        <div style="font-size:2rem;font-weight:700;color:#E67E22"><?= $ent_stats['dispatches_pending'] ?></div>
        <div class="small text-muted">Dispatches Pending</div>
      </div>
    </div>
  </div>
  <div class="col">
    <div class="card text-center h-100 border-<?= $ent_stats['signals_unmatched'] > 0 ? 'danger' : 'secondary' ?>">
      <div class="card-body">
        <div style="font-size:2rem;font-weight:700;color:<?= $ent_stats['signals_unmatched'] > 0 ? '#C0392B' : '#888' ?>">
          <?= $ent_stats['signals_unmatched'] ?>
        </div>
        <div class="small text-muted">Unmatched Consent Signals</div>
      </div>
    </div>
  </div>
</div>

<?php endif; ?>
```

---

### Addition 3: Intake Activity Chart (last 7 days)

Pure CSS/JS bar chart showing daily record intake volume per connected system.

```php
<?php if ($adrs_tier === 'enterprise'): ?>

<?php
// Records ingested per day per system, last 7 days
$intake_chart = $pdo->query(
    "SELECT cs.name AS system_name,
            DATE(iq.created_at) AS day,
            COUNT(*) AS count
     FROM intake_queue iq
     JOIN connected_systems cs ON cs.id = iq.system_id
     WHERE iq.created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
       AND iq.status = 'completed'
     GROUP BY cs.name, DATE(iq.created_at)
     ORDER BY day ASC"
)->fetchAll();
?>

<div class="card mb-4">
  <div class="card-header card-header-teal">
    <i class="bi bi-bar-chart"></i> Record Intake — Last 7 Days
    <a href="<?= APP_URL ?>/src/pages/integrations/" class="btn btn-sm btn-outline-light float-end">
      Manage Integrations
    </a>
  </div>
  <div class="card-body">
    <div id="intakeChart" style="height:120px;display:flex;align-items:flex-end;gap:4px;">
      <!-- JS builds the bar chart from PHP JSON data -->
    </div>
    <div class="text-muted small mt-2 text-center">Daily record intake volume from connected systems</div>
  </div>
</div>

<script>
const intakeData = <?= json_encode($intake_chart) ?>;
// Build simple CSS bar chart from intakeData array
(function() {
    const chart = document.getElementById('intakeChart');
    if (!intakeData.length) {
        chart.innerHTML = '<p class="text-muted text-center w-100 small">No intake data for the last 7 days.</p>';
        return;
    }
    const maxVal = Math.max(...intakeData.map(d => d.count), 1);
    // Group by day
    const days = [...new Set(intakeData.map(d => d.day))].sort();
    days.forEach(day => {
        const dayTotal = intakeData.filter(d => d.day === day).reduce((s, d) => s + parseInt(d.count), 0);
        const pct = Math.round((dayTotal / maxVal) * 100);
        const label = new Date(day).toLocaleDateString('en-GB', {day:'numeric',month:'short'});
        const col = document.createElement('div');
        col.style.cssText = 'flex:1;display:flex;flex-direction:column;align-items:center;gap:4px';
        col.innerHTML = `
            <span style="font-size:10px;color:#1A6187;font-weight:700">${dayTotal}</span>
            <div style="width:100%;background:#C85C1A;height:${pct}%;min-height:4px;border-radius:3px 3px 0 0"></div>
            <span style="font-size:9px;color:#888">${label}</span>`;
        chart.appendChild(col);
    });
})();
</script>

<?php endif; ?>
```

---

### Addition 4: Recent API Activity (mini log)

Below the standard audit log section on the dashboard:

```php
<?php if ($adrs_tier === 'enterprise'): ?>

<?php
$api_recent = $pdo->query(
    "SELECT il.direction, il.endpoint, il.status_code, il.records_affected,
            il.duration_ms, il.created_at, cs.name AS system_name
     FROM integration_logs il
     LEFT JOIN connected_systems cs ON cs.id = il.system_id
     ORDER BY il.created_at DESC LIMIT 8"
)->fetchAll();
?>

<div class="card mb-4">
  <div class="card-header card-header-teal">
    <i class="bi bi-arrow-left-right"></i> Recent API Activity
    <a href="<?= APP_URL ?>/src/pages/integrations/logs/" class="btn btn-sm btn-outline-light float-end">
      Full Log
    </a>
  </div>
  <div class="card-body p-0">
    <table class="table table-sm mb-0">
      <thead>
        <tr><th>Time</th><th>System</th><th>Direction</th><th>Endpoint</th><th>Status</th><th>Records</th></tr>
      </thead>
      <tbody>
        <?php foreach ($api_recent as $entry): ?>
        <tr>
          <td class="small text-muted"><?= relative_time($entry['created_at']) ?></td>
          <td class="small"><?= sanitize($entry['system_name'] ?? 'Unknown') ?></td>
          <td><span class="badge <?= $entry['direction'] === 'inbound' ? 'bg-info' : 'bg-secondary' ?>">
            <?= $entry['direction'] === 'inbound' ? '↓ In' : '↑ Out' ?></span></td>
          <td class="small text-muted" style="font-family:monospace"><?= sanitize($entry['endpoint']) ?></td>
          <td><span class="badge <?= $entry['status_code'] < 300 ? 'bg-success' : ($entry['status_code'] < 500 ? 'bg-warning text-dark' : 'bg-danger') ?>">
            <?= $entry['status_code'] ?></span></td>
          <td class="small"><?= $entry['records_affected'] ?></td>
        </tr>
        <?php endforeach; ?>
      </tbody>
    </table>
  </div>
</div>

<?php endif; ?>
```

---

## `src/pages/integrations/monitoring.php` — Standalone Monitoring Page

Full-page monitoring view. Admin only.

**Sections:**
1. **System Health Grid** — all connected systems, health status, last ping, record counts
2. **Intake Queue Status** — pending / processing / completed / failed breakdown per system
3. **Disposal Dispatch Status** — pending / confirmed / failed per system
4. **Unmatched Consent Signals** — table of unmatched signals with manual match button
5. **API Rate Usage** — calls per hour per API key (last 24h from integration_logs)
6. **Cron Health** — all cron jobs: last run time, next expected run, status

**"Refresh" button** — reloads the page.
**"Export Status Report"** — CSV snapshot of current health for all systems.
