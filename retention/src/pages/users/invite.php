<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/invitations_lib.php';
require_role('admin');
$pdo = get_db();
$org = fetch_current_organization($pdo);
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $name = trim($_POST['name'] ?? '');
    $email = trim($_POST['email'] ?? '');
    $role = $_POST['role'] ?? 'data_owner';
    try {
        $result = create_org_invitation($pdo, $name, $email, $role, (int) current_user()['id']);
        $orgName = $org['name'] ?? 'your organisation';
        $sent = send_invitation_email($pdo, strtolower($email), $name, $role, $orgName, $result['token']);
        log_audit($pdo, 'user_invited', 'user', null, (int) current_user()['id'], [
            'email' => strtolower($email), 'role' => $role, 'email_sent' => $sent,
        ], get_client_ip());
        if ($sent) {
            flash('success', 'Invitation sent to ' . $email . '. They have 7 days to accept.');
        } elseif (is_local_environment()) {
            flash('success', 'Invitation created. Share this link: ' . invite_accept_url($result['token']));
        } else {
            flash('warning', 'Invitation saved but email could not be sent. Configure SMTP in Settings, or share this link manually: '
                . invite_accept_url($result['token']));
        }
        redirect(APP_URL . '/users');
    } catch (InvalidArgumentException $e) {
        $error = $e->getMessage();
    }
}

$page_title = 'Invite team member';
$active_nav = 'users';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="card shadow-sm" style="max-width:560px">
  <div class="card-body">
    <h1 class="h4 mb-2">Invite a team member</h1>
    <p class="text-muted small mb-3">
      Send a secure link so your DPO or data owners can join <?= escape_html($org['name'] ?? 'your organisation') ?>.
      They will set their own password when they accept.
    </p>
    <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
    <form method="post">
      <?= csrf_field() ?>
      <div class="mb-3">
        <label class="form-label">Full name *</label>
        <input name="name" class="form-control" required value="<?= escape_html($_POST['name'] ?? '') ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Work email *</label>
        <input type="email" name="email" class="form-control" required value="<?= escape_html($_POST['email'] ?? '') ?>">
        <?php if ($org && !empty($org['primary_domain']) && !str_ends_with($org['primary_domain'], '.local')): ?>
          <div class="form-text">Must be <strong>@<?= escape_html($org['primary_domain']) ?></strong></div>
        <?php endif; ?>
      </div>
      <div class="mb-3">
        <label class="form-label">Role *</label>
        <select name="role" class="form-select">
          <option value="data_owner" <?= ($_POST['role'] ?? '') === 'data_owner' ? 'selected' : '' ?>>Data Owner</option>
          <option value="dpo" <?= ($_POST['role'] ?? '') === 'dpo' ? 'selected' : '' ?>>Data Protection Officer</option>
          <option value="admin" <?= ($_POST['role'] ?? '') === 'admin' ? 'selected' : '' ?>>Administrator</option>
        </select>
      </div>
      <button class="btn btn-primary">Send invitation</button>
      <a href="<?= APP_URL ?>/users" class="btn btn-outline-secondary ms-2">Cancel</a>
    </form>
    <hr class="my-4">
    <p class="small text-muted mb-0">
      Prefer to set a temporary password yourself?
      <a href="<?= APP_URL ?>/users/create">Create user manually</a>
    </p>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
