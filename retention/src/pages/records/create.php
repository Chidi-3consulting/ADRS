<?php
$pdo = get_pdo();
$error = null;
$success = null;

$categories = $pdo->query('SELECT id, name, retention_period_days, disposal_trigger FROM data_categories WHERE deleted_at IS NULL ORDER BY name')->fetchAll();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validate_csrf($_POST['csrf_token'] ?? '')) {
        $error = 'Invalid CSRF token.';
    } else {
        $categoryId = (int)($_POST['category_id'] ?? 0);
        $reference = trim($_POST['record_reference'] ?? '');
        $subjectType = trim($_POST['data_subject_type'] ?? '');
        $collectionDate = trim($_POST['collection_date'] ?? '');

        if ($categoryId <= 0 || $reference === '' || $collectionDate === '') {
            $error = 'Category, reference and collection date are required.';
        } else {
            $category = null;
            foreach ($categories as $item) {
                if ((int)$item['id'] === $categoryId) {
                    $category = $item;
                    break;
                }
            }

            if ($category === null) {
                $error = 'Selected category was not found.';
            } else {
                $retentionEndDate = null;
                if ((int)$category['retention_period_days'] > 0) {
                    $retentionEndDate = date('Y-m-d', strtotime($collectionDate . ' + ' . (int)$category['retention_period_days'] . ' days'));
                }

                $stmt = $pdo->prepare('INSERT INTO data_records (category_id, original_category_id, record_reference, data_subject_type, collection_date, retention_end_date, status, created_by) VALUES (:category_id, :original_category_id, :reference, :subject_type, :collection_date, :retention_end_date, :status, :created_by)');
                $status = 'active';
                if ($category['disposal_trigger'] === 'consent_withdrawal') {
                    $status = 'active';
                }

                $stmt->execute([
                    'category_id' => $categoryId,
                    'original_category_id' => $categoryId,
                    'reference' => $reference,
                    'subject_type' => $subjectType ?: null,
                    'collection_date' => $collectionDate,
                    'retention_end_date' => $retentionEndDate,
                    'status' => $status,
                    'created_by' => current_user()['id'] ?? null,
                ]);

                flash_set('success', 'Record created successfully.');
                redirect('/retention/records');
            }
        }
    }
}
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="card shadow-sm">
  <div class="card-body">
    <h1 class="h4 mb-3">Create Data Record</h1>
    <?php if ($error): ?>
      <div class="alert alert-danger"><?= escape_html($error) ?></div>
    <?php endif; ?>
    <form method="post">
      <input type="hidden" name="csrf_token" value="<?= escape_html(csrf_token()) ?>">
      <div class="mb-3">
        <label class="form-label">Category</label>
        <select name="category_id" class="form-select" required>
          <option value="">Select category</option>
          <?php foreach ($categories as $category): ?>
          <option value="<?= escape_html($category['id']) ?>" <?= ((int)($_POST['category_id'] ?? 0) === (int)$category['id']) ? 'selected' : '' ?>><?= escape_html($category['name']) ?></option>
          <?php endforeach; ?>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">Record reference</label>
        <input type="text" name="record_reference" class="form-control" required value="<?= escape_html($_POST['record_reference'] ?? '') ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Data subject type</label>
        <input type="text" name="data_subject_type" class="form-control" value="<?= escape_html($_POST['data_subject_type'] ?? '') ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Collection date</label>
        <input type="date" name="collection_date" class="form-control" required value="<?= escape_html($_POST['collection_date'] ?? date('Y-m-d')) ?>">
      </div>
      <button class="btn btn-primary">Create record</button>
      <a href="/retention/records" class="btn btn-secondary ms-2">Cancel</a>
    </form>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
