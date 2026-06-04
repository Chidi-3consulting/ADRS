<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);

$systems  = (int) $pdo->query("SELECT COUNT(*) FROM connected_systems WHERE is_active=1")->fetchColumn();
$keys     = (int) $pdo->query("SELECT COUNT(*) FROM api_keys WHERE is_active=1 AND revoked_at IS NULL")->fetchColumn();
$qPending = (int) $pdo->query("SELECT COUNT(*) FROM intake_queue WHERE status='pending'")->fetchColumn();
$qFailed  = (int) $pdo->query("SELECT COUNT(*) FROM intake_queue WHERE status='failed'")->fetchColumn();
$dPending = (int) $pdo->query("SELECT COUNT(*) FROM disposal_dispatches WHERE status='pending'")->fetchColumn();
$synced   = (int) $pdo->query("SELECT COALESCE(SUM(records_synced),0) FROM connected_systems")->fetchColumn();
$apiOn    = get_setting($pdo, 'enterprise_api_enabled', '0') === '1';

$page_title = 'Integrations';
$active_nav = 'integrations';
require __DIR__ . '/../../includes/layout_header.php';
function ecard($label, $val, $href = null, $cls = '') {
    $inner = '<div class="text-muted small">' . escape_html($label) . '</div><div class="h3 mb-0 ' . $cls . '">' . escape_html($val) . '</div>';
    $link = $href ? '<a href="' . $href . '" class="stretched-link"></a>' : '';
    echo '<div class="col-md-3"><div class="card shadow-sm"><div class="card-body position-relative">' . $inner . $link . '</div></div></div>';
}
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Enterprise Integrations</h1>
  <span class="badge <?= $apiOn ? 'bg-success' : 'bg-secondary' ?>">REST API <?= $apiOn ? 'ENABLED' : 'disabled' ?></span>
</div>
<div class="row g-3 mb-3">
  <?php
    ecard('Connected systems', $systems, APP_URL . '/integrations/systems');
    ecard('Active API keys', $keys, APP_URL . '/integrations/keys');
    ecard('Records synced', $synced);
    ecard('Intake pending', $qPending, APP_URL . '/integrations/queue', $qPending ? 'text-warning' : '');
  ?>
</div>
<div class="row g-3 mb-3">
  <?php
    ecard('Intake failed', $qFailed, APP_URL . '/integrations/queue', $qFailed ? 'text-danger' : '');
    ecard('Dispatch pending', $dPending, APP_URL . '/integrations/dispatch');
    ecard('Auto-categorisation rules', (int) $pdo->query("SELECT COUNT(*) FROM auto_categorization_rules WHERE is_active=1")->fetchColumn(), APP_URL . '/integrations/rules');
    ecard('Field mappings', (int) $pdo->query("SELECT COUNT(*) FROM field_mappings")->fetchColumn(), APP_URL . '/integrations/mappings');
  ?>
</div>
<div class="card shadow-sm"><div class="card-body">
  <h5 class="card-title">Manage</h5>
  <a href="<?= APP_URL ?>/integrations/systems" class="btn btn-outline-primary btn-sm mb-1">Connected Systems</a>
  <a href="<?= APP_URL ?>/integrations/keys" class="btn btn-outline-primary btn-sm mb-1">API Keys</a>
  <a href="<?= APP_URL ?>/integrations/rules" class="btn btn-outline-primary btn-sm mb-1">Auto-categorisation Rules</a>
  <a href="<?= APP_URL ?>/integrations/mappings" class="btn btn-outline-primary btn-sm mb-1">Field Mappings</a>
  <a href="<?= APP_URL ?>/integrations/logs" class="btn btn-outline-secondary btn-sm mb-1">Integration Logs</a>
  <a href="<?= APP_URL ?>/integrations/queue" class="btn btn-outline-secondary btn-sm mb-1">Intake Queue</a>
  <a href="<?= APP_URL ?>/integrations/dispatch" class="btn btn-outline-secondary btn-sm mb-1">Disposal Dispatch</a>
  <a href="<?= APP_URL ?>/integrations/tier" class="btn btn-outline-dark btn-sm mb-1">Tier &amp; Licence</a>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
