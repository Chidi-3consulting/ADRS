<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/mailer.php';
require_once __DIR__ . '/../includes/public_layout.php';
require_login();

$pdo = get_db();
$me = current_user();
$userId = (int) $me['id'];
$verified = !empty($me['email_verified_at']);
$message = null;

if (!$verified && isset($_GET['token'])) {
    if (verify_email_token($pdo, $userId, trim($_GET['token']))) {
        flash('success', 'Your email has been verified. Welcome to ADRS.');
        redirect(APP_URL . '/dashboard');
    }
    $message = 'This verification link is invalid or has expired.';
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && !$verified) {
    csrf_verify();
    $token = issue_email_verification_token($pdo, $userId);
    $link = APP_URL . '/verify_email?token=' . urlencode($token);
    [$subject, $html] = email_verification($me['name'] ?? 'there', $link);
    send_platform_email($pdo, $me['email'], $subject, $html);
    $message = 'A new verification link has been sent to ' . $me['email'] . '.';
}

public_page_head('Verify your email', $pdo);
?>
<main class="flex-grow-1 d-flex align-items-center py-5">
  <div class="container" style="max-width:480px;">
    <div class="card shadow-sm">
      <div class="card-header card-header-orange text-center"><h1 class="h5 mb-0">Verify your email</h1></div>
      <div class="card-body">
        <?php if ($verified): ?>
          <div class="alert alert-success">Your email is verified.</div>
          <a class="btn btn-primary w-100" href="<?= APP_URL ?>/dashboard">Go to dashboard</a>
        <?php else: ?>
          <p class="text-muted small">We sent a verification link to <strong><?= escape_html($me['email']) ?></strong>. Click it to activate your account.</p>
          <?php if ($message): ?><div class="alert alert-info"><?= escape_html($message) ?></div><?php endif; ?>
          <form method="post"><?= csrf_field() ?>
            <button class="btn btn-outline-primary w-100">Resend verification email</button>
          </form>
        <?php endif; ?>
      </div>
    </div>
  </div>
</main>
<?php public_page_foot(); ?>
