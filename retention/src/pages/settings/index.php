<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_role('admin');
$pdo = get_db();
$orgId = require_org_id();

$activeTab = $_GET['tab'] ?? 'retention';
if (!isset(ORG_SETTING_SECTIONS[$activeTab])) {
    $activeTab = 'retention';
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $tab = $_POST['tab'] ?? $activeTab;
    if (!isset(ORG_SETTING_SECTIONS[$tab])) {
        flash('error', 'Invalid settings section.');
        redirect(APP_URL . '/settings');
    }
    $allowed = array_keys(ORG_SETTING_SECTIONS[$tab]['keys']);
    foreach ($allowed as $key) {
        if (!array_key_exists($key, $_POST)) { continue; }
        $val = trim((string) $_POST[$key]);
        if ($key === 'smtp_pass' && $val === '') { continue; }
        set_setting($pdo, $key, $val, $orgId);
    }
    log_audit($pdo, 'schedule_reviewed', 'system', null, (int) current_user()['id'], ['action' => 'settings_updated', 'tab' => $tab], get_client_ip());
    flash('success', ORG_SETTING_SECTIONS[$tab]['label'] . ' saved.');
    redirect(APP_URL . '/settings?tab=' . urlencode($tab));
}

$page_title = 'Settings';
$active_nav = 'settings';
require __DIR__ . '/../../includes/layout_header.php';
require __DIR__ . '/_nav.php';
echo settings_nav('general');
?>
<div class="d-flex flex-wrap gap-2 mb-3">
  <a href="<?= APP_URL ?>/integrations/tier" class="btn btn-outline-secondary btn-sm"><i class="bi bi-layers"></i> Tier &amp; licence</a>
  <a href="<?= APP_URL ?>/audit?verify=1" class="btn btn-outline-secondary btn-sm"><i class="bi bi-shield-check"></i> Verify audit integrity</a>
  <a href="<?= APP_URL ?>/webhooks" class="btn btn-outline-secondary btn-sm"><i class="bi bi-broadcast"></i> Ops webhooks</a>
</div>

<ul class="nav nav-pills settings-pills mb-4">
  <?php foreach (ORG_SETTING_SECTIONS as $tabKey => $section): ?>
    <li class="nav-item">
      <a class="nav-link<?= $tabKey === $activeTab ? ' active' : '' ?>" href="<?= APP_URL ?>/settings?tab=<?= urlencode($tabKey) ?>">
        <?= escape_html($section['label']) ?>
      </a>
    </li>
  <?php endforeach; ?>
</ul>

<?php
$section = ORG_SETTING_SECTIONS[$activeTab];
$fields = org_settings_for_section($pdo, $orgId, $activeTab);
?>
<div class="card shadow-sm">
  <div class="card-header bg-white">
    <h2 class="h5 mb-1"><?= escape_html($section['label']) ?></h2>
    <p class="text-muted small mb-0"><?= escape_html($section['description']) ?></p>
  </div>
  <div class="card-body">
    <?php if ($activeTab === 'email' && !smtp_is_configured($pdo)): ?>
      <div class="alert alert-warning py-2 small">
        Email is not configured yet. Retention alerts and notifications will not be delivered until SMTP is set up.
      </div>
    <?php endif; ?>
    <form method="post">
      <?= csrf_field() ?>
      <input type="hidden" name="tab" value="<?= escape_html($activeTab) ?>">
      <div class="row">
        <?php foreach ($fields as $key => $field):
            $meta = $field['meta'];
            $type = $meta['type'] ?? 'text';
            $isSecret = $type === 'password';
        ?>
        <div class="col-md-6 mb-3">
          <label class="form-label" for="setting_<?= escape_html($key) ?>"><?= escape_html($meta['label']) ?></label>
          <input id="setting_<?= escape_html($key) ?>"
                 type="<?= $isSecret ? 'password' : escape_html($type === 'number' ? 'number' : 'text') ?>"
                 name="<?= escape_html($key) ?>"
                 class="form-control"
                 value="<?= $isSecret ? '' : escape_html($field['value']) ?>"
                 placeholder="<?= escape_html($meta['placeholder'] ?? ($isSecret ? 'Leave blank to keep current' : '')) ?>"
                 autocomplete="off"
                 <?= $type === 'number' ? 'min="1"' : '' ?>>
          <?php if ($isSecret && $field['value'] !== ''): ?>
            <div class="form-text text-success">A password is saved. Enter a new value only to change it.</div>
          <?php endif; ?>
        </div>
        <?php endforeach; ?>
      </div>
      <button class="btn btn-primary">Save <?= escape_html($section['label']) ?></button>
    </form>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
