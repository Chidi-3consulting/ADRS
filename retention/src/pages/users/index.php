<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_role('admin');
$pdo = get_db();
$orgId = require_org_id();
$stmt = $pdo->prepare("SELECT id, name, email, role, is_active, last_login_at FROM users WHERE organization_id = :o AND deleted_at IS NULL ORDER BY name");
$stmt->execute(['o' => $orgId]);
$users = $stmt->fetchAll();
$page_title = 'Users';
$active_nav = 'users';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Users</h1>
  <a href="<?= APP_URL ?>/users/create" class="btn btn-primary"><i class="bi bi-plus-lg"></i> New user</a>
</div>
<div class="card shadow-sm"><div class="card-body">
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Last login</th><th></th></tr></thead>
    <tbody>
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
