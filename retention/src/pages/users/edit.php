<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_role('admin');
$pdo = get_db();
$id = (int) ($_GET['id'] ?? 0);
$stmt = $pdo->prepare("SELECT * FROM users WHERE id=:id AND deleted_at IS NULL");
$stmt->execute(['id' => $id]);
$user = $stmt->fetch();
if (!$user) { http_response_code(404); require __DIR__ . '/../../../404.php'; exit; }
assert_org_row($user);
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $name = trim($_POST['name'] ?? '');
    $role = $_POST['role'] ?? $user['role'];
    $active = isset($_POST['is_active']) ? 1 : 0;
    $newPass = $_POST['password'] ?? '';
    if ($name === '' || !in_array($role, ['admin','dpo','data_owner'], true)) {
        $error = 'Name and a valid role are required.';
    } else {
        $pdo->prepare("UPDATE users SET name=:n, role=:r, is_active=:a WHERE id=:id")
            ->execute(['n' => $name, 'r' => $role, 'a' => $active, 'id' => $id]);
        if ($newPass !== '') {
            if (($pwErr = password_policy_error($newPass)) !== null) { $error = $pwErr; }
            else { $pdo->prepare("UPDATE users SET password_hash=:p WHERE id=:id")->execute(['p' => password_hash($newPass, PASSWORD_BCRYPT), 'id' => $id]); }
        }
        if (!$error) {
            log_audit($pdo, 'user_updated', 'user', $id, (int) current_user()['id'], ['role' => $role, 'is_active' => $active], get_client_ip());
            flash('success', 'User updated.');
            redirect(APP_URL . '/users');
        }
    }
}
$page_title = 'Edit User';
$active_nav = 'users';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:560px"><div class="card-body">
  <h1 class="h4 mb-3">Edit User</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Name *</label><input name="name" class="form-control" required value="<?= escape_html($_POST['name'] ?? $user['name']) ?>"></div>
    <div class="mb-3"><label class="form-label">Email</label><input class="form-control" value="<?= escape_html($user['email']) ?>" disabled></div>
    <div class="mb-3"><label class="form-label">Role *</label>
      <select name="role" class="form-select">
        <?php foreach (['data_owner'=>'Data Owner','dpo'=>'DPO','admin'=>'Administrator'] as $v=>$l): ?>
          <option value="<?= $v ?>" <?= ($_POST['role'] ?? $user['role'])===$v?'selected':'' ?>><?= $l ?></option>
        <?php endforeach; ?>
      </select></div>
    <div class="mb-3"><label class="form-label">Reset password (optional, min 10)</label><input type="password" name="password" class="form-control" minlength="10"></div>
    <div class="form-check mb-3"><input type="checkbox" class="form-check-input" id="active" name="is_active" value="1" <?= (int)$user['is_active'] ? 'checked' : '' ?>><label class="form-check-label" for="active">Active</label></div>
    <button class="btn btn-primary">Save</button>
    <a href="<?= APP_URL ?>/users" class="btn btn-secondary ms-2">Cancel</a>
  </form>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
