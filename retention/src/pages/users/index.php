<?php
$pdo = get_pdo();
$stmt = $pdo->query('SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC');
$users = $stmt->fetchAll();
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">Users</h1>
    <p class="text-muted mb-0">Manage administrator and operator accounts for the retention system.</p>
  </div>
  <a href="/retention/users/create" class="btn btn-primary">New user</a>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if (empty($users)): ?>
      <p class="text-muted">No user accounts exist yet.</p>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-hover align-middle">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($users as $user): ?>
            <tr>
              <td><?= escape_html($user['name']) ?></td>
              <td><?= escape_html($user['email']) ?></td>
              <td><?= escape_html($user['role']) ?></td>
              <td><?= escape_html($user['created_at']) ?></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
