<?php
$pdo = get_pdo();
$id = (int)($_GET['id'] ?? 0);
$error = null;

if ($id <= 0) {
    http_response_code(404);
    echo 'DSAR request not found.';
    exit;
}

$users = $pdo->query('SELECT id, name FROM users WHERE deleted_at IS NULL ORDER BY name')->fetchAll();
$statusOptions = ['open','identity_check','in_progress','completed','rejected','extended'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validate_csrf($_POST['csrf_token'] ?? '')) {
        $error = 'Invalid CSRF token.';
    } else {
        $status = $_POST['status'] ?? 'open';
        $assignedTo = (int)($_POST['assigned_to'] ?? 0) ?: null;
        $internalNotes = trim($_POST['internal_notes'] ?? '');
        $responseNotes = trim($_POST['response_notes'] ?? '');

        if (!in_array($status, $statusOptions, true)) {
            $error = 'Invalid status selected.';
        } else {
            $stmt = $pdo->prepare(
                'UPDATE dsar_requests SET status = :status, assigned_to = :assigned_to, internal_notes = :internal_notes, response_notes = :response_notes, updated_at = CURRENT_TIMESTAMP WHERE id = :id'
            );
            $stmt->execute([
                'status' => $status,
                'assigned_to' => $assignedTo,
                'internal_notes' => $internalNotes ?: null,
                'response_notes' => $responseNotes ?: null,
                'id' => $id,
            ]);

            flash_set('success', 'DSAR request updated successfully.');
            redirect('/retention/dsar/view?id=' . $id);
        }
    }
}

$stmt = $pdo->prepare(
    'SELECT dr.*, u.name AS created_by_name, a.name AS assigned_to_name
     FROM dsar_requests dr
     LEFT JOIN users u ON dr.created_by = u.id
     LEFT JOIN users a ON dr.assigned_to = a.id
     WHERE dr.id = :id'
);
$stmt->execute(['id' => $id]);
$dsar = $stmt->fetch();

if (!$dsar) {
    http_response_code(404);
    echo 'DSAR request not found.';
    exit;
}
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h4">DSAR request</h1>
    <p class="text-muted mb-0">Reference <?= escape_html($dsar['reference']) ?> — status <?= escape_html($dsar['status']) ?></p>
  </div>
  <a href="/retention/dsar" class="btn btn-secondary">Back to DSAR list</a>
</div>
<?php if ($error): ?>
<div class="alert alert-danger"><?= escape_html($error) ?></div>
<?php endif; ?>
<div class="row">
  <div class="col-lg-7">
    <div class="card shadow-sm mb-3">
      <div class="card-body">
        <h5 class="card-title">Request details</h5>
        <div class="row">
          <div class="col-md-6 mb-3">
            <strong>Request type</strong>
            <p><?= escape_html($dsar['request_type']) ?></p>
          </div>
          <div class="col-md-6 mb-3">
            <strong>Compliance</strong>
            <p><?= escape_html($dsar['compliance_framework']) ?></p>
          </div>
          <div class="col-md-6 mb-3">
            <strong>Data subject</strong>
            <p><?= escape_html($dsar['data_subject_name']) ?></p>
          </div>
          <div class="col-md-6 mb-3">
            <strong>Received date</strong>
            <p><?= escape_html($dsar['received_date']) ?></p>
          </div>
          <div class="col-md-6 mb-3">
            <strong>Due date</strong>
            <p><?= escape_html($dsar['due_date']) ?></p>
          </div>
          <div class="col-md-6 mb-3">
            <strong>Assigned to</strong>
            <p><?= escape_html($dsar['assigned_to_name'] ?? 'Unassigned') ?></p>
          </div>
          <div class="col-md-12 mb-3">
            <strong>Description</strong>
            <p><?= nl2br(escape_html($dsar['description'] ?? '')) ?></p>
          </div>
          <div class="col-md-12 mb-3">
            <strong>Internal notes</strong>
            <p><?= nl2br(escape_html($dsar['internal_notes'] ?? '')) ?></p>
          </div>
          <div class="col-md-12 mb-3">
            <strong>Response notes</strong>
            <p><?= nl2br(escape_html($dsar['response_notes'] ?? '')) ?></p>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div class="col-lg-5">
    <div class="card shadow-sm">
      <div class="card-body">
        <h5 class="card-title">Update DSAR</h5>
        <form method="post">
          <input type="hidden" name="csrf_token" value="<?= escape_html(csrf_token()) ?>">
          <div class="mb-3">
            <label class="form-label">Status</label>
            <select name="status" class="form-select">
              <?php foreach ($statusOptions as $statusOption): ?>
              <option value="<?= escape_html($statusOption) ?>" <?= ($dsar['status'] === $statusOption) ? 'selected' : '' ?>><?= escape_html(str_replace('_', ' ', ucfirst($statusOption))) ?></option>
              <?php endforeach; ?>
            </select>
          </div>
          <div class="mb-3">
            <label class="form-label">Assigned user</label>
            <select name="assigned_to" class="form-select">
              <option value="">Unassigned</option>
              <?php foreach ($users as $user): ?>
              <option value="<?= escape_html($user['id']) ?>" <?= ($dsar['assigned_to'] == $user['id']) ? 'selected' : '' ?>><?= escape_html($user['name']) ?></option>
              <?php endforeach; ?>
            </select>
          </div>
          <div class="mb-3">
            <label class="form-label">Internal notes</label>
            <textarea name="internal_notes" class="form-control" rows="4"><?= escape_html($_POST['internal_notes'] ?? $dsar['internal_notes']) ?></textarea>
          </div>
          <div class="mb-3">
            <label class="form-label">Response notes</label>
            <textarea name="response_notes" class="form-control" rows="4"><?= escape_html($_POST['response_notes'] ?? $dsar['response_notes']) ?></textarea>
          </div>
          <button class="btn btn-primary">Update DSAR</button>
        </form>
      </div>
    </div>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
