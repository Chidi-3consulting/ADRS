<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/mailer.php';
$done = false;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $pdo = get_db();
    $email = trim($_POST['email'] ?? '');
    $token = create_password_reset_token($pdo, $email);
    if ($token !== null) {
        $link = APP_URL . '/reset_password?email=' . urlencode($email) . '&token=' . $token;
        [$subject, $html] = email_password_reset('there', $link);
        send_system_email($pdo, $email, $subject, $html);
    }
    // Always show the same message — never reveal whether an account exists.
    $done = true;
}
?>
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forgot password — <?= escape_html(APP_NAME) ?></title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="<?= APP_URL ?>/src/assets/css/app.css" rel="stylesheet"></head>
<body class="d-flex align-items-center" style="min-height:100vh;">
<div class="container" style="max-width:420px;">
  <div class="card shadow-sm"><div class="card-header card-header-orange text-center"><h1 class="h5 mb-0">Reset your password</h1></div>
  <div class="card-body">
    <?php if ($done): ?>
      <div class="alert alert-info">If that email matches an account, a reset link has been sent. The link expires in 1 hour.</div>
      <a href="<?= APP_URL ?>/login">Back to login</a>
    <?php else: ?>
      <form method="post"><?= csrf_field() ?>
        <div class="mb-3"><label class="form-label">Email</label><input type="email" name="email" class="form-control" required></div>
        <button class="btn btn-primary w-100">Send reset link</button>
      </form>
      <p class="mt-3 mb-0 small"><a href="<?= APP_URL ?>/login">Back to login</a></p>
    <?php endif; ?>
  </div></div>
</div></body></html>
