<?php
$pdo = get_pdo();
require_login();
$currentUser = current_user();
$id = (int)($_GET['id'] ?? 0);
$types = ['crm', 'core_banking', 'hr_platform', 'customer_db', 'loan_management', 'ecommerce', 'custom'];

$stmt = $pdo->prepare('SELECT * FROM connected_systems WHERE id = :id LIMIT 1');
$stmt->execute(['id' => $id]);
$system = $stmt->fetch(PDO::FETCH_ASSOC);
if ($system === false) {
    http_response_code(404);
    echo 'Connected system not found.';
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validate_csrf($_POST['csrf_token'] ?? '')) {
        flash_set('danger', 'Invalid form submission.');
        redirect('/retention/connected-systems/edit?id=' . $id);
    }

    $name = trim($_POST['name'] ?? '');
    $systemType = $_POST['system_type'] ?? 'custom';
    $baseUrl = trim($_POST['base_url'] ?? '');
    $description = trim($_POST['description'] ?? '');
    $isActive = isset($_POST['is_active']) ? 1 : 0;

    if ($name === '') {
        flash_set('danger', 'System name is required.');
        redirect('/retention/connected-systems/edit?id=' . $id);
    }

    if (!in_array($systemType, $types, true)) {
        flash_set('danger', 'Invalid connected system type.');
        redirect('/retention/connected-systems/edit?id=' . $id);
    }

    if ($baseUrl !== '' && filter_var($baseUrl, FILTER_VALIDATE_URL) === false) {
        flash_set('danger', 'Base URL must be a valid URL.');
        redirect('/retention/connected-systems/edit?id=' . $id);
    }

    if (strlen($name) > 255) {
        flash_set('danger', 'System name must be 255 characters or fewer.');
        redirect('/retention/connected-systems/edit?id=' . $id);
    }

    if ($baseUrl !== '' && strlen($baseUrl) > 500) {
        flash_set('danger', 'Base URL must be 500 characters or fewer.');
        redirect('/retention/connected-systems/edit?id=' . $id);
    }

    $update = $pdo->prepare(
        'UPDATE connected_systems
         SET name = :name, system_type = :system_type, base_url = :base_url, description = :description, is_active = :is_active, updated_at = NOW()
         WHERE id = :id'
    );
    $update->execute([
        'name' => $name,
        'system_type' => $systemType,
        'base_url' => $baseUrl !== '' ? $baseUrl : null,
        'description' => $description,
        'is_active' => $isActive,
        'id' => $id,
    ]);

    flash_set('success', 'Connected system updated successfully.');
    redirect('/retention/connected-systems');
}

$types = ['crm', 'core_banking', 'hr_platform', 'customer_db', 'loan_management', 'ecommerce', 'custom'];
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Edit connected system</h1>
    <p class="text-muted mb-0">Update the external system configuration and integration settings.</p>
  </div>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <form method="post">
      <input type="hidden" name="csrf_token" value="<?= escape_html(csrf_token()) ?>">
      <div class="mb-3">
        <label class="form-label">System name</label>
        <input type="text" name="name" class="form-control" required value="<?= escape_html($_POST['name'] ?? $system['name']) ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">System type</label>
        <select name="system_type" class="form-select">
          <?php foreach ($types as $type): ?>
            <option value="<?= escape_html($type) ?>" <?= ($_POST['system_type'] ?? $system['system_type']) === $type ? 'selected' : '' ?>><?= escape_html($type) ?></option>
          <?php endforeach; ?>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">Base URL</label>
        <input type="url" name="base_url" class="form-control" value="<?= escape_html($_POST['base_url'] ?? $system['base_url']) ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Description</label>
        <textarea name="description" class="form-control" rows="3"><?= escape_html($_POST['description'] ?? $system['description']) ?></textarea>
      </div>
      <div class="form-check mb-3">
        <input class="form-check-input" type="checkbox" id="isActive" name="is_active" value="1" <?= isset($_POST['is_active']) ? 'checked' : ($system['is_active'] ? 'checked' : '') ?> >
        <label class="form-check-label" for="isActive">Active</label>
      </div>
      <button type="submit" class="btn btn-primary">Save changes</button>
      <a href="/retention/connected-systems" class="btn btn-secondary ms-2">Cancel</a>
    </form>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
