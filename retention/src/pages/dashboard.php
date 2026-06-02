<?php
$pdo = get_pdo();
$user = current_user();

$stmt = $pdo->query('SELECT COUNT(*) AS total FROM data_categories WHERE deleted_at IS NULL');
$totalCategories = $stmt->fetchColumn();

$stmt = $pdo->query("SELECT COUNT(*) AS total FROM data_records WHERE deleted_at IS NULL");
$totalRecords = $stmt->fetchColumn();

$stmt = $pdo->prepare("SELECT COUNT(*) FROM data_records WHERE status = 'due_review'");
$stmt->execute();
$dueReview = $stmt->fetchColumn();

$stmt = $pdo->query('SELECT COUNT(*) FROM dsar_requests');
$totalDsar = $stmt->fetchColumn();

$stmt = $pdo->query("SELECT COUNT(*) FROM intake_queue WHERE status = 'pending'");
$totalIntakePending = $stmt->fetchColumn();

$stmt = $pdo->query("SELECT COUNT(*) FROM disposal_dispatches WHERE status = 'pending'");
$totalDispatchPending = $stmt->fetchColumn();

$stmt = $pdo->query('SELECT COUNT(*) FROM audit_log');
$totalAuditEntries = $stmt->fetchColumn();

$stmt = $pdo->query('SELECT COUNT(*) FROM notifications');
$totalNotifications = $stmt->fetchColumn();

$stmt = $pdo->query('SELECT COUNT(*) FROM attachments');
$totalAttachments = $stmt->fetchColumn();
?>
<?php require __DIR__ . '/../includes/layout_header.php'; ?>
<div class="row">
  <div class="col-md-4">
    <div class="card mb-3 shadow-sm">
      <div class="card-body">
        <h5 class="card-title">Categories</h5>
        <p class="card-text display-6"><?= escape_html($totalCategories) ?></p>
      </div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card mb-3 shadow-sm">
      <div class="card-body">
        <h5 class="card-title">Records</h5>
        <p class="card-text display-6"><?= escape_html($totalRecords) ?></p>
      </div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card mb-3 shadow-sm">
      <div class="card-body">
        <h5 class="card-title">Due review</h5>
        <p class="card-text display-6"><?= escape_html($dueReview) ?></p>
      </div>
    </div>
  </div>
</div>
<div class="row">
  <div class="col-md-6">
    <div class="card mb-3 shadow-sm">
      <div class="card-body">
        <h5 class="card-title">Pending intake</h5>
        <p class="card-text display-6"><?= escape_html($totalIntakePending) ?></p>
        <a href="/retention/intake-queue" class="stretched-link"></a>
      </div>
    </div>
  </div>
  <div class="col-md-6">
    <div class="card mb-3 shadow-sm">
      <div class="card-body">
        <h5 class="card-title">Pending dispatch</h5>
        <p class="card-text display-6"><?= escape_html($totalDispatchPending) ?></p>
        <a href="/retention/disposal-dispatch" class="stretched-link"></a>
      </div>
    </div>
  </div>
</div>
<div class="row">
  <div class="col-md-6">
    <div class="card mb-3 shadow-sm">
      <div class="card-body">
        <h5 class="card-title">DSAR requests</h5>
        <p class="card-text display-6"><?= escape_html($totalDsar) ?></p>
      </div>
    </div>
  </div>
  <div class="col-md-6">
    <div class="card mb-3 shadow-sm">
      <div class="card-body">
        <h5 class="card-title">Audit events</h5>
        <p class="card-text display-6"><?= escape_html($totalAuditEntries) ?></p>
      </div>
    </div>
  </div>
</div>
<div class="row">
  <div class="col-md-6">
    <div class="card mb-3 shadow-sm">
      <div class="card-body">
        <h5 class="card-title">Notifications</h5>
        <p class="card-text display-6"><?= escape_html($totalNotifications) ?></p>
      </div>
    </div>
  </div>
  <div class="col-md-6">
    <div class="card mb-3 shadow-sm">
      <div class="card-body">
        <h5 class="card-title">Attachments</h5>
        <p class="card-text display-6"><?= escape_html($totalAttachments) ?></p>
      </div>
    </div>
  </div>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <h2 class="h5">Welcome back, <?= escape_html($user['name']) ?></h2>
    <p>Use the menu to manage data categories or review retention tasks.</p>
  </div>
</div>
<?php require __DIR__ . '/../includes/layout_footer.php'; ?>
