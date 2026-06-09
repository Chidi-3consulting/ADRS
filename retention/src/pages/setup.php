<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/public_layout.php';

$pdo = get_db();
if (setup_is_complete($pdo)) {
    redirect(is_logged_in() ? APP_URL . '/dashboard' : APP_URL . '/login');
}

$error = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $orgName = trim($_POST['org_name'] ?? '');
    $name = trim($_POST['name'] ?? '');
    $email = trim($_POST['email'] ?? '');
    $password = $_POST['password'] ?? '';
    $password2 = $_POST['password_confirm'] ?? '';
    $importCategories = !empty($_POST['import_categories']);

    if ($orgName === '' || $name === '' || $email === '') {
        $error = 'Organisation name, your name, and email are required.';
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $error = 'A valid email address is required.';
    } elseif (($pwErr = password_policy_error($password)) !== null) {
        $error = $pwErr;
    } elseif ($password !== $password2) {
        $error = 'Passwords do not match.';
    } else {
        $exists = $pdo->prepare("SELECT 1 FROM users WHERE email = :e LIMIT 1");
        $exists->execute(['e' => $email]);
        if ($exists->fetch()) {
            $error = 'A user with that email already exists.';
        } else {
            $pdo->prepare(
                "INSERT INTO users (name, email, password_hash, role, is_active, must_change_password)
                 VALUES (:n, :e, :p, 'admin', 1, 0)"
            )->execute([
                'n' => $name,
                'e' => $email,
                'p' => password_hash($password, PASSWORD_BCRYPT),
            ]);
            $adminId = (int) $pdo->lastInsertId();
            set_setting($pdo, 'white_label_name', $orgName);
            set_setting($pdo, 'app_name', $orgName);
            set_setting($pdo, 'setup_complete', '1');
            if ($importCategories) { import_category_seed($pdo); }
            $stmt = $pdo->prepare("SELECT * FROM users WHERE id = :id LIMIT 1");
            $stmt->execute(['id' => $adminId]);
            $user = $stmt->fetch();
            establish_session($pdo, $user);
            log_audit($pdo, 'setup_completed', 'system', null, $adminId, ['org' => $orgName], get_client_ip());
            flash('success', 'Welcome! Your ADRS portal is ready. Configure SMTP in Settings when you are ready to send emails.');
            redirect(APP_URL . '/dashboard');
        }
    }
}

public_page_head('Initial setup', $pdo);
?>
<main class="flex-grow-1 d-flex align-items-center py-5" style="background:var(--3c-light);">
<div class="container" style="max-width:560px;">
  <div class="card shadow-sm">
    <div class="card-header card-header-orange text-center">
      <h1 class="h4 mb-0">Set up your ADRS portal</h1>
    </div>
    <div class="card-body">
      <p class="text-muted small">Create the first administrator account for this organisation. This step runs once per deployment.</p>
      <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
      <form method="post" novalidate>
        <?= csrf_field() ?>
        <div class="mb-3">
          <label class="form-label">Organisation name *</label>
          <input name="org_name" class="form-control" required autofocus
                 value="<?= escape_html($_POST['org_name'] ?? '') ?>"
                 placeholder="e.g. Acme Bank Ltd">
          <div class="form-text">Shown in the portal header and emails.</div>
        </div>
        <div class="mb-3">
          <label class="form-label">Your name *</label>
          <input name="name" class="form-control" required value="<?= escape_html($_POST['name'] ?? '') ?>">
        </div>
        <div class="mb-3">
          <label class="form-label">Administrator email *</label>
          <input type="email" name="email" class="form-control" required value="<?= escape_html($_POST['email'] ?? '') ?>">
        </div>
        <div class="mb-3">
          <label class="form-label">Password *</label>
          <input type="password" name="password" class="form-control" required minlength="10">
          <div class="form-text">At least 10 characters, including letters and numbers.</div>
        </div>
        <div class="mb-3">
          <label class="form-label">Confirm password *</label>
          <input type="password" name="password_confirm" class="form-control" required minlength="10">
        </div>
        <div class="form-check mb-3">
          <input class="form-check-input" type="checkbox" name="import_categories" id="import_categories" value="1" checked>
          <label class="form-check-label" for="import_categories">Import the 30-category GDPR/NDPR library</label>
        </div>
        <button class="btn btn-primary w-100">Complete setup</button>
      </form>
    </div>
  </div>
</div>
</main>
<?php public_page_foot(); ?>
