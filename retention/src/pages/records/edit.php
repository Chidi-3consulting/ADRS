<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/records_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
$id = (int) ($_GET['id'] ?? 0);
$record = $id > 0 ? fetch_record($pdo, $id) : null;
if ($record === null) { http_response_code(404); require __DIR__ . '/../../../404.php'; exit; }
$error = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $reference = trim($_POST['record_reference'] ?? '');
    $subject = trim($_POST['data_subject_type'] ?? '');
    $collection = trim($_POST['collection_date'] ?? $record['collection_date']);
    $notes = trim($_POST['notes'] ?? '');
    if ($reference === '' || $collection === '') {
        $error = 'Reference and collection date are required.';
    } else {
        // Recompute retention end from the record's category (date_based only).
        $cat = fetch_category($pdo, (int) $record['category_id']);
        $retentionEnd = $cat ? compute_retention_end($cat, $collection) : $record['retention_end_date'];
        $pdo->prepare(
            "UPDATE data_records SET record_reference=:ref, data_subject_type=:subj, collection_date=:cd,
                    retention_end_date=:rend, notes=:notes WHERE id=:id"
        )->execute([
            'ref' => $reference, 'subj' => $subject ?: null, 'cd' => $collection,
            'rend' => $retentionEnd, 'notes' => $notes ?: null, 'id' => $id,
        ]);
        log_audit($pdo, 'record_updated', 'data_record', $id, (int) current_user()['id'], ['reference' => $reference], get_client_ip());
        flash('success', 'Record updated.');
        redirect(APP_URL . '/records/view?id=' . $id);
    }
}
$page_title = 'Edit Record';
$active_nav = 'records';
require __DIR__ . '/../../includes/layout_header.php';
$cur = fn($k) => escape_html($_POST[$k] ?? (string) ($record[$k] ?? ''));
?>
<div class="card shadow-sm" style="max-width:680px"><div class="card-body">
  <h1 class="h4 mb-3">Edit Record</h1>
  <p class="text-muted">Category: <strong><?= escape_html($record['category_name']) ?></strong> (change via Reassign on the record page).</p>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <div class="mb-3"><label class="form-label">Reference *</label><input name="record_reference" class="form-control" required value="<?= $cur('record_reference') ?>"></div>
    <div class="mb-3"><label class="form-label">Data subject type</label><input name="data_subject_type" class="form-control" value="<?= $cur('data_subject_type') ?>"></div>
    <div class="mb-3"><label class="form-label">Collection date *</label><input type="date" name="collection_date" class="form-control" required value="<?= $cur('collection_date') ?>"></div>
    <div class="mb-3"><label class="form-label">Notes</label><textarea name="notes" class="form-control" rows="3"><?= $cur('notes') ?></textarea></div>
    <button class="btn btn-primary">Save</button>
    <a href="<?= APP_URL ?>/records/view?id=<?= $id ?>" class="btn btn-secondary ms-2">Cancel</a>
  </form>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
