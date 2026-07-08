<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/categories_lib.php';
require_once __DIR__ . '/../../includes/retention_rules_lib.php';
require_login();
$pdo = get_db();
$me = current_user();

// Data Owners see only their own categories; Admin/DPO see all.
$orgId = require_org_id();
if (has_role('data_owner')) {
    $stmt = $pdo->prepare("SELECT * FROM data_categories WHERE organization_id = :org AND deleted_at IS NULL AND owner_id = :o ORDER BY name");
    $stmt->execute(['org' => $orgId, 'o' => $me['id']]);
} else {
    $stmt = $pdo->prepare("SELECT * FROM data_categories WHERE organization_id = :org AND deleted_at IS NULL ORDER BY name");
    $stmt->execute(['org' => $orgId]);
}
$categories = $stmt->fetchAll();
$ruleCounts = count_rules_by_category($pdo, array_column($categories, 'id'));

$stats = ['total' => 0, 'gdpr' => 0, 'ndpr' => 0, 'dual' => 0];
foreach ($categories as $c) {
    $stats['total']++;
    if ($c['compliance_framework'] === 'GDPR' || $c['compliance_framework'] === 'BOTH') { $stats['gdpr']++; }
    if ($c['compliance_framework'] === 'NDPR' || $c['compliance_framework'] === 'BOTH') { $stats['ndpr']++; }
    if ((int) $c['requires_dual_approval'] === 1) { $stats['dual']++; }
}

$page_title = 'Data Categories';
$active_nav = 'categories';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Data Categories</h1>
  <?php if (has_role('admin','dpo')): ?>
    <a href="<?= APP_URL ?>/categories/create" class="btn btn-primary"><i class="bi bi-plus-lg"></i> New category</a>
  <?php endif; ?>
</div>

<div class="row g-3 mb-3">
  <div class="col-md-3"><div class="card shadow-sm"><div class="card-body"><div class="text-muted small">Total</div><div class="h3 mb-0"><?= $stats['total'] ?></div></div></div></div>
  <div class="col-md-3"><div class="card shadow-sm"><div class="card-body"><div class="text-muted small">GDPR</div><div class="h3 mb-0"><?= $stats['gdpr'] ?></div></div></div></div>
  <div class="col-md-3"><div class="card shadow-sm"><div class="card-body"><div class="text-muted small">NDPR</div><div class="h3 mb-0"><?= $stats['ndpr'] ?></div></div></div></div>
  <div class="col-md-3"><div class="card shadow-sm"><div class="card-body"><div class="text-muted small">Dual approval</div><div class="h3 mb-0"><?= $stats['dual'] ?></div></div></div></div>
</div>

<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($categories)): ?>
    <p class="text-muted mb-0">No categories yet.</p>
  <?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr>
      <th>Name</th><th>Framework</th><th>Retention rules</th><th>Default retention</th><th>Trigger</th>
      <th>Disposal</th><th>Dual</th><th>Source</th><th></th>
    </tr></thead>
    <tbody>
    <?php foreach ($categories as $c): ?>
      <tr>
        <td><?= escape_html($c['name']) ?></td>
        <td><?= get_framework_badge($c['compliance_framework']) ?></td>
        <td><span class="badge bg-secondary"><?= (int) ($ruleCounts[(int)$c['id']] ?? 1) ?> rule<?= ($ruleCounts[(int)$c['id']] ?? 1) !== 1 ? 's' : '' ?></span></td>
        <td>
          <?php if ($c['disposal_trigger'] === 'consent_withdrawal'): ?>
            <span class="text-muted">Until consent withdrawn</span>
          <?php else: ?>
            <?= escape_html($c['retention_period_label']) ?>
          <?php endif; ?>
        </td>
        <td><?php if ($c['disposal_trigger'] === 'consent_withdrawal'): ?><span class="badge bg-purple" style="background:#6f42c1">👤 Consent</span><?php else: ?><span class="badge bg-primary">📅 Date</span><?php endif; ?></td>
        <td><?= escape_html(get_disposal_method_label($c['disposal_method'])) ?></td>
        <td><?php if ((int)$c['requires_dual_approval'] === 1): ?><span class="badge" style="background:var(--3c-orange)">🔐 Dual</span><?php endif; ?></td>
        <td><?php if ($c['source'] === 'seeded'): ?><span title="Seeded from library">📚</span><?php else: ?>—<?php endif; ?></td>
        <td class="text-nowrap">
          <a href="<?= APP_URL ?>/categories/view?id=<?= (int)$c['id'] ?>" class="btn btn-sm btn-outline-secondary">View</a>
          <?php if (has_role('admin','dpo')): ?>
            <a href="<?= APP_URL ?>/categories/edit?id=<?= (int)$c['id'] ?>" class="btn btn-sm btn-outline-primary">Edit</a>
          <?php endif; ?>
        </td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
