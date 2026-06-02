<?php
require_once __DIR__ . '/../config/database.php';
$page_title = 'Dashboard';
$active_nav = 'dashboard';
require __DIR__ . '/../includes/layout_header.php';
$pdo = $__pdo;

$totalCategories = (int) $pdo->query("SELECT COUNT(*) c FROM data_categories WHERE deleted_at IS NULL")->fetch()['c'];
$totalRecords    = (int) $pdo->query("SELECT COUNT(*) c FROM data_records WHERE deleted_at IS NULL")->fetch()['c'];
$dueReview       = (int) $pdo->query("SELECT COUNT(*) c FROM data_records WHERE status='due_review'")->fetch()['c'];
?>
<div class="row g-3">
  <div class="col-md-4"><div class="card shadow-sm"><div class="card-body">
    <h5 class="card-title text-muted">Categories</h5><p class="display-6 mb-0"><?= $totalCategories ?></p></div></div></div>
  <div class="col-md-4"><div class="card shadow-sm"><div class="card-body">
    <h5 class="card-title text-muted">Records</h5><p class="display-6 mb-0"><?= $totalRecords ?></p></div></div></div>
  <div class="col-md-4"><div class="card shadow-sm"><div class="card-body">
    <h5 class="card-title text-muted">Due for review</h5><p class="display-6 mb-0"><?= $dueReview ?></p></div></div></div>
</div>
<div class="card shadow-sm mt-3"><div class="card-body">
  <h2 class="h5">Welcome, <?= escape_html($__user['name']) ?></h2>
  <p class="text-muted mb-0">ADRS Core foundation is live. Modules will appear in the sidebar as they are built.</p>
</div></div>
<?php require __DIR__ . '/../includes/layout_footer.php'; ?>
