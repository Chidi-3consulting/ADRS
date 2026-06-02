<?php
$pdo = get_pdo();
$id = (int)($_GET['id'] ?? 0);
$error = null;

if ($id <= 0) {
    http_response_code(404);
    echo 'Record not found.';
    exit;
}

$recordStmt = $pdo->prepare('SELECT * FROM data_records WHERE id = :id AND deleted_at IS NULL LIMIT 1');
$recordStmt->execute(['id' => $id]);
$record = $recordStmt->fetch();

if (!$record) {
    http_response_code(404);
    echo 'Record not found.';
    exit;
}

$categories = $pdo->query('SELECT id, name, retention_period_days FROM data_categories WHERE deleted_at IS NULL ORDER BY name')->fetchAll();
$statuses = ['active','due_review','disposal_requested','legal_hold','disposed'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validate_csrf($_POST['csrf_token'] ?? '')) {
        $error = 'Invalid CSRF token.';
    } else {
        $categoryId = (int)($_POST['category_id'] ?? 0);
        $reference = trim($_POST['record_reference'] ?? '');
        $subjectType = trim($_POST['data_subject_type'] ?? '');
        $collectionDate = trim($_POST['collection_date'] ?? '');
        $status = $_POST['status'] ?? 'active';
        $notes = trim($_POST['notes'] ?? '');

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
            } elseif (!in_array($status, $statuses, true)) {
                $error = 'Invalid status selected.';
            } else {
                $retentionEndDate = null;
                if ((int)$category['retention_period_days'] > 0) {
                    $retentionEndDate = date('Y-m-d', strtotime($collectionDate . ' + ' . (int)$category['retention_period_days'] . ' days'));
                }

                $stmt = $pdo->prepare(
                    'UPDATE data_records SET category_id = :category_id, record_reference = :reference, data_subject_type = :subject_type, collection_date = :collection_date, retention_end_date = :retention_end_date, status = :status, notes = :notes, updated_at = CURRENT_TIMESTAMP WHERE id = :id'
                );
                $stmt->execute([
                    'category_id' => $categoryId,
                    'reference' => $reference,
                    'subject_type' => $subjectType ?: null,
                    'collection_date' => $collectionDate,
                    'retention_end_date' => $retentionEndDate,
                    'status' => $status,
                    'notes' => $notes ?: null,
                    'id' => $id,
                ]);

                flash_set('success', 'Record updated successfully.');
                redirect('/retention/records/view?id=' . $id);
            }
        }
    }
}
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="card shadow-sm">
  <div class="card-body">
    <h1 class="h4 mb-3">Edit Record</h1>
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
            <option value="<?= escape_html($category['id']) ?>" <?= ((int)($_POST['category_id'] ?? $record['category_id']) === (int)$category['id']) ? 'selected' : '' ?>><?= escape_html($category['name']) ?></option>
          <?php endforeach; ?>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">Reference</label>
        <input type="text" name="record_reference" class="form-control" required value="<?= escape_html($_POST['record_reference'] ?? $record['record_reference']) ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Data subject type</label>
        <input type="text" name="data_subject_type" class="form-control" value="<?= escape_html($_POST['data_subject_type'] ?? $record['data_subject_type']) ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Collection date</label>
        <input type="date" name="collection_date" class="form-control" required value="<?= escape_html($_POST['collection_date'] ?? $record['collection_date']) ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Status</label>
        <select name="status" class="form-select">
          <?php foreach ($statuses as $option): ?>
          <option value="<?= escape_html($option) ?>" <?= ($_POST['status'] ?? $record['status']) === $option ? 'selected' : '' ?>><?= escape_html(str_replace('_', ' ', ucfirst($option))) ?></option>
          <?php endforeach; ?>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">Notes</label>
        <textarea name="notes" class="form-control" rows="4"><?= escape_html($_POST['notes'] ?? $record['notes']) ?></textarea>
      </div>
      <button class="btn btn-primary">Save record</button>
      <a href="/retention/records/view?id=<?= escape_html($id) ?>" class="btn btn-secondary ms-2">Cancel</a>
    </form>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
