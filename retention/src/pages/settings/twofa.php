<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/twofa_lib.php';
require_login();
$pdo = get_db();
$me = current_user();
$row = $pdo->prepare("SELECT * FROM users WHERE id = :id"); $row->execute(['id' => $me['id']]); $u = $row->fetch();
$enabled = (int) ($u['twofa_enabled'] ?? 0) === 1;
$error = null; $newRecovery = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $action = $_POST['action'] ?? '';
    if ($action === 'enable' && !$enabled) {
        $secret = $_SESSION['2fa_setup_secret'] ?? '';
        if ($secret === '' || !totp_verify($secret, trim($_POST['code'] ?? ''))) {
            $error = 'That code did not match. Try again.';
        } else {
            $rc = generate_recovery_codes(8);
            enable_user_2fa($pdo, (int) $me['id'], $secret, $rc['hashed']);
            log_audit($pdo, 'user_updated', 'user', (int) $me['id'], (int) $me['id'], ['twofa' => 'enabled'], get_client_ip());
            unset($_SESSION['2fa_setup_secret']);
            $enabled = true; $newRecovery = $rc['plain'];
        }
    } elseif ($action === 'disable' && $enabled) {
        if (!password_verify($_POST['password'] ?? '', $u['password_hash'])) {
            $error = 'Incorrect password.';
        } else {
            disable_user_2fa($pdo, (int) $me['id']);
            log_audit($pdo, 'user_updated', 'user', (int) $me['id'], (int) $me['id'], ['twofa' => 'disabled'], get_client_ip());
            $enabled = false;
        }
    }
}

// For the enable form, ensure a setup secret exists in session.
if (!$enabled && empty($_SESSION['2fa_setup_secret'])) { $_SESSION['2fa_setup_secret'] = totp_generate_secret(); }
$setupSecret = $_SESSION['2fa_setup_secret'] ?? '';
$uri = $setupSecret ? totp_uri($setupSecret, $me['email'] ?? ('user' . $me['id']), 'ADRS') : '';

$page_title = 'Two-Factor Authentication';
$active_nav = 'settings';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:640px"><div class="card-body">
  <h1 class="h4 mb-3">Two-Factor Authentication (2FA)</h1>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>

  <?php if ($newRecovery): ?>
    <div class="alert alert-success">
      <strong>2FA enabled.</strong> Save these one-time recovery codes somewhere safe — they are shown only once:
      <pre class="mt-2 mb-0"><?php foreach ($newRecovery as $c) { echo escape_html($c) . "\n"; } ?></pre>
    </div>
    <a href="<?= APP_URL ?>/settings" class="btn btn-primary">Done</a>

  <?php elseif ($enabled): ?>
    <p>✅ Two-factor authentication is <strong>enabled</strong> on your account.</p>
    <form method="post" onsubmit="return confirm('Disable 2FA? Your account will be protected by password only.')">
      <?= csrf_field() ?><input type="hidden" name="action" value="disable">
      <div class="mb-3" style="max-width:320px"><label class="form-label">Confirm your password to disable</label><input type="password" name="password" class="form-control" required></div>
      <button class="btn btn-outline-danger">Disable 2FA</button>
    </form>

  <?php else: ?>
    <p class="text-muted">Scan this QR code with Google Authenticator / Authy / Microsoft Authenticator, then enter the 6-digit code to confirm.</p>
    <div class="text-center mb-3"><canvas id="qr"></canvas></div>
    <p class="small">Can't scan? Enter this key manually: <code><?= escape_html($setupSecret) ?></code></p>
    <form method="post">
      <?= csrf_field() ?><input type="hidden" name="action" value="enable">
      <div class="mb-3" style="max-width:240px"><label class="form-label">Authentication code</label><input name="code" class="form-control" placeholder="123456" autocomplete="one-time-code" required></div>
      <button class="btn btn-primary">Enable 2FA</button>
    </form>
    <script src="https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js"></script>
    <script>QRCode && QRCode.toCanvas(document.getElementById('qr'), <?= json_encode($uri) ?>, {width:200});</script>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
