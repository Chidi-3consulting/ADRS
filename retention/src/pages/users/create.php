<?php
$pdo = get_pdo();
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validate_csrf($_POST['csrf_token'] ?? '')) {
        $error = 'Invalid CSRF token.';
    } else {
        $name = trim($_POST['name'] ?? '');
        $email = trim($_POST['email'] ?? '');
        $password = $_POST['password'] ?? '';
        $role = trim($_POST['role'] ?? 'admin');

        if ($name === '' || $email === '' || $password === '') {
            $error = 'Name, email and password are required.';
        } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            $error = 'A valid email address is required.';
        } else {
            $stmt = $pdo->prepare('INSERT INTO users (name, email, password_hash, role, created_by) VALUES (:name, :email, :password_hash, :role, :created_by)');
            $stmt->execute([
                'name' => $name,
                'email' => $email,
                'password_hash' => password_hash($password, PASSWORD_DEFAULT),
                'role' => $role,
                'created_by' => current_user()['id'] ?? null,
            ]);

            flash_set('success', 'User account created successfully.');
            redirect('/retention/users');
        }
    }
}
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="card shadow-sm">
  <div class="card-body">
    <h1 class="h4 mb-3">Create User</h1>
    <?php if ($error): ?>
      <div class="alert alert-danger"><?= escape_html($error) ?></div>
    <?php endif; ?>
    <form method="post">
      <input type="hidden" name="csrf_token" value="<?= escape_html(csrf_token()) ?>">
      <div class="mb-3">
        <label class="form-label">Name</label>
        <input type="text" name="name" class="form-control" required value="<?= escape_html($_POST['name'] ?? '') ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Email</label>
        <input type="email" name="email" class="form-control" required value="<?= escape_html($_POST['email'] ?? '') ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Password</label>
        <input type="password" name="password" class="form-control" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Role</label>
        <select name="role" class="form-select">
          <option value="admin" <?= ($_POST['role'] ?? '') === 'admin' ? 'selected' : '' ?>>Administrator</option>
          <option value="operator" <?= ($_POST['role'] ?? '') === 'operator' ? 'selected' : '' ?>>Operator</option>
        </select>
      </div>
      <button class="btn btn-primary">Create user</button>
      <a href="/retention/users" class="btn btn-secondary ms-2">Cancel</a>
    </form>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
