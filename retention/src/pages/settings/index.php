<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_role('admin');
$pdo = get_db();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $orgId = require_org_id();
    foreach ($_POST as $k => $v) {
        if ($k === 'csrf_token' || in_array($k, PLATFORM_SETTING_KEYS, true)) { continue; }
        set_setting($pdo, $k, is_array($v) ? json_encode($v) : (string) $v, $orgId);
    }
    log_audit($pdo, 'schedule_reviewed', 'system', null, (int) current_user()['id'], ['action' => 'settings_updated'], get_client_ip());
    flash('success', 'Settings saved.');
    redirect(APP_URL . '/settings');
}

$orgId = require_org_id();
$rows = $pdo->prepare("SELECT setting_key, setting_value, description FROM organization_settings WHERE organization_id = :o ORDER BY setting_key");
$rows->execute(['o' => $orgId]);
$rows = $rows->fetchAll();
$page_title = 'System Settings';
$active_nav = 'settings';
require __DIR__ . '/../../includes/layout_header.php';
?>
<h1 class="h4 mb-3">System Settings</h1>
<div class="mb-3">
  <a href="<?= APP_URL ?>/settings/2fa" class="btn btn-outline-secondary btn-sm">🔐 Two-Factor Auth</a>
  <a href="<?= APP_URL ?>/integrations/tier" class="btn btn-outline-secondary btn-sm">Tier &amp; Licence</a>
  <a href="<?= APP_URL ?>/audit?verify=1" class="btn btn-outline-secondary btn-sm">Verify Audit Integrity</a>
  <a href="<?= APP_URL ?>/webhooks" class="btn btn-outline-secondary btn-sm">Ops Webhooks</a>
</div>
<form method="post" class="card shadow-sm"><div class="card-body">
  <?= csrf_field() ?>
  <p class="text-muted small">SMTP and tier settings live here (single source of truth). Sensitive values are stored in the database, not in code.</p>
  <div class="row">
    <?php foreach ($rows as $s): ?>
      <div class="col-md-6 mb-3">
        <label class="form-label"><?= escape_html(ucwords(str_replace('_',' ',$s['setting_key']))) ?></label>
        <?php $isSecret = str_contains($s['setting_key'], 'password'); ?>
        <input type="<?= $isSecret ? 'password' : 'text' ?>" name="<?= escape_html($s['setting_key']) ?>" class="form-control"
               value="<?= escape_html($s['setting_value']) ?>" autocomplete="off">
        <?php if ($s['description']): ?><small class="text-muted"><?= escape_html($s['description']) ?></small><?php endif; ?>
      </div>
    <?php endforeach; ?>
  </div>
  <button class="btn btn-primary">Save settings</button>
</div></form>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
