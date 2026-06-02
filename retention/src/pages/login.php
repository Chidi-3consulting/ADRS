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
    if ($email === '' || $password === '') {
        $error = 'Please enter both email and password.';
    } elseif (login_user($pdo, $email, $password)) {
        redirect(APP_URL . '/dashboard');
    } else {
        $error = 'Invalid email or password.';
    }
}
?>
<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login — <?= escape_html(APP_NAME) ?></title>
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
