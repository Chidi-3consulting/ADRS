<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/twofa_lib.php';
_auth_session();

$pendingId = (int) ($_SESSION['2fa_pending_user'] ?? 0);
if ($pendingId <= 0) { redirect(APP_URL . '/login'); }
$pdo = get_db();
$stmt = $pdo->prepare("SELECT * FROM users WHERE id = :id AND is_active = 1 AND deleted_at IS NULL LIMIT 1");
$stmt->execute(['id' => $pendingId]);
$user = $stmt->fetch();
if (!$user) { unset($_SESSION['2fa_pending_user']); redirect(APP_URL . '/login'); }
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $code = trim($_POST['code'] ?? '');
    $ok = false;
    if (totp_verify((string) $user['twofa_secret'], $code)) {
        $ok = true;
    } else {
        // Try a one-time recovery code.
        $remaining = consume_recovery_code(json_decode($user['twofa_recovery'] ?? '[]', true) ?: [], $code);
        if ($remaining !== null) {
            $pdo->prepare("UPDATE users SET twofa_recovery = :r WHERE id = :id")->execute(['r' => json_encode($remaining), 'id' => $pendingId]);
            log_audit($pdo, 'user_login', 'user', $pendingId, $pendingId, ['twofa' => 'recovery_code_used'], get_client_ip());
            $ok = true;
        }
    }
    if ($ok) {
        unset($_SESSION['2fa_pending_user']);
        establish_session($pdo, $user);
        redirect(APP_URL . '/dashboard');
    }
    $error = 'Invalid authentication code.';
}
?>
<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Two-factor authentication — <?= escape_html(APP_NAME) ?></title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="<?= APP_URL ?>/src/assets/css/app.css" rel="stylesheet">
</head><body class="d-flex align-items-center" style="min-height:100vh;">
<div class="container" style="max-width:420px;">
  <div class="card shadow-sm">
    <div class="card-header card-header-orange text-center"><h1 class="h5 mb-0">Two-factor authentication</h1></div>
    <div class="card-body">
      <p class="text-muted small">Enter the 6-digit code from your authenticator app, or a recovery code.</p>
      <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
      <form method="post">
        <?= csrf_field() ?>
        <div class="mb-3"><input name="code" class="form-control form-control-lg text-center" autofocus autocomplete="one-time-code" placeholder="123456"></div>
        <button class="btn btn-primary w-100">Verify</button>
      </form>
      <a class="d-block text-center mt-3 small" href="<?= APP_URL ?>/logout">Cancel</a>
    </div>
  </div>
</div></body></html>
