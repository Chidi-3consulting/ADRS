<?php
$pdo = get_pdo();
require_login();
$currentUser = current_user();
$id = (int)($_GET['id'] ?? 0);
$allowedPermissions = ['ingest', 'batch', 'consent', 'health', 'categories'];

$stmt = $pdo->prepare('SELECT api_keys.*, connected_systems.name AS system_name FROM api_keys LEFT JOIN connected_systems ON api_keys.system_id = connected_systems.id WHERE api_keys.id = :id LIMIT 1');
$stmt->execute(['id' => $id]);
$key = $stmt->fetch(PDO::FETCH_ASSOC);
if ($key === false) {
    http_response_code(404);
    echo 'API key not found.';
    exit;
}

$systems = $pdo->query('SELECT id, name FROM connected_systems ORDER BY name ASC')->fetchAll(PDO::FETCH_ASSOC);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validate_csrf($_POST['csrf_token'] ?? '')) {
        flash_set('danger', 'Invalid form submission.');
        redirect('/retention/api-keys/edit?id=' . $id);
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
        flash_set('danger', 'A valid connected system, key name, and at least one permission are required.');
        redirect('/retention/api-keys/edit?id=' . $id);
    }

    if (strlen($keyName) > 100) {
        flash_set('danger', 'Key name must be 100 characters or fewer.');
        redirect('/retention/api-keys/edit?id=' . $id);
    }

    if ($expiresAt !== '' && strtotime($expiresAt) === false) {
        flash_set('danger', 'Expires at must be a valid date/time.');
        redirect('/retention/api-keys/edit?id=' . $id);
    }

    $revokedAt = $isActive ? null : ($key['is_active'] ? date('Y-m-d H:i:s') : $key['revoked_at']);
    $update = $pdo->prepare(
        'UPDATE api_keys
         SET system_id = :system_id,
             key_name = :key_name,
             permissions = :permissions,
             rate_limit_per_min = :rate_limit_per_min,
             expires_at = :expires_at,
             is_active = :is_active,
             revoked_at = :revoked_at,
             updated_at = NOW()
         WHERE id = :id'
    );
    $update->execute([
        'system_id' => $systemId,
        'key_name' => $keyName,
        'permissions' => json_encode(array_values($permissions)),
        'rate_limit_per_min' => $rateLimit,
        'expires_at' => $expiresAt !== '' ? $expiresAt : null,
        'is_active' => $isActive,
        'revoked_at' => $revokedAt,
        'id' => $id,
    ]);

    flash_set('success', 'API key updated successfully.');
    redirect('/retention/api-keys');
}

$permissionsString = implode(', ', json_decode($key['permissions'] ?? '[]', true) ?: []);
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Edit API key</h1>
    <p class="text-muted mb-0">Update permissions, expiration, and connectivity for this API key.</p>
  </div>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <form method="post">
      <input type="hidden" name="csrf_token" value="<?= escape_html(csrf_token()) ?>">
      <div class="mb-3">
        <label class="form-label">Key name</label>
        <input type="text" name="key_name" class="form-control" required value="<?= escape_html($_POST['key_name'] ?? $key['key_name']) ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Connected system</label>
        <select name="system_id" class="form-select" required>
          <option value="">Select a system</option>
          <?php foreach ($systems as $system): ?>
            <option value="<?= escape_html($system['id']) ?>" <?= ((string)($_POST['system_id'] ?? $key['system_id']) === (string)$system['id']) ? 'selected' : '' ?>><?= escape_html($system['name']) ?></option>
          <?php endforeach; ?>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">Permissions</label>
        <div class="row">
          <?php foreach ($allowedPermissions as $permission): ?>
            <div class="col-md-4">
              <div class="form-check">
                <input class="form-check-input" type="checkbox" id="perm_<?= escape_html($permission) ?>" name="permissions[]" value="<?= escape_html($permission) ?>" <?= in_array($permission, $_POST['permissions'] ?? json_decode($key['permissions'] ?? '[]', true), true) ? 'checked' : '' ?>>
                <label class="form-check-label" for="perm_<?= escape_html($permission) ?>"><?= escape_html($permission) ?></label>
              </div>
            </div>
          <?php endforeach; ?>
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label">Key prefix</label>
        <input type="text" class="form-control" value="<?= escape_html($key['key_prefix']) ?>" readonly>
      </div>
      <div class="mb-3">
        <label class="form-label">Rate limit per minute</label>
        <input type="number" name="rate_limit_per_min" class="form-control" min="1" value="<?= escape_html($_POST['rate_limit_per_min'] ?? $key['rate_limit_per_min']) ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Expires at</label>
        <input type="datetime-local" name="expires_at" class="form-control" value="<?= escape_html($_POST['expires_at'] ?? ($key['expires_at'] ? date('Y-m-d\TH:i', strtotime($key['expires_at'])) : '')) ?>">
      </div>
      <div class="form-check mb-3">
        <input class="form-check-input" type="checkbox" id="isActive" name="is_active" value="1" <?= isset($_POST['is_active']) ? 'checked' : ($key['is_active'] ? 'checked' : '') ?> >
        <label class="form-check-label" for="isActive">Active</label>
      </div>
      <button type="submit" class="btn btn-primary">Save changes</button>
      <a href="/retention/api-keys" class="btn btn-secondary ms-2">Cancel</a>
    </form>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
