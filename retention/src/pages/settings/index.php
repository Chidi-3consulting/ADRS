<?php
$pdo = get_pdo();
$error = null;

$settings = [];
$stmt = $pdo->query('SELECT `key`, `value`, `description` FROM system_settings ORDER BY `key` ASC');
foreach ($stmt->fetchAll() as $setting) {
    $settings[$setting['key']] = $setting;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validate_csrf($_POST['csrf_token'] ?? '')) {
        $error = 'Invalid CSRF token.';
    } else {
        foreach ($settings as $key => $setting) {
            $value = trim($_POST[$key] ?? '');
            $stmt = $pdo->prepare('UPDATE system_settings SET `value` = :value WHERE `key` = :key');
            $stmt->execute(['value' => $value, 'key' => $key]);
        }
        flash_set('success', 'Settings updated successfully.');
        redirect('/retention/settings');
    }
}
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="card shadow-sm">
  <div class="card-body">
    <h1 class="h4 mb-3">System Settings</h1>
    <?php if ($error): ?>
      <div class="alert alert-danger"><?= escape_html($error) ?></div>
    <?php endif; ?>
    <form method="post">
      <input type="hidden" name="csrf_token" value="<?= escape_html(csrf_token()) ?>">
      <div class="row">
        <?php foreach ($settings as $setting): ?>
          <div class="mb-3 col-md-6">
            <label class="form-label"><?= escape_html(ucwords(str_replace('_', ' ', $setting['key']))) ?></label>
            <input type="text" name="<?= escape_html($setting['key']) ?>" class="form-control" value="<?= escape_html($_POST[$setting['key']] ?? $setting['value']) ?>">
            <?php if ($setting['description']): ?>
              <small class="text-muted"><?= escape_html($setting['description']) ?></small>
            <?php endif; ?>
          </div>
        <?php endforeach; ?>
      </div>
      <button class="btn btn-primary">Save settings</button>
    </form>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
