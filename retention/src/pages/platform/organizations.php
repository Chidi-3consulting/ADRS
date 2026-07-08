<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/platform_lib.php';
require_platform_admin();

$pdo = get_db();
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $orgId = (int) ($_POST['org_id'] ?? 0);
    $status = $_POST['status'] ?? '';
    if ($orgId > 0) {
        platform_set_org_status($pdo, $orgId, $status);
        flash('success', 'Organisation updated.');
    }
    redirect(APP_URL . '/platform/organizations');
}

$orgs = platform_list_organizations($pdo);
$page_title = 'Organisations';
$active_nav = '';
require __DIR__ . '/../../includes/layout_header.php';
?>
<h1 class="h4 mb-3">All organisations</h1>
<div class="card shadow-sm"><div class="card-body table-responsive">
  <table class="table table-sm align-middle">
    <thead><tr><th>Name</th><th>Domain</th><th>Tier</th><th>Status</th><th>Subscription</th><th>Users</th><th>Records</th><th>Trial ends</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($orgs as $o): ?>
      <tr>
        <td><?= escape_html($o['name']) ?><br><span class="text-muted small"><?= escape_html($o['slug']) ?></span></td>
        <td><code><?= escape_html($o['primary_domain'] ?? '—') ?></code></td>
        <td><?= escape_html($o['tier']) ?></td>
        <td><?= escape_html($o['status']) ?></td>
        <td><?= escape_html($o['subscription_status'] ?? '') ?></td>
        <td><?= (int) $o['user_count'] ?></td>
        <td><?= (int) $o['record_count'] ?></td>
        <td><?= format_datetime($o['trial_ends_at'] ?? null) ?></td>
        <td>
          <form method="post" class="d-inline"><?= csrf_field() ?>
            <input type="hidden" name="org_id" value="<?= (int) $o['id'] ?>">
            <select name="status" class="form-select form-select-sm d-inline-block" style="width:auto" onchange="this.form.submit()">
              <?php foreach (['active','trial','suspended'] as $s): ?>
                <option value="<?= $s ?>" <?= $o['status'] === $s ? 'selected' : '' ?>><?= $s ?></option>
              <?php endforeach; ?>
            </select>
          </form>
        </td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
</div></div>
<p class="mt-3"><a href="<?= APP_URL ?>/platform">&larr; Platform dashboard</a></p>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
