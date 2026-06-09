<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);
$orgId = require_org_id();

$systemsStmt = $pdo->prepare('SELECT COUNT(*) FROM connected_systems WHERE organization_id = :o AND is_active = 1');
$systemsStmt->execute(['o' => $orgId]);
$systems = (int) $systemsStmt->fetchColumn();
$keysStmt = $pdo->prepare('SELECT COUNT(*) FROM api_keys WHERE organization_id = :o AND is_active = 1 AND revoked_at IS NULL');
$keysStmt->execute(['o' => $orgId]);
$keys = (int) $keysStmt->fetchColumn();
$qPendingStmt = $pdo->prepare("SELECT COUNT(*) FROM intake_queue WHERE organization_id = :o AND status = 'pending'");
$qPendingStmt->execute(['o' => $orgId]);
$qPending = (int) $qPendingStmt->fetchColumn();
$qFailedStmt = $pdo->prepare("SELECT COUNT(*) FROM intake_queue WHERE organization_id = :o AND status = 'failed'");
$qFailedStmt->execute(['o' => $orgId]);
$qFailed = (int) $qFailedStmt->fetchColumn();
$dPendingStmt = $pdo->prepare("SELECT COUNT(*) FROM disposal_dispatches WHERE organization_id = :o AND status = 'pending'");
$dPendingStmt->execute(['o' => $orgId]);
$dPending = (int) $dPendingStmt->fetchColumn();
$syncedStmt = $pdo->prepare('SELECT COALESCE(SUM(records_synced), 0) FROM connected_systems WHERE organization_id = :o');
$syncedStmt->execute(['o' => $orgId]);
$synced = (int) $syncedStmt->fetchColumn();
$rulesStmt = $pdo->prepare('SELECT COUNT(*) FROM auto_categorization_rules WHERE organization_id = :o AND is_active = 1');
$rulesStmt->execute(['o' => $orgId]);
$ruleCount = (int) $rulesStmt->fetchColumn();
$mapsStmt = $pdo->prepare('SELECT COUNT(*) FROM field_mappings WHERE organization_id = :o');
$mapsStmt->execute(['o' => $orgId]);
$mapCount = (int) $mapsStmt->fetchColumn();
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
    ecard('Auto-categorisation rules', $ruleCount, APP_URL . '/integrations/rules');
    ecard('Field mappings', $mapCount, APP_URL . '/integrations/mappings');
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
