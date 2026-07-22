<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/public_layout.php';
if (is_logged_in()) { redirect(APP_URL . '/dashboard'); }
if (!setup_is_complete(get_db())) { redirect(APP_URL . '/setup'); }
$pdo = get_db();

$error = null;
if (isset($_GET['expired'])) { $error = 'Your session has expired (inactivity or time limit). Please sign in again.'; }
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $pdo = get_db();
    $email = trim($_POST['email'] ?? '');
    $password = $_POST['password'] ?? '';
    $ip = get_client_ip();
    $wait = ($email !== '') ? login_throttle_seconds($pdo, $email, $ip) : 0;
    if ($email === '' || $password === '') {
        $error = 'Please enter both email and password.';
    } elseif ($wait > 0) {
        $error = 'Too many failed attempts. Please try again in ' . (int) ceil($wait / 60) . ' minute(s).';
    } else {
        $user = verify_credentials($pdo, $email, $password);
        if (!$user) {
            record_login_attempt($pdo, $email, $ip, false);
            $error = 'Invalid email or password.';
        } elseif ((int) ($user['twofa_enabled'] ?? 0) === 1) {
            record_login_attempt($pdo, $email, $ip, true);
            // Credentials OK but 2FA required — hold a pending state, do NOT log in yet.
            _auth_session();
            $_SESSION['2fa_pending_user'] = (int) $user['id'];
            redirect(APP_URL . '/login/2fa');
        } else {
            record_login_attempt($pdo, $email, $ip, true);
            establish_session($pdo, $user);
            if ((int) ($user['must_change_password'] ?? 0) === 1) {
                redirect(APP_URL . '/profile?required=1');
            }
            redirect(APP_URL . '/dashboard');
        }
    }
}
$page_title = 'Sign In';
public_page_head('Sign In', $pdo);
public_page_nav($pdo);
?>
<main class="flex-grow-1 d-flex align-items-center py-5">
<div class="container" style="max-width:420px;">
  <div class="card shadow-sm border-0">
    <div class="card-header card-header-orange text-center py-3 rounded-top" style="border-bottom:0px;">
      <h1 class="h5 mb-0 text-white fw-bold">Sign In to ADRS</h1>
    </div>
    <div class="card-body p-4">
      <?php if ($error): ?><div class="alert alert-danger mb-4 small"><?= escape_html($error) ?></div><?php endif; ?>
      <form method="post" novalidate>
        <?= csrf_field() ?>
        <div class="mb-3">
          <label class="form-label fw-semibold small text-secondary">Work Email</label>
          <input type="email" name="email" class="form-control" required autofocus value="<?= escape_html($_POST['email'] ?? '') ?>" placeholder="name@company.com">
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold small text-secondary">Password</label>
          <input type="password" name="password" class="form-control" required placeholder="••••••••">
        </div>
        <button class="btn btn-primary w-100 hover-lift mt-2">Sign in</button>
      </form>
      <p class="mt-4 mb-0 small text-center text-muted">
        <a href="<?= APP_URL ?>/forgot_password" class="text-decoration-none">Forgot password?</a>
        <?php if (is_saas_deployment($pdo)): ?>
          · <a href="<?= APP_URL ?>/register" class="text-decoration-none fw-semibold">Start free trial</a>
        <?php elseif (public_signup_enabled($pdo)): ?>
          · <a href="<?= APP_URL ?>/signup" class="text-decoration-none fw-semibold">Create account</a>
        <?php endif; ?>
      </p>
    </div>
  </div>
  <p class="text-center text-muted small mt-3">
    <a href="<?= APP_URL ?>/" class="text-muted text-decoration-none">&larr; Back to home</a>
  </p>
</div>
</main>
<?php public_page_foot(); ?>
