<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_login();
$pdo = get_db();
$me = (int) current_user()['id'];
$cnt = $pdo->prepare("SELECT COUNT(*) FROM notifications WHERE recipient_id=:u"); $cnt->execute(['u' => $me]);
$pg = paginate((int) $cnt->fetchColumn(), 30, (int) ($_GET['page'] ?? 1));
$rows = $pdo->prepare("SELECT * FROM notifications WHERE recipient_id=:u ORDER BY id DESC LIMIT {$pg['per_page']} OFFSET {$pg['offset']}");
$rows->execute(['u' => $me]);
$notifications = $rows->fetchAll();
$page_title = 'Notifications';
$active_nav = 'notifications';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Notifications</h1>
  <form method="post" action="<?= APP_URL ?>/notifications/mark_read"><?= csrf_field() ?>
    <button class="btn btn-outline-secondary btn-sm">Mark all read</button></form>
</div>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($notifications)): ?><p class="text-muted mb-0">You have no notifications.</p><?php else: ?>
  <ul class="list-group list-group-flush">
    <?php foreach ($notifications as $n): ?>
      <li class="list-group-item <?= $n['read_at'] === null ? 'fw-semibold' : '' ?>">
        <div class="d-flex justify-content-between">
          <span><?php if ($n['read_at']===null): ?><span class="badge bg-danger">new</span> <?php endif; ?><?= escape_html($n['subject']) ?></span>
          <small class="text-muted"><?= escape_html(format_datetime($n['created_at'])) ?></small>
        </div>
        <div class="small text-muted"><?= escape_html($n['message']) ?></div>
      </li>
    <?php endforeach; ?>
  </ul>
  <div class="d-flex justify-content-end mt-2"><?= pagination_links($pg, APP_URL . '/notifications') ?></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
