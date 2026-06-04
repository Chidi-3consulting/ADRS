<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/enterprise_lib.php';
require_role('admin');           // NOT enterprise-gated: this is the upgrade entry point.
$pdo = get_db();
$error = null;
$tier = get_setting($pdo, 'adrs_tier', 'core');

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $action = $_POST['action'] ?? '';
    if ($action === 'upgrade') {
        $licence = trim($_POST['licence_key'] ?? '');
        if ($licence === '') {
            $error = 'A licence key is required to activate Enterprise.';
        } else {
            set_setting($pdo, 'adrs_tier', 'enterprise');
            set_setting($pdo, 'enterprise_licence_key', $licence);
            set_setting($pdo, 'enterprise_api_enabled', '1');
            log_audit($pdo, 'schedule_reviewed', 'system', null, (int) current_user()['id'], ['tier_upgraded' => 'enterprise'], get_client_ip());
            flash('success', 'ADRS Enterprise activated. Integration features are now available.');
            redirect(APP_URL . '/integrations');
        }
    } elseif ($action === 'toggle_api') {
        set_setting($pdo, 'enterprise_api_enabled', get_setting($pdo, 'enterprise_api_enabled', '0') === '1' ? '0' : '1');
        flash('success', 'API state updated.');
        redirect(APP_URL . '/integrations/tier');
    }
}
$tier = get_setting($pdo, 'adrs_tier', 'core');
$apiOn = get_setting($pdo, 'enterprise_api_enabled', '0') === '1';
$page_title = 'Tier & Licence';
$active_nav = has_role('admin') ? 'settings' : '';
require __DIR__ . '/../../includes/layout_header.php';
?>
<h1 class="h4 mb-3">Deployment Tier &amp; Licence</h1>
<div class="card shadow-sm mb-3" style="max-width:720px"><div class="card-body">
  <p>Current tier: <span class="badge bg-<?= $tier==='enterprise'?'success':'secondary' ?> fs-6"><?= strtoupper(escape_html($tier)) ?></span></p>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>

  <?php if ($tier !== 'enterprise'): ?>
    <p class="text-muted">ADRS Core is active. Enter your Enterprise licence key to unlock the REST API, automatic data capture, connected systems, and outbound disposal dispatch. Your existing Core data is preserved.</p>
    <form method="post">
      <?= csrf_field() ?><input type="hidden" name="action" value="upgrade">
      <div class="mb-3" style="max-width:420px"><label class="form-label">Enterprise licence key</label><input name="licence_key" class="form-control" required placeholder="ADRS-ENT-XXXX-XXXX"></div>
      <button class="btn btn-primary">Activate Enterprise</button>
    </form>
  <?php else: ?>
    <div class="alert alert-success">Enterprise is active. Downgrade is not offered here to protect cross-system data integrity — contact 3Consulting if you need to change tiers.</div>
    <p>REST API: <span class="badge bg-<?= $apiOn?'success':'secondary' ?>"><?= $apiOn?'enabled':'disabled' ?></span></p>
    <form method="post"><?= csrf_field() ?><input type="hidden" name="action" value="toggle_api"><button class="btn btn-outline-<?= $apiOn?'warning">Disable':'success">Enable' ?> REST API</button></form>
    <a href="<?= APP_URL ?>/integrations" class="btn btn-link">Go to Integrations →</a>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
