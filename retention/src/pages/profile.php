<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_login();

$pdo = get_db();
$me = current_user();
$userId = (int) $me['id'];
$required = !empty($_GET['required']) || (int) ($me['must_change_password'] ?? 0) === 1;
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $name = trim($_POST['name'] ?? '');
    $current = $_POST['current_password'] ?? '';
    $newPass = $_POST['new_password'] ?? '';
    $newPass2 = $_POST['new_password_confirm'] ?? '';
    $changingPassword = $newPass !== '' || $newPass2 !== '' || $current !== '';

    if ($name === '') {
        $error = 'Name is required.';
    } elseif ($required || $changingPassword) {
        $row = $pdo->prepare("SELECT password_hash FROM users WHERE id = :id LIMIT 1");
        $row->execute(['id' => $userId]);
        $hash = (string) ($row->fetchColumn() ?: '');
        if (!$required && $current === '') {
            $error = 'Current password is required to set a new password.';
        } elseif (!$required && !password_verify($current, $hash)) {
            $error = 'Current password is incorrect.';
        } elseif (($pwErr = password_policy_error($newPass)) !== null) {
            $error = $pwErr;
        } elseif ($newPass !== $newPass2) {
            $error = 'New passwords do not match.';
        } else {
            $pdo->prepare("UPDATE users SET name = :n, password_hash = :p, must_change_password = 0 WHERE id = :id")
                ->execute(['n' => $name, 'p' => password_hash($newPass, PASSWORD_BCRYPT), 'id' => $userId]);
            $_SESSION['user']['name'] = $name;
            $_SESSION['user']['must_change_password'] = 0;
            log_audit($pdo, 'profile_updated', 'user', $userId, $userId, ['password_changed' => true], get_client_ip());
            flash('success', 'Your profile has been updated.');
            redirect(APP_URL . '/dashboard');
        }
    } else {
        $pdo->prepare("UPDATE users SET name = :n WHERE id = :id")->execute(['n' => $name, 'id' => $userId]);
        $_SESSION['user']['name'] = $name;
        log_audit($pdo, 'profile_updated', 'user', $userId, $userId, null, get_client_ip());
        flash('success', 'Profile saved.');
        redirect(APP_URL . '/profile');
    }
}

$page_title = 'My profile';
$active_nav = '';
require __DIR__ . '/../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:560px">
  <div class="card-body">
    <h1 class="h4 mb-3">My profile</h1>
    <?php if ($required): ?>
      <div class="alert alert-warning">You must set a new password before you can use the portal.</div>
    <?php endif; ?>
    <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
    <form method="post">
      <?= csrf_field() ?>
      <div class="mb-3">
        <label class="form-label">Email</label>
        <input class="form-control" value="<?= escape_html($me['email'] ?? '') ?>" disabled>
      </div>
      <div class="mb-3">
        <label class="form-label">Name *</label>
        <input name="name" class="form-control" required value="<?= escape_html($me['name'] ?? '') ?>" <?= $required ? '' : '' ?>>
      </div>
      <div class="mb-3">
        <label class="form-label">Role</label>
        <div><?= get_role_badge($me['role'] ?? '') ?></div>
      </div>
      <hr>
      <h2 class="h6"><?= $required ? 'Set a new password *' : 'Change password' ?></h2>
      <?php if (!$required): ?>
        <div class="mb-3">
          <label class="form-label">Current password</label>
          <input type="password" name="current_password" class="form-control" autocomplete="current-password">
        </div>
      <?php endif; ?>
      <div class="mb-3">
        <label class="form-label"><?= $required ? 'New password *' : 'New password' ?></label>
        <input type="password" name="new_password" class="form-control" <?= $required ? 'required' : '' ?> minlength="10" autocomplete="new-password">
        <div class="form-text">At least 10 characters, including letters and numbers.</div>
      </div>
      <div class="mb-3">
        <label class="form-label"><?= $required ? 'Confirm new password *' : 'Confirm new password' ?></label>
        <input type="password" name="new_password_confirm" class="form-control" <?= $required ? 'required' : '' ?> autocomplete="new-password">
      </div>
      <button class="btn btn-primary"><?= $required ? 'Save and continue' : 'Save changes' ?></button>
      <?php if (!$required): ?>
        <a href="<?= APP_URL ?>/dashboard" class="btn btn-secondary ms-2">Cancel</a>
      <?php endif; ?>
    </form>
    <?php if (!$required): ?>
      <p class="mt-3 mb-0 small"><a href="<?= APP_URL ?>/forgot_password">Forgot your password?</a></p>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../includes/layout_footer.php'; ?>
