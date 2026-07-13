<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/categories_lib.php';
require_once __DIR__ . '/../../includes/retention_rules_lib.php';
require_login();
$pdo = get_db();
$me = current_user();

$orgId = require_org_id();
if (has_role('data_owner')) {
    $stmt = $pdo->prepare("SELECT * FROM data_categories WHERE organization_id = :org AND deleted_at IS NULL AND owner_id = :o ORDER BY name");
    $stmt->execute(['org' => $orgId, 'o' => $me['id']]);
} else {
    $stmt = $pdo->prepare("SELECT * FROM data_categories WHERE organization_id = :org AND deleted_at IS NULL ORDER BY name");
    $stmt->execute(['org' => $orgId]);
}
$categories = $stmt->fetchAll();

$stats = ['total' => 0, 'sensitive' => 0, 'date_based' => 0, 'consent_based' => 0];
foreach ($categories as $c) {
    $stats['total']++;
    if ((int)$c['requires_dual_approval'] === 1) { $stats['sensitive']++; }
    if ($c['disposal_trigger'] === 'consent_withdrawal') {
        $stats['consent_based']++;
    } else {
        $stats['date_based']++;
    }
}

$page_title = 'Data Categories';
$active_nav = 'categories';
require __DIR__ . '/../../includes/layout_header.php';
?>

<div class="d-flex justify-content-between align-items-center mb-4">
  <div>
    <h1 class="h3 mb-1 fw-bold">Data Categories</h1>
    <p class="text-muted mb-0">Define policies, periods, and disposal mechanisms for governance categories.</p>
  </div>
  <div class="d-flex gap-2">
    <a href="<?= APP_URL ?>/categories/export" class="btn btn-outline-secondary d-inline-flex align-items-center gap-2">
      <i class="bi bi-download"></i> Export CSV
    </a>
    <?php if (has_role('admin','dpo')): ?>
      <a href="<?= APP_URL ?>/categories/create" class="btn btn-primary d-inline-flex align-items-center gap-2">
        <i class="bi bi-plus-lg"></i> New Category
      </a>
    <?php endif; ?>
  </div>
</div>

<!-- Stat Cards -->
<div class="row g-3 mb-4">
  <div class="col-6 col-md-3">
    <div class="card stat-card-gradient h-100 shadow-sm">
      <div class="card-body py-3">
        <div class="text-muted small fw-medium">Total Categories</div>
        <div class="h3 mb-0 mt-1 fw-bold"><?= $stats['total'] ?></div>
      </div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card stat-card-gradient yellow h-100 shadow-sm">
      <div class="card-body py-3">
        <div class="text-muted small fw-medium">Sensitive (Dual Appr.)</div>
        <div class="h3 mb-0 mt-1 fw-bold"><?= $stats['sensitive'] ?></div>
      </div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card stat-card-gradient h-100 shadow-sm" style="--3c-primary: var(--3c-teal);">
      <div class="card-body py-3">
        <div class="text-muted small fw-medium">Date-Based</div>
        <div class="h3 mb-0 mt-1 fw-bold"><?= $stats['date_based'] ?></div>
      </div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card stat-card-gradient h-100 shadow-sm" style="--3c-primary: #8b5cf6;">
      <div class="card-body py-3">
        <div class="text-muted small fw-medium">Consent-Based</div>
        <div class="h3 mb-0 mt-1 fw-bold"><?= $stats['consent_based'] ?></div>
      </div>
    </div>
  </div>
</div>

<!-- Filter Bar -->
<div class="card shadow-sm mb-4">
  <div class="card-body p-3">
    <div class="row g-2 align-items-center">
      <div class="col-md-6">
        <div class="input-group">
          <span class="input-group-text bg-transparent border-end-0 text-muted"><i class="bi bi-search"></i></span>
          <input type="text" id="category-search" class="form-control border-start-0" placeholder="Search categories by name or reason...">
        </div>
      </div>
      <div class="col-md-3">
        <select id="trigger-filter" class="form-select">
          <option value="">All Disposal Triggers</option>
          <option value="date_based">Date-based</option>
          <option value="consent_withdrawal">Consent withdrawal</option>
        </select>
      </div>
      <div class="col-md-3">
        <select id="sensitive-filter" class="form-select">
          <option value="">All Sensitivity Tiers</option>
          <option value="yes">Sensitive Only</option>
          <option value="no">Non-Sensitive Only</option>
        </select>
      </div>
    </div>
  </div>
</div>

<!-- Categories Table -->
<div class="card shadow-sm">
  <div class="card-body p-0">
    <?php if (empty($categories)): ?>
      <div class="text-center py-5 text-muted">
        <i class="bi bi-collection fs-1 opacity-40"></i>
        <p class="mt-2 mb-0">No data categories configured yet.</p>
      </div>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0" id="categories-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Retention Period</th>
              <th>Trigger</th>
              <th>Disposal Method</th>
              <th>Sensitive</th>
              <th>Retention Reason</th>
              <th>Source</th>
              <th class="no-print"></th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($categories as $c):
              $isConsent = $c['disposal_trigger'] === 'consent_withdrawal';
              $isSensitive = (int)$c['requires_dual_approval'] === 1;
              $reason = $c['retention_reason'] ?: $c['description'] ?: '—';
            ?>
              <tr data-trigger="<?= escape_html($c['disposal_trigger']) ?>" data-sensitive="<?= $isSensitive ? 'yes' : 'no' ?>">
                <td class="fw-semibold text-dark"><?= escape_html($c['name']) ?></td>
                <td>
                  <?php if ($isConsent): ?>
                    <span class="text-muted">Until consent withdrawn</span>
                  <?php else: ?>
                    <?= escape_html($c['retention_period_label']) ?>
                  <?php endif; ?>
                </td>
                <td>
                  <?php if ($isConsent): ?>
                    <span class="badge bg-purple" style="background:#8b5cf6;">👤 Consent</span>
                  <?php else: ?>
                    <span class="badge bg-primary">📅 Date</span>
                  <?php endif; ?>
                </td>
                <td>
                  <span class="text-capitalize"><?= escape_html(get_disposal_method_label($c['disposal_method'])) ?></span>
                </td>
                <td>
                  <?php if ($isSensitive): ?>
                    <span class="text-success fw-bold">✅ Yes</span>
                  <?php else: ?>
                    <span class="text-muted">— No</span>
                  <?php endif; ?>
                </td>
                <td class="text-muted small" style="max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="<?= escape_html($reason) ?>">
                  <?= escape_html($reason) ?>
                </td>
                <td>
                  <?php if ($c['source'] === 'seeded'): ?>
                    <span class="badge bg-secondary" title="Seeded from regulatory template library">Standard</span>
                  <?php else: ?>
                    <span class="badge bg-light text-dark border">Custom</span>
                  <?php endif; ?>
                </td>
                <td class="text-nowrap text-end no-print pe-3">
                  <a href="<?= APP_URL ?>/categories/view?id=<?= (int)$c['id'] ?>" class="btn btn-sm btn-outline-secondary">View</a>
                  <?php if (has_role('admin','dpo')): ?>
                    <a href="<?= APP_URL ?>/categories/edit?id=<?= (int)$c['id'] ?>" class="btn btn-sm btn-outline-primary">Edit</a>
                  <?php endif; ?>
                </td>
              </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('category-search');
    const triggerFilter = document.getElementById('trigger-filter');
    const sensitiveFilter = document.getElementById('sensitive-filter');
    const tableRows = document.querySelectorAll('#categories-table tbody tr');

    function filterTable() {
        const query = searchInput.value.toLowerCase();
        const trigger = triggerFilter.value;
        const sensitive = sensitiveFilter.value;

        tableRows.forEach(row => {
            const name = row.cells[0].textContent.toLowerCase();
            const reason = row.cells[5].textContent.toLowerCase();
            const rowTrigger = row.getAttribute('data-trigger');
            const rowSensitive = row.getAttribute('data-sensitive');

            const matchesSearch = name.includes(query) || reason.includes(query);
            const matchesTrigger = !trigger || rowTrigger === trigger;
            const matchesSensitive = !sensitive || rowSensitive === sensitive;

            if (matchesSearch && matchesTrigger && matchesSensitive) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    if(searchInput) searchInput.addEventListener('input', filterTable);
    if(triggerFilter) triggerFilter.addEventListener('change', filterTable);
    if(sensitiveFilter) sensitiveFilter.addEventListener('change', filterTable);
});
</script>

<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
