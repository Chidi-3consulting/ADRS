<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/import_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
$preview = null; $summary = null; $error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $stage = $_POST['stage'] ?? 'validate';
    if ($stage === 'validate') {
        $file = $_FILES['csv'] ?? null;
        if (!$file || ($file['error'] ?? 1) !== UPLOAD_ERR_OK) {
            $error = 'Please choose a CSV file.';
        } else {
            $content = file_get_contents($file['tmp_name']);
            $rows = parse_csv($content);
            $check = validate_import_rows($pdo, $rows);
            $_SESSION['import_rows'] = $rows;
            $_SESSION['import_name'] = $file['name'];
            $preview = ['rows' => $rows, 'valid' => count($check['valid']), 'errors' => $check['errors']];
        }
    } elseif ($stage === 'commit') {
        $rows = $_SESSION['import_rows'] ?? [];
        $name = $_SESSION['import_name'] ?? 'import.csv';
        if (!$rows) { $error = 'Nothing to import — please upload a file first.'; }
        else {
            $summary = commit_import($pdo, $name, $rows, (int) current_user()['id']);
            unset($_SESSION['import_rows'], $_SESSION['import_name']);
            flash('success', "Imported {$summary['imported']} record(s); {$summary['errors']} skipped.");
            redirect(APP_URL . '/records');
        }
    }
}
$page_title = 'Bulk Import';
$active_nav = 'records';
require __DIR__ . '/../../includes/layout_header.php';
?>
<h1 class="h4 mb-1">Bulk Import Records</h1>
<p class="text-muted small">CSV header: <code>category_name, record_reference, data_subject_type, collection_date</code>. Validation runs first; nothing is written until you confirm (B8 two-pass).</p>
<?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>

<?php if ($preview === null): ?>
<form method="post" enctype="multipart/form-data" class="card shadow-sm"><div class="card-body">
  <?= csrf_field() ?><input type="hidden" name="stage" value="validate">
  <div class="mb-3"><label class="form-label">CSV file</label><input type="file" name="csv" accept=".csv" class="form-control" required></div>
  <button class="btn btn-primary">Validate</button>
</div></form>
<?php else: ?>
<div class="card shadow-sm"><div class="card-body">
  <p><strong><?= (int)$preview['valid'] ?></strong> valid row(s), <strong><?= count($preview['errors']) ?></strong> with errors, out of <?= count($preview['rows']) ?>.</p>
  <?php if ($preview['errors']): ?>
    <div class="alert alert-warning"><strong>Rows with errors (skipped on import):</strong>
      <ul class="mb-0 small"><?php foreach ($preview['errors'] as $e): ?><li>Line <?= (int)$e['line'] ?>: <?= escape_html($e['error']) ?></li><?php endforeach; ?></ul>
    </div>
  <?php endif; ?>
  <?php if ($preview['valid'] > 0): ?>
    <form method="post"><?= csrf_field() ?><input type="hidden" name="stage" value="commit">
      <button class="btn btn-primary">Import <?= (int)$preview['valid'] ?> valid record(s)</button>
      <a href="<?= APP_URL ?>/import" class="btn btn-secondary ms-2">Start over</a>
    </form>
  <?php else: ?>
    <a href="<?= APP_URL ?>/import" class="btn btn-secondary">Start over</a>
  <?php endif; ?>
</div></div>
<?php endif; ?>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
