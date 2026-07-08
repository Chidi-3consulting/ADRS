<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_role('admin');
$pdo = get_db();
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $name = trim($_POST['name'] ?? '');
    $email = trim($_POST['email'] ?? '');
    $password = $_POST['password'] ?? '';
    $role = $_POST['role'] ?? 'data_owner';
    if ($name === '' || $email === '') {
        $error = 'Name and email are required.';
    } elseif (($pwErr = password_policy_error($password)) !== null) {
        $error = $pwErr;
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $error = 'A valid email address is required.';
    } elseif (($domainErr = org_member_email_error($pdo, $email)) !== null) {
        $error = $domainErr;
    } elseif (!in_array($role, ['admin','dpo','data_owner'], true)) {
        $error = 'Invalid role.';
    } else {
        $exists = $pdo->prepare("SELECT 1 FROM users WHERE email = :e LIMIT 1");
        $exists->execute(['e' => $email]);
        if ($exists->fetch()) {
            $error = 'A user with that email already exists.';
        } else {
            $pdo->prepare(
                "INSERT INTO users (organization_id,name,email,password_hash,role,is_active,must_change_password)
                 VALUES (:oid,:n,:e,:p,:r,1,1)"
            )->execute([
                'oid' => require_org_id(),
                'n' => $name, 'e' => $email,
                'p' => password_hash($password, PASSWORD_BCRYPT), 'r' => $role,
            ]);
            $id = (int) $pdo->lastInsertId();
            log_audit($pdo, 'user_created', 'user', $id, (int) current_user()['id'], ['email' => $email, 'role' => $role], get_client_ip());
            flash('success', 'User created.');
            redirect(APP_URL . '/users');
        }
    }
}
$page_title = 'Create User';
$active_nav = 'users';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:560px"><div class="card-body">
  <h1 class="h4 mb-3">Create User</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Name *</label><input name="name" class="form-control" required value="<?= escape_html($_POST['name'] ?? '') ?>"></div>
    <div class="mb-3"><label class="form-label">Email *</label><input type="email" name="email" class="form-control" required value="<?= escape_html($_POST['email'] ?? '') ?>">
      <?php
      $curOrg = fetch_current_organization($pdo);
      if ($curOrg && !empty($curOrg['primary_domain']) && !str_ends_with($curOrg['primary_domain'], '.local')): ?>
      <div class="form-text">Must be a work email at <strong>@<?= escape_html($curOrg['primary_domain']) ?></strong>.</div>
      <?php endif; ?>
    </div>
    <div class="mb-3"><label class="form-label">Temporary password * (min 10 chars)</label><input type="password" name="password" class="form-control" required minlength="10"><div class="form-text">The user must change this password on first login.</div></div>
    <div class="mb-3"><label class="form-label">Role *</label>
      <select name="role" class="form-select">
        <option value="data_owner">Data Owner</option>
        <option value="dpo">Data Protection Officer</option>
        <option value="admin">Administrator</option>
      </select></div>
    <button class="btn btn-primary">Create user</button>
    <a href="<?= APP_URL ?>/users" class="btn btn-secondary ms-2">Cancel</a>
  </form>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
