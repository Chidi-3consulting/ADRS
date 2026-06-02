<?php
$pdo = get_pdo();
$stmt = $pdo->query('SELECT * FROM data_categories WHERE deleted_at IS NULL ORDER BY name');
$categories = $stmt->fetchAll();
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4">Data Categories</h1>
  <a href="/retention/categories/create" class="btn btn-primary">New category</a>
</div>
<div class="card shadow-sm">
  <div class="card-body">
    <?php if (empty($categories)): ?>
      <p class="text-muted">No categories have been created yet.</p>
    <?php else: ?>
      <div class="table-responsive">
        <table class="table table-striped table-hover">
          <thead>
            <tr>
              <th>Name</th>
              <th>Framework</th>
              <th>Retention</th>
              <th>Method</th>
              <th>Trigger</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($categories as $category): ?>
            <tr>
              <td><?= escape_html($category['name']) ?></td>
              <td><?= escape_html($category['compliance_framework']) ?></td>
              <td><?= escape_html($category['retention_period_label']) ?></td>
              <td><?= escape_html($category['disposal_method']) ?></td>
              <td><?= escape_html($category['disposal_trigger']) ?></td>
              <td><a href="/retention/categories/edit?id=<?= escape_html($category['id']) ?>" class="btn btn-sm btn-outline-primary">Edit</a></td>
            </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
