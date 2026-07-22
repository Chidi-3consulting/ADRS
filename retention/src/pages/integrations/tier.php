<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/enterprise_lib.php';
require_once __DIR__ . '/../../includes/billing_lib.php';
require_role('admin');
$pdo = get_db();
$error = null;
$orgId = require_org_id();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $action = $_POST['action'] ?? '';
    if ($action === 'upgrade') {
        $licence = trim($_POST['licence_key'] ?? '');
        if ($licence === '') {
            $error = 'A licence key is required to activate API access.';
        } elseif (!redeem_enterprise_licence($pdo, $licence, $orgId)) {
            $error = 'Invalid or already-used licence key.';
        } else {
            log_audit($pdo, 'schedule_reviewed', 'system', null, (int) current_user()['id'], ['tier_upgraded' => 'enterprise'], get_client_ip());
            flash('success', 'Licence activated. Integration features are now available.');
            redirect(APP_URL . '/integrations');
        }
    } elseif ($action === 'toggle_api') {
        set_setting($pdo, 'enterprise_api_enabled', get_setting($pdo, 'enterprise_api_enabled', '0') === '1' ? '0' : '1');
        flash('success', 'API state updated.');
        redirect(APP_URL . '/integrations/tier');
    }
}
$apiOn = get_setting($pdo, 'enterprise_api_enabled', '0') === '1';
$page_title = 'Licence & API Access';
$active_nav = has_role('admin') ? 'settings' : '';
require __DIR__ . '/../../includes/layout_header.php';
?>
<h1 class="h4 mb-3">Licence &amp; API Access</h1>
<div class="card shadow-sm mb-3" style="max-width:720px"><div class="card-body">
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>

  <?php if (!get_setting($pdo, 'enterprise_api_enabled', '0') && !organization_has_access($pdo, $orgId)): ?>
    <p class="text-muted">Enter your product licence key to unlock full platform integrations, REST API access, and automated disposal instructions.</p>
    <form method="post">
      <?= csrf_field() ?><input type="hidden" name="action" value="upgrade">
      <div class="mb-3" style="max-width:420px">
        <label class="form-label">Licence key</label>
        <input name="licence_key" class="form-control" required placeholder="ADRS-LIC-XXXX-XXXX">
      </div>
      <button class="btn btn-primary">Activate Licence</button>
    </form>
  <?php else: ?>
    <div class="alert alert-success">Platform Licence is active and valid.</div>
    <p>REST API: <span class="badge bg-<?= $apiOn?'success':'secondary' ?>"><?= $apiOn?'enabled':'disabled' ?></span></p>
    <form method="post" class="mb-3"><?= csrf_field() ?><input type="hidden" name="action" value="toggle_api"><button class="btn btn-outline-<?= $apiOn?'warning">Disable':'success">Enable' ?> REST API</button></form>
    <a href="<?= APP_URL ?>/integrations" class="btn btn-link px-0">Go to Integrations →</a>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
