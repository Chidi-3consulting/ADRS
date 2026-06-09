<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/platform_lib.php';
require_platform_admin();

$pdo = get_db();
$m = platform_metrics($pdo);
$page_title = 'Platform admin';
$active_nav = '';
require __DIR__ . '/../../includes/layout_header.php';
?>
<h1 class="h4 mb-3">Platform administration</h1>
<div class="row g-3 mb-4">
  <?php foreach ([
    'organizations' => 'Organisations', 'trial_orgs' => 'On trial', 'paid_orgs' => 'Paid',
    'users' => 'Users', 'records' => 'Records', 'revenue_tx' => 'Successful payments',
  ] as $k => $label): ?>
  <div class="col-md-4"><div class="card shadow-sm"><div class="card-body">
    <div class="text-muted small"><?= escape_html($label) ?></div>
    <div class="h3 mb-0"><?= (int) ($m[$k] ?? 0) ?></div>
  </div></div></div>
  <?php endforeach; ?>
</div>
<a href="<?= APP_URL ?>/platform/organizations" class="btn btn-primary">Manage organisations</a>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
