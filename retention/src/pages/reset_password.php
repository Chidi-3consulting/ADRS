<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
$pdo = get_db();
$email = trim($_GET['email'] ?? $_POST['email'] ?? '');
$token = trim($_GET['token'] ?? $_POST['token'] ?? '');
$error = null; $ok = false;

$validToken = $email !== '' && $token !== '' && validate_reset_token($pdo, $email, $token);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    if (!$validToken) {
        $error = 'This reset link is invalid or has expired.';
    } else {
        $p1 = $_POST['password'] ?? '';
        $p2 = $_POST['password_confirm'] ?? '';
        if (($pwErr = password_policy_error($p1)) !== null) { $error = $pwErr; }
        elseif ($p1 !== $p2) { $error = 'Passwords do not match.'; }
        else {
            $pdo->prepare("UPDATE users SET password_hash=:p WHERE email=:e")
                ->execute(['p' => password_hash($p1, PASSWORD_BCRYPT), 'e' => $email]);
            consume_reset_token($pdo, $email);
            log_audit($pdo, 'password_reset_completed', 'user', null, null, ['email' => $email], get_client_ip());
            $ok = true;
        }
    }
}
?>
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Set new password — <?= escape_html(APP_NAME) ?></title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="<?= APP_URL ?>/src/assets/css/app.css" rel="stylesheet"></head>
<body class="d-flex align-items-center" style="min-height:100vh;">
<div class="container" style="max-width:420px;">
  <div class="card shadow-sm"><div class="card-header card-header-orange text-center"><h1 class="h5 mb-0">Set a new password</h1></div>
  <div class="card-body">
    <?php if ($ok): ?>
      <div class="alert alert-success">Your password has been reset.</div>
      <a class="btn btn-primary w-100" href="<?= APP_URL ?>/login">Go to login</a>
    <?php elseif (!$validToken): ?>
      <div class="alert alert-danger">This reset link is invalid or has expired.</div>
      <a href="<?= APP_URL ?>/forgot_password">Request a new link</a>
    <?php else: ?>
      <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
      <form method="post"><?= csrf_field() ?>
        <input type="hidden" name="email" value="<?= escape_html($email) ?>">
        <input type="hidden" name="token" value="<?= escape_html($token) ?>">
        <div class="mb-3"><label class="form-label">New password</label><input type="password" name="password" class="form-control" required minlength="10"><div class="form-text">At least 10 characters, including letters and numbers.</div></div>
        <div class="mb-3"><label class="form-label">Confirm password</label><input type="password" name="password_confirm" class="form-control" required></div>
        <button class="btn btn-primary w-100">Set password</button>
      </form>
    <?php endif; ?>
  </div></div>
</div></body></html>
