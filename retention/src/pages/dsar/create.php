<?php
$pdo = get_pdo();
$error = null;

$types = ['access','rectification','erasure','restriction','portability','objection'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validate_csrf($_POST['csrf_token'] ?? '')) {
        $error = 'Invalid CSRF token.';
    } else {
        $requestType = $_POST['request_type'] ?? 'access';
        $name = trim($_POST['data_subject_name'] ?? '');
        $email = trim($_POST['data_subject_email'] ?? '');
        $phone = trim($_POST['data_subject_phone'] ?? '');
        $receivedDate = trim($_POST['received_date'] ?? '');
        $description = trim($_POST['description'] ?? '');

        if ($name === '' || $receivedDate === '') {
            $error = 'Subject name and received date are required.';
        } else {
            $dueDate = date('Y-m-d', strtotime($receivedDate . ' + 30 days'));
            $reference = 'DSAR-' . date('Y') . '-' . str_pad(random_int(1, 9999), 4, '0', STR_PAD_LEFT);

            $stmt = $pdo->prepare('INSERT INTO dsar_requests (reference, request_type, data_subject_name, data_subject_email, data_subject_phone, received_date, due_date, status, description, created_by) VALUES (:reference, :request_type, :name, :email, :phone, :received_date, :due_date, "open", :description, :created_by)');
            $stmt->execute([
                'reference' => $reference,
                'request_type' => $requestType,
                'name' => $name,
                'email' => $email ?: null,
                'phone' => $phone ?: null,
                'received_date' => $receivedDate,
                'due_date' => $dueDate,
                'description' => $description ?: null,
                'created_by' => current_user()['id'] ?? null,
            ]);

            flash_set('success', 'DSAR request logged successfully.');
            redirect('/retention/dsar');
        }
    }
}
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="card shadow-sm">
  <div class="card-body">
    <h1 class="h4 mb-3">Create DSAR Request</h1>
    <?php if ($error): ?>
      <div class="alert alert-danger"><?= escape_html($error) ?></div>
    <?php endif; ?>
    <form method="post">
      <input type="hidden" name="csrf_token" value="<?= escape_html(csrf_token()) ?>">
      <div class="row">
        <div class="col-md-6 mb-3">
          <label class="form-label">Request type</label>
          <select name="request_type" class="form-select">
            <?php foreach ($types as $type): ?>
            <option value="<?= escape_html($type) ?>" <?= ($_POST['request_type'] ?? '') === $type ? 'selected' : '' ?>><?= escape_html(ucfirst($type)) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <div class="col-md-6 mb-3">
          <label class="form-label">Received date</label>
          <input type="date" name="received_date" class="form-control" required value="<?= escape_html($_POST['received_date'] ?? date('Y-m-d')) ?>">
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label">Subject name</label>
        <input type="text" name="data_subject_name" class="form-control" required value="<?= escape_html($_POST['data_subject_name'] ?? '') ?>">
      </div>
      <div class="row">
        <div class="col-md-6 mb-3">
          <label class="form-label">Email</label>
          <input type="email" name="data_subject_email" class="form-control" value="<?= escape_html($_POST['data_subject_email'] ?? '') ?>">
        </div>
        <div class="col-md-6 mb-3">
          <label class="form-label">Phone</label>
          <input type="text" name="data_subject_phone" class="form-control" value="<?= escape_html($_POST['data_subject_phone'] ?? '') ?>">
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label">Description</label>
        <textarea name="description" class="form-control" rows="4"><?= escape_html($_POST['description'] ?? '') ?></textarea>
      </div>
      <button class="btn btn-primary">Create DSAR</button>
      <a href="/retention/dsar" class="btn btn-secondary ms-2">Cancel</a>
    </form>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
