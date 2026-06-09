<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/webhooks_lib.php';
require_role('admin');
$pdo = get_db();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $action = $_POST['action'] ?? '';
    if ($action === 'create' && trim($_POST['url'] ?? '') !== '') {
        $orgId = require_org_id();
        $pdo->prepare("INSERT INTO webhook_endpoints (organization_id, name, url, event_types, created_by) VALUES (:oid,:n,:u,:e,:by)")
            ->execute(['oid' => $orgId, 'n' => trim($_POST['name'] ?? 'Webhook'), 'u' => trim($_POST['url']), 'e' => trim($_POST['event_types'] ?? '*') ?: '*', 'by' => (int) current_user()['id']]);
        flash('success', 'Webhook added.');
    } elseif ($action === 'delete') {
        $orgId = require_org_id();
        $pdo->prepare('DELETE FROM webhook_endpoints WHERE id = :id AND organization_id = :o')->execute(['id' => (int) $_POST['id'], 'o' => $orgId]);
        flash('success', 'Webhook removed.');
    } elseif ($action === 'test') {
        $n = fire_ops_event($pdo, 'test.ping', ['message' => 'ADRS test event'], fn($u, $p) => [200, 'ok']);
        flash('success', "Test event fired to $n endpoint(s) (set ops_webhooks_enabled=1 in Settings to send for real).");
    }
    redirect(APP_URL . '/webhooks');
}
$orgId = require_org_id();
$whStmt = $pdo->prepare('SELECT * FROM webhook_endpoints WHERE organization_id = :o ORDER BY id DESC');
$whStmt->execute(['o' => $orgId]);
$rows = $whStmt->fetchAll();
$enabled = get_setting($pdo, 'ops_webhooks_enabled', '0') === '1';
$page_title = 'Ops Webhooks';
$active_nav = 'settings';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Operational Webhooks</h1>
  <span class="badge bg-<?= $enabled ? 'success' : 'secondary' ?>">sending <?= $enabled ? 'ON' : 'OFF' ?></span>
</div>
<p class="text-muted">Push key events (breaches, escalations, failures) to Slack, Teams, or any JSON endpoint. Use <code>*</code> for all events, or a comma-separated list (e.g. <code>breach.created,escalation.sent</code>).</p>
<div class="card shadow-sm mb-3"><div class="card-body">
  <form method="post" class="row g-2 align-items-end">
    <?= csrf_field() ?><input type="hidden" name="action" value="create">
    <div class="col-md-3"><label class="form-label small">Name</label><input name="name" class="form-control form-control-sm" placeholder="Slack #compliance"></div>
    <div class="col-md-5"><label class="form-label small">URL</label><input name="url" class="form-control form-control-sm" required placeholder="https://hooks.slack.com/…"></div>
    <div class="col-md-2"><label class="form-label small">Events</label><input name="event_types" class="form-control form-control-sm" value="*"></div>
    <div class="col-md-2"><button class="btn btn-primary btn-sm w-100">Add</button></div>
  </form>
</div></div>
<div class="card shadow-sm"><div class="card-body">
  <?php if (empty($rows)): ?><p class="text-muted mb-0">No webhooks configured.</p><?php else: ?>
  <table class="table table-hover align-middle">
    <thead><tr><th>Name</th><th>URL</th><th>Events</th><th>Last fired</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($rows as $w): ?>
      <tr>
        <td><?= escape_html($w['name']) ?></td>
        <td class="small"><?= escape_html(mb_strimwidth($w['url'], 0, 50, '…')) ?></td>
        <td><code><?= escape_html($w['event_types']) ?></code></td>
        <td class="small"><?= escape_html(format_datetime($w['last_fired_at'])) ?></td>
        <td><form method="post" data-confirm="Remove webhook?"><?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<?= (int)$w['id'] ?>"><button class="btn btn-sm btn-outline-danger">Delete</button></form></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
  <form method="post" class="mt-2"><?= csrf_field() ?><input type="hidden" name="action" value="test"><button class="btn btn-outline-secondary btn-sm">Send test event</button></form>
  <?php endif; ?>
</div></div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
