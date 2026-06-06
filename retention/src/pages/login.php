<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
if (is_logged_in()) { redirect(APP_URL . '/dashboard'); }

$error = null;
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
            redirect(APP_URL . '/dashboard');
        }
    }
}
?>
<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login — <?= escape_html(APP_NAME) ?></title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%23C85C1A'/><text x='16' y='23' font-size='18' font-weight='bold' text-anchor='middle' fill='white' font-family='Arial,sans-serif'>A</text></svg>">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="<?= APP_URL ?>/src/assets/css/app.css" rel="stylesheet">
</head><body class="d-flex align-items-center" style="min-height:100vh;">
<div class="container" style="max-width:420px;">
  <div class="card shadow-sm">
    <div class="card-header card-header-orange text-center"><h1 class="h4 mb-0">ADRS</h1></div>
    <div class="card-body">
      <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
      <form method="post" novalidate>
        <?= csrf_field() ?>
        <div class="mb-3"><label class="form-label">Email</label>
          <input type="email" name="email" class="form-control" required autofocus value="<?= escape_html($_POST['email'] ?? '') ?>"></div>
        <div class="mb-3"><label class="form-label">Password</label>
          <input type="password" name="password" class="form-control" required></div>
        <button class="btn btn-primary w-100">Sign in</button>
      </form>
    </div>
  </div>
  <p class="text-center text-muted small mt-3">3Consulting Limited</p>
</div></body></html>
