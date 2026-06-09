<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/compliance_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
$orgId = require_org_id();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    if (($_POST['action'] ?? '') === 'generate') {
        $n = generate_ropa_from_categories($pdo, (int) current_user()['id']);
        flash('success', "$n RoPA entries generated from your data categories.");
    }
    redirect(APP_URL . '/ropa');
}

if (($_GET['export'] ?? '') === 'csv') {
    $exp = $pdo->prepare('SELECT * FROM ropa_entries WHERE organization_id = :o ORDER BY activity_name');
    $exp->execute(['o' => $orgId]);
    $rows = $exp->fetchAll();
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="ropa_article30_' . date('Y-m-d') . '.csv"');
    echo "\xEF\xBB\xBF";
    $out = fopen('php://output', 'w');
    fputcsv($out, ['Activity','Controller','DPO contact','Purpose','Lawful basis','Data subjects','Data categories','Recipients','Transfers','Retention','Security measures']);
    foreach ($rows as $r) {
        fputcsv($out, [$r['activity_name'],$r['controller_name'],$r['dpo_contact'],$r['purpose'],$r['lawful_basis'],$r['data_subjects'],$r['data_categories'],$r['recipients'],$r['third_country_transfers'],$r['retention_summary'],$r['security_measures']]);
    }
    fclose($out);
    exit;
}

$stmt = $pdo->prepare('SELECT * FROM ropa_entries WHERE organization_id = :o ORDER BY activity_name');
$stmt->execute(['o' => $orgId]);
$rows = $stmt->fetchAll();
$page_title = 'Record of Processing (Art. 30)';
$active_nav = 'ropa';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Record of Processing Activities (RoPA)</h1>
  <div class="d-flex gap-2">
    <form method="post"><?= csrf_field() ?><input type="hidden" name="action" value="generate"><button class="btn btn-outline-secondary btn-sm">Generate from categories</button></form>
    <a href="<?= APP_URL ?>/ropa?export=csv" class="btn btn-outline-primary btn-sm">Export CSV</a>
    <a href="<?= APP_URL ?>/ropa/create" class="btn btn-primary btn-sm">New entry</a>
  </div>
</div>
<p class="text-muted">Your Article 30 register — one entry per processing activity. "Generate from categories" seeds drafts from your data register.</p>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($rows)): ?><p class="text-muted mb-0">No RoPA entries yet.</p><?php else: ?>
  <div class="table-responsive"><table class="table table-hover align-middle">
    <thead><tr><th>Activity</th><th>Lawful basis</th><th>Purpose</th><th>Retention</th><th>Recipients</th></tr></thead>
    <tbody>
    <?php foreach ($rows as $r): ?>
      <tr><td><?= escape_html($r['activity_name']) ?></td><td><?= escape_html($r['lawful_basis'] ?? '—') ?></td>
          <td class="small"><?= escape_html(mb_strimwidth((string)$r['purpose'], 0, 80, '…')) ?></td>
          <td class="small"><?= escape_html($r['retention_summary'] ?? '—') ?></td>
          <td class="small"><?= escape_html($r['recipients'] ?? '—') ?></td></tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
