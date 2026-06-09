<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/public_layout.php';

$pdo = get_db();
if (is_logged_in()) { redirect(APP_URL . '/dashboard'); }
require_setup_complete();
if (!public_signup_enabled($pdo)) {
    http_response_code(403);
    exit('Public registration is not enabled on this portal. Contact your administrator for access.');
}

$error = null;
$done = false;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $name = trim($_POST['name'] ?? '');
    $email = trim($_POST['email'] ?? '');
    $password = $_POST['password'] ?? '';
    $password2 = $_POST['password_confirm'] ?? '';

    if ($name === '' || $email === '') {
        $error = 'Name and email are required.';
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $error = 'A valid email address is required.';
    } elseif (($pwErr = password_policy_error($password)) !== null) {
        $error = $pwErr;
    } elseif ($password !== $password2) {
        $error = 'Passwords do not match.';
    } else {
        $exists = $pdo->prepare("SELECT 1 FROM users WHERE email = :e LIMIT 1");
        $exists->execute(['e' => $email]);
        if ($exists->fetch()) {
            $error = 'An account with that email already exists. Try signing in or resetting your password.';
        } else {
            $pdo->prepare(
                "INSERT INTO users (name, email, password_hash, role, is_active, must_change_password)
                 VALUES (:n, :e, :p, 'data_owner', 1, 0)"
            )->execute([
                'n' => $name,
                'e' => $email,
                'p' => password_hash($password, PASSWORD_BCRYPT),
            ]);
            $id = (int) $pdo->lastInsertId();
            log_audit($pdo, 'user_self_registered', 'user', $id, null, ['email' => $email], get_client_ip());
            $done = true;
        }
    }
}

public_page_head('Create account', $pdo);
public_page_nav($pdo);
?>
<main class="flex-grow-1 d-flex align-items-center py-5">
  <div class="container" style="max-width:420px;">
    <div class="card shadow-sm">
      <div class="card-header card-header-orange text-center"><h1 class="h5 mb-0">Create your account</h1></div>
      <div class="card-body">
        <?php if ($done): ?>
          <div class="alert alert-success">Your account has been created. You can sign in now.</div>
          <a class="btn btn-primary w-100" href="<?= APP_URL ?>/login">Sign in</a>
        <?php else: ?>
          <p class="text-muted small">You will be registered as a <strong>Data Owner</strong>. An administrator can change your role later if needed.</p>
          <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
          <form method="post" novalidate>
            <?= csrf_field() ?>
            <div class="mb-3"><label class="form-label">Full name *</label>
              <input name="name" class="form-control" required value="<?= escape_html($_POST['name'] ?? '') ?>"></div>
            <div class="mb-3"><label class="form-label">Work email *</label>
              <input type="email" name="email" class="form-control" required value="<?= escape_html($_POST['email'] ?? '') ?>"></div>
            <div class="mb-3"><label class="form-label">Password *</label>
              <input type="password" name="password" class="form-control" required minlength="10">
              <div class="form-text">At least 10 characters, including letters and numbers.</div></div>
            <div class="mb-3"><label class="form-label">Confirm password *</label>
              <input type="password" name="password_confirm" class="form-control" required></div>
            <button class="btn btn-primary w-100">Create account</button>
          </form>
          <p class="mt-3 mb-0 small text-center"><a href="<?= APP_URL ?>/login">Already have an account? Sign in</a></p>
        <?php endif; ?>
      </div>
    </div>
  </div>
</main>
<?php public_page_foot(); ?>
