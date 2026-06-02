<?php
$pdo = get_pdo();
$currentUser = current_user();
$allowedPermissions = ['ingest', 'batch', 'consent', 'health', 'categories'];
$stmt = $pdo->query('SELECT id, name FROM connected_systems WHERE is_active = 1 ORDER BY name');
$systems = $stmt->fetchAll(PDO::FETCH_ASSOC);
$generatedKey = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validate_csrf($_POST['csrf_token'] ?? '')) {
        flash_set('danger', 'Invalid form submission.');
        redirect('/retention/api-keys/create');
    }

    $systemId = (int)($_POST['system_id'] ?? 0);
    $keyName = trim($_POST['key_name'] ?? '');
    $permissions = array_values(array_intersect($allowedPermissions, $_POST['permissions'] ?? []));
    $rateLimit = max(1, (int)($_POST['rate_limit_per_min'] ?? 60));
    $expiresAt = trim($_POST['expires_at'] ?? '');
    $expiresAt = $expiresAt !== '' ? str_replace('T', ' ', $expiresAt) : '';
    $isActive = isset($_POST['is_active']) ? 1 : 0;

    $systemIds = array_column($systems, 'id');
    if ($systemId === 0 || $keyName === '' || empty($permissions) || !in_array($systemId, $systemIds, true)) {
        flash_set('danger', 'A valid system, key name, and at least one permission are required.');
        redirect('/retention/api-keys/create');
    }

    if (strlen($keyName) > 100) {
        flash_set('danger', 'Key name must be 100 characters or fewer.');
        redirect('/retention/api-keys/create');
    }

    if ($expiresAt !== '' && strtotime($expiresAt) === false) {
        flash_set('danger', 'Expires at must be a valid date/time.');
        redirect('/retention/api-keys/create');
    }

    $rawKey = 'adrs_' . bin2hex(random_bytes(16));
    $keyHash = hash('sha256', $rawKey);
    $keyPrefix = substr($rawKey, 0, 12);

    $stmt = $pdo->prepare(
        'INSERT INTO api_keys (system_id, key_name, key_hash, key_prefix, permissions, rate_limit_per_min, is_active, expires_at, created_by, created_at)
         VALUES (:system_id, :key_name, :key_hash, :key_prefix, :permissions, :rate_limit_per_min, :is_active, :expires_at, :created_by, NOW())'
    );
    $stmt->execute([
        'system_id' => $systemId,
        'key_name' => $keyName,
        'key_hash' => $keyHash,
        'key_prefix' => $keyPrefix,
        'permissions' => json_encode(array_values($permissions), JSON_UNESCAPED_UNICODE),
        'rate_limit_per_min' => $rateLimit,
        'is_active' => $isActive,
        'expires_at' => $expiresAt !== '' ? $expiresAt : null,
        'created_by' => $currentUser['id'] ?? null,
    ]);

    session_start();
    $_SESSION['created_api_key_raw'] = $rawKey;
    flash_set('success', 'API key created successfully. Copy it now before leaving the page.');
    redirect('/retention/api-keys/create');
}

session_start();
if (!empty($_SESSION['created_api_key_raw'])) {
    $generatedKey = $_SESSION['created_api_key_raw'];
    unset($_SESSION['created_api_key_raw']);
}
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Create API key</h1>
    <p class="text-muted mb-0">Generate a credential for an external system to call the ADRS enterprise API.</p>
  </div>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if ($generatedKey): ?>
      <div class="alert alert-success">
        <p class="mb-2"><strong>API key created.</strong> Copy this value now; it will not be shown again.</p>
        <pre class="p-2 bg-light rounded"><?= escape_html($generatedKey) ?></pre>
      </div>
    <?php endif; ?>

    <?php if (empty($systems)): ?>
      <div class="alert alert-warning">
        No active connected systems are available. Create a connected system first.
      </div>
    <?php else: ?>
      <form method="post">
        <input type="hidden" name="csrf_token" value="<?= escape_html(csrf_token()) ?>">
        <div class="mb-3">
          <label class="form-label">Connected system</label>
          <select name="system_id" class="form-select" required>
            <option value="">Select system</option>
            <?php foreach ($systems as $system): ?>
              <option value="<?= escape_html($system['id']) ?>" <?= ((int)($_POST['system_id'] ?? 0) === (int)$system['id']) ? 'selected' : '' ?>><?= escape_html($system['name']) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <div class="mb-3">
          <label class="form-label">Key name</label>
          <input type="text" name="key_name" class="form-control" required value="<?= escape_html($_POST['key_name'] ?? '') ?>">
        </div>
        <div class="mb-3">
          <label class="form-label">Permissions</label>
          <div class="row">
            <?php foreach ($allowedPermissions as $permission): ?>
              <div class="col-md-4">
                <div class="form-check">
                  <input class="form-check-input" type="checkbox" id="perm_<?= escape_html($permission) ?>" name="permissions[]" value="<?= escape_html($permission) ?>" <?= in_array($permission, $_POST['permissions'] ?? [], true) ? 'checked' : '' ?>>
                  <label class="form-check-label" for="perm_<?= escape_html($permission) ?>"><?= escape_html($permission) ?></label>
                </div>
              </div>
            <?php endforeach; ?>
          </div>
        </div>
        <div class="mb-3">
          <label class="form-label">Rate limit per minute</label>
          <input type="number" name="rate_limit_per_min" class="form-control" min="1" value="<?= escape_html($_POST['rate_limit_per_min'] ?? '60') ?>">
        </div>
        <div class="mb-3">
          <label class="form-label">Expires at</label>
          <input type="datetime-local" name="expires_at" class="form-control" value="<?= escape_html($_POST['expires_at'] ?? '') ?>">
          <div class="form-text">Optional. Leave blank for no expiration.</div>
        </div>
        <div class="form-check mb-3">
          <input class="form-check-input" type="checkbox" id="isActive" name="is_active" value="1" <?= isset($_POST['is_active']) ? 'checked' : '' ?>>
          <label class="form-check-label" for="isActive">Active</label>
        </div>
        <button type="submit" class="btn btn-primary">Create API key</button>
      </form>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
