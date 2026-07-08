<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/onboarding_lib.php';
require_login();
$pdo = get_db();
$me = (int) current_user()['id'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    if (($_POST['action'] ?? '') === 'dismiss_onboarding' && has_role('admin')) {
        set_setting($pdo, 'onboarding_dismissed', '1', require_org_id());
        dismiss_onboarding_notifications($pdo, $me);
        flash('info', 'Setup guide dismissed.');
        redirect(APP_URL . '/notifications');
    }
}

$cnt = $pdo->prepare("SELECT COUNT(*) FROM notifications WHERE recipient_id=:u");
$cnt->execute(['u' => $me]);
$pg = paginate((int) $cnt->fetchColumn(), 30, (int) ($_GET['page'] ?? 1));
$rows = $pdo->prepare("SELECT * FROM notifications WHERE recipient_id=:u ORDER BY id DESC LIMIT {$pg['per_page']} OFFSET {$pg['offset']}");
$rows->execute(['u' => $me]);
$notifications = $rows->fetchAll();

$onboardingPending = 0;
if (has_role('admin')) {
    $obStmt = $pdo->prepare("SELECT COUNT(*) FROM notifications WHERE recipient_id=:u AND type='onboarding_setup' AND read_at IS NULL");
    $obStmt->execute(['u' => $me]);
    $onboardingPending = (int) $obStmt->fetchColumn();
}

$page_title = 'Notifications';
$active_nav = 'notifications';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
  <h1 class="h4 mb-0">Notifications</h1>
  <div class="d-flex gap-2">
    <?php if ($onboardingPending > 0 && has_role('admin')): ?>
      <form method="post" class="mb-0"><?= csrf_field() ?>
        <input type="hidden" name="action" value="dismiss_onboarding">
        <button class="btn btn-outline-secondary btn-sm">Dismiss setup guide</button>
      </form>
    <?php endif; ?>
    <form method="post" action="<?= APP_URL ?>/notifications/mark_read"><?= csrf_field() ?>
      <button class="btn btn-outline-secondary btn-sm">Mark all read</button>
    </form>
  </div>
</div>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($notifications)): ?><p class="text-muted mb-0">You have no notifications.</p><?php else: ?>
  <ul class="list-group list-group-flush">
    <?php foreach ($notifications as $n):
      $isOnboarding = $n['type'] === 'onboarding_setup';
      $actionHref = $isOnboarding ? onboarding_href_from_message($n['message']) : null;
      $displayMsg = $isOnboarding
          ? preg_replace('/\[onboarding:[^\]]+\]\s*/', '', preg_replace('/\s*\[action:[^\]]+\]/', '', $n['message']))
          : $n['message'];
    ?>
      <li class="list-group-item <?= $n['read_at'] === null ? 'fw-semibold' : '' ?><?= $isOnboarding ? ' border-start border-3 border-warning' : '' ?>">
        <div class="d-flex justify-content-between align-items-start gap-2">
          <div class="flex-grow-1">
            <?php if ($n['read_at']===null): ?><span class="badge bg-danger me-1">new</span><?php endif; ?>
            <?php if ($isOnboarding): ?><span class="badge bg-warning text-dark me-1">Setup</span><?php endif; ?>
            <?= escape_html($n['subject']) ?>
            <div class="small text-muted mt-1"><?= escape_html($displayMsg) ?></div>
            <?php if ($actionHref): ?>
              <a href="<?= escape_html($actionHref) ?>" class="btn btn-sm btn-outline-primary mt-2">Continue setup</a>
            <?php endif; ?>
          </div>
          <small class="text-muted text-nowrap"><?= escape_html(format_datetime($n['created_at'])) ?></small>
        </div>
      </li>
    <?php endforeach; ?>
  </ul>
  <div class="d-flex justify-content-end mt-2"><?= pagination_links($pg, APP_URL . '/notifications') ?></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
