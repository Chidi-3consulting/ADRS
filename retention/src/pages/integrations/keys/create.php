<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);
$error = null; $rawKey = null;
$allPerms = ['ingest','batch','consent','health','categories'];
$systems = $pdo->query("SELECT id, name FROM connected_systems WHERE is_active=1 ORDER BY name")->fetchAll();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $systemId = (int) ($_POST['system_id'] ?? 0);
    $name = trim($_POST['key_name'] ?? '');
    $perms = array_values(array_intersect($allPerms, $_POST['permissions'] ?? []));
    $rate = max(1, (int) ($_POST['rate_limit_per_min'] ?? 60));
    if ($systemId <= 0 || $name === '') { $error = 'System and key name are required.'; }
    elseif (empty($perms)) { $error = 'Select at least one permission.'; }
    else {
        $created = create_api_key($pdo, $systemId, $name, $perms, $rate, (int) current_user()['id']);
        $rawKey = $created['raw'];
    }
}
$page_title = 'New API Key';
$active_nav = 'integrations';
require __DIR__ . '/../../../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:640px"><div class="card-body">
  <h1 class="h4 mb-3">Create API Key</h1>
  <?php if ($rawKey): ?>
    <div class="alert alert-success">
      <strong>Key created.</strong> Copy it now — it will <strong>never be shown again</strong>:
      <div class="input-group mt-2"><input class="form-control font-monospace" value="<?= escape_html($rawKey) ?>" readonly data-select></div>
    </div>
    <a href="<?= APP_URL ?>/integrations/keys" class="btn btn-primary">Done</a>
  <?php else: ?>
    <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
    <?php if (empty($systems)): ?>
      <div class="alert alert-warning">Register a connected system first.</div>
    <?php else: ?>
    <form method="post">
      <?= csrf_field() ?>
      <div class="mb-3"><label class="form-label">Connected system *</label>
        <select name="system_id" class="form-select" required><option value="">Select…</option>
          <?php foreach ($systems as $s): ?><option value="<?= (int)$s['id'] ?>"><?= escape_html($s['name']) ?></option><?php endforeach; ?>
        </select></div>
      <div class="mb-3"><label class="form-label">Key name *</label><input name="key_name" class="form-control" required placeholder="e.g. Production Key"></div>
      <div class="mb-3"><label class="form-label">Permissions *</label>
        <?php foreach ($allPerms as $p): ?>
          <div class="form-check"><input type="checkbox" class="form-check-input" id="p_<?= $p ?>" name="permissions[]" value="<?= $p ?>" <?= in_array($p,['ingest','health'],true)?'checked':'' ?>><label class="form-check-label" for="p_<?= $p ?>"><?= $p ?></label></div>
        <?php endforeach; ?></div>
      <div class="mb-3"><label class="form-label">Rate limit (requests/min)</label><input type="number" name="rate_limit_per_min" class="form-control" value="60" min="1"></div>
      <button class="btn btn-primary">Create key</button>
      <a href="<?= APP_URL ?>/integrations/keys" class="btn btn-secondary ms-2">Cancel</a>
    </form>
    <?php endif; ?>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../../includes/layout_footer.php'; ?>
