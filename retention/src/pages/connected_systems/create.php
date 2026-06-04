<?php
$pdo = get_pdo();
require_login();
$currentUser = current_user();
$types = ['crm', 'core_banking', 'hr_platform', 'customer_db', 'loan_management', 'ecommerce', 'custom'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validate_csrf($_POST['csrf_token'] ?? '')) {
        flash_set('danger', 'Invalid form submission.');
        redirect('/retention/connected-systems/create');
    }

    $name = trim($_POST['name'] ?? '');
    $systemType = $_POST['system_type'] ?? 'custom';
    $baseUrl = trim($_POST['base_url'] ?? '');
    $description = trim($_POST['description'] ?? '');
    $isActive = isset($_POST['is_active']) ? 1 : 0;

    if ($name === '') {
        flash_set('danger', 'System name is required.');
        redirect('/retention/connected-systems/create');
    }

    if (!in_array($systemType, $types, true)) {
        flash_set('danger', 'Invalid connected system type.');
        redirect('/retention/connected-systems/create');
    }

    if ($baseUrl !== '' && filter_var($baseUrl, FILTER_VALIDATE_URL) === false) {
        flash_set('danger', 'Base URL must be a valid URL.');
        redirect('/retention/connected-systems/create');
    }

    if (strlen($name) > 255) {
        flash_set('danger', 'System name must be 255 characters or fewer.');
        redirect('/retention/connected-systems/create');
    }

    if ($baseUrl !== '' && strlen($baseUrl) > 500) {
        flash_set('danger', 'Base URL must be 500 characters or fewer.');
        redirect('/retention/connected-systems/create');
    }

    $stmt = $pdo->prepare(
        'INSERT INTO connected_systems (name, system_type, base_url, description, is_active, created_by, created_at, updated_at)
         VALUES (:name, :system_type, :base_url, :description, :is_active, :created_by, NOW(), NOW())'
    );
    $stmt->execute([
        'name' => $name,
        'system_type' => $systemType,
        'base_url' => $baseUrl !== '' ? $baseUrl : null,
        'description' => $description,
        'is_active' => $isActive,
        'created_by' => $currentUser['id'] ?? null,
    ]);

    flash_set('success', 'Connected system registered successfully.');
    redirect('/retention/connected-systems');
}

$types = ['crm', 'core_banking', 'hr_platform', 'customer_db', 'loan_management', 'ecommerce', 'custom'];
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Register connected system</h1>
    <p class="text-muted mb-0">Add an external system for enterprise API integration.</p>
  </div>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <form method="post">
      <input type="hidden" name="csrf_token" value="<?= escape_html(csrf_token()) ?>">
      <div class="mb-3">
        <label class="form-label">System name</label>
        <input type="text" name="name" class="form-control" required value="<?= escape_html($_POST['name'] ?? '') ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">System type</label>
        <select name="system_type" class="form-select">
          <?php foreach ($types as $type): ?>
            <option value="<?= escape_html($type) ?>" <?= ($_POST['system_type'] ?? '') === $type ? 'selected' : '' ?>><?= escape_html($type) ?></option>
          <?php endforeach; ?>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">Base URL</label>
        <input type="url" name="base_url" class="form-control" value="<?= escape_html($_POST['base_url'] ?? '') ?>">
        <div class="form-text">Optional endpoint base URL used for outbound dispatch.</div>
      </div>
      <div class="mb-3">
        <label class="form-label">Description</label>
        <textarea name="description" class="form-control" rows="3"><?= escape_html($_POST['description'] ?? '') ?></textarea>
      </div>
      <div class="form-check mb-3">
        <input class="form-check-input" type="checkbox" id="isActive" name="is_active" <?= isset($_POST['is_active']) ? 'checked' : '' ?> value="1">
        <label class="form-check-label" for="isActive">Active</label>
      </div>
      <button type="submit" class="btn btn-primary">Create connected system</button>
    </form>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
