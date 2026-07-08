<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/invitations_lib.php';
require_once __DIR__ . '/../includes/public_layout.php';

$pdo = get_db();
if (is_logged_in()) { redirect(APP_URL . '/dashboard'); }

$token = trim($_GET['token'] ?? $_POST['token'] ?? '');
$invite = $token !== '' ? find_invitation_by_token($pdo, $token) : null;
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    try {
        $password = $_POST['password'] ?? '';
        $password2 = $_POST['password_confirm'] ?? '';
        if ($password !== $password2) {
            throw new InvalidArgumentException('Passwords do not match.');
        }
        $user = accept_org_invitation($pdo, $token, $password, trim($_POST['name'] ?? ''));
        establish_session($pdo, $user);
        log_audit($pdo, 'invitation_accepted', 'user', (int) $user['id'], (int) $user['id'], [
            'email' => $user['email'], 'role' => $user['role'],
        ], get_client_ip());
        flash('success', 'Welcome to ADRS! Your account is ready.');
        redirect(APP_URL . '/dashboard');
    } catch (InvalidArgumentException $e) {
        $error = $e->getMessage();
        $invite = find_invitation_by_token($pdo, $token);
    }
}

public_page_head('Accept invitation', $pdo);
public_page_nav($pdo);
?>
<main class="flex-grow-1 py-5">
  <div class="container" style="max-width:480px;">
    <div class="card shadow-sm">
      <div class="card-header card-header-orange text-center">
        <h1 class="h4 mb-0">Join your organisation on ADRS</h1>
      </div>
      <div class="card-body">
        <?php if ($invite === null): ?>
          <div class="alert alert-danger mb-0">This invitation link is invalid or has expired. Ask your administrator to send a new invitation.</div>
          <p class="mt-3 mb-0 small text-center"><a href="<?= APP_URL ?>/login">Sign in</a> if you already have an account.</p>
        <?php else: ?>
          <p class="text-muted small">
            You have been invited to <strong><?= escape_html($invite['org_name']) ?></strong>
            as <?= get_role_badge($invite['role']) ?>.
          </p>
          <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
          <form method="post" novalidate>
            <?= csrf_field() ?>
            <input type="hidden" name="token" value="<?= escape_html($token) ?>">
            <div class="mb-3">
              <label class="form-label">Email</label>
              <input class="form-control" value="<?= escape_html($invite['email']) ?>" disabled>
            </div>
            <div class="mb-3">
              <label class="form-label">Your full name *</label>
              <input name="name" class="form-control" required value="<?= escape_html($_POST['name'] ?? $invite['name']) ?>">
            </div>
            <div class="mb-3">
              <label class="form-label">Choose a password *</label>
              <input type="password" name="password" class="form-control" required minlength="10" autocomplete="new-password">
              <div class="form-text">At least 10 characters, including letters and numbers.</div>
            </div>
            <div class="mb-3">
              <label class="form-label">Confirm password *</label>
              <input type="password" name="password_confirm" class="form-control" required minlength="10" autocomplete="new-password">
            </div>
            <button class="btn btn-primary w-100 btn-lg">Accept &amp; join</button>
          </form>
        <?php endif; ?>
      </div>
    </div>
  </div>
</main>
<?php public_page_foot(); ?>
