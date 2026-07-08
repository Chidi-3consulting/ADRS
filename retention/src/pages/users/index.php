<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/invitations_lib.php';
require_role('admin');
$pdo = get_db();
$orgId = require_org_id();

if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['action'] ?? '') === 'revoke_invite') {
    csrf_verify();
    $invId = (int) ($_POST['invitation_id'] ?? 0);
    if ($invId > 0 && revoke_org_invitation($pdo, $invId, $orgId)) {
        flash('success', 'Invitation cancelled.');
    }
    redirect(APP_URL . '/users');
}

$stmt = $pdo->prepare("SELECT id, name, email, role, is_active, last_login_at FROM users WHERE organization_id = :o AND deleted_at IS NULL ORDER BY name");
$stmt->execute(['o' => $orgId]);
$users = $stmt->fetchAll();
$pending = list_pending_invitations($pdo, $orgId);
$page_title = 'Users';
$active_nav = 'users';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
  <h1 class="h4 mb-0">Users</h1>
  <div class="d-flex gap-2">
    <a href="<?= APP_URL ?>/users/invite" class="btn btn-primary"><i class="bi bi-envelope-plus"></i> Invite user</a>
    <a href="<?= APP_URL ?>/users/create" class="btn btn-outline-secondary btn-sm align-self-center">Manual create</a>
  </div>
</div>

<?php if (!empty($pending)): ?>
<div class="card shadow-sm mb-3 border-info">
  <div class="card-header bg-white fw-semibold">Pending invitations</div>
  <div class="card-body p-0">
    <div class="table-responsive">
      <table class="table table-sm mb-0 align-middle">
        <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Sent</th><th>Expires</th><th></th></tr></thead>
        <tbody>
        <?php foreach ($pending as $inv): ?>
          <tr>
            <td><?= escape_html($inv['name']) ?></td>
            <td><?= escape_html($inv['email']) ?></td>
            <td><?= get_role_badge($inv['role']) ?></td>
            <td class="small text-muted"><?= escape_html(format_datetime($inv['created_at'])) ?></td>
            <td class="small text-muted"><?= escape_html(format_datetime($inv['expires_at'])) ?></td>
            <td>
              <form method="post" class="d-inline" data-confirm="Cancel this invitation?">
                <?= csrf_field() ?>
                <input type="hidden" name="action" value="revoke_invite">
                <input type="hidden" name="invitation_id" value="<?= (int) $inv['id'] ?>">
                <button class="btn btn-sm btn-outline-danger">Cancel</button>
              </form>
            </td>
          </tr>
        <?php endforeach; ?>
        </tbody>
      </table>
    </div>
  </div>
</div>
<?php endif; ?>

<div class="card shadow-sm"><div class="card-body">
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Last login</th><th></th></tr></thead>
    <tbody>
    <?php if (empty($users)): ?>
      <tr><td colspan="6" class="text-muted text-center py-4">No users yet. <a href="<?= APP_URL ?>/users/invite">Invite your first team member</a>.</td></tr>
    <?php endif; ?>
    <?php foreach ($users as $u): ?>
      <tr>
        <td><?= escape_html($u['name']) ?></td>
        <td><?= escape_html($u['email']) ?></td>
        <td><?= get_role_badge($u['role']) ?></td>
        <td><?= (int)$u['is_active'] ? '<span class="badge bg-success">Active</span>' : '<span class="badge bg-secondary">Disabled</span>' ?></td>
        <td><?= escape_html(format_datetime($u['last_login_at'])) ?></td>
        <td><a href="<?= APP_URL ?>/users/edit?id=<?= (int)$u['id'] ?>" class="btn btn-sm btn-outline-primary">Edit</a></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
