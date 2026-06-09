<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/categories_lib.php';
require_login();
$pdo = get_db();
$id = (int) ($_GET['id'] ?? 0);
$category = $id > 0 ? fetch_category($pdo, $id) : null;
if ($category === null) { http_response_code(404); require __DIR__ . '/../../../404.php'; exit; }
assert_org_row($category);

// Data Owners may only view their own categories.
if (has_role('data_owner') && (int) $category['owner_id'] !== (int) current_user()['id']) {
    http_response_code(403); exit('Forbidden');
}

$orgId = require_org_id();
$activeStmt = $pdo->prepare("SELECT COUNT(*) c FROM data_records WHERE organization_id = :o AND category_id = :id AND deleted_at IS NULL AND status != 'disposed'");
$activeStmt->execute(['o' => $orgId, 'id' => $id]);
$active = (int) $activeStmt->fetch()['c'];
$dueStmt = $pdo->prepare("SELECT COUNT(*) c FROM data_records WHERE organization_id = :o AND category_id = :id AND status = 'due_review'");
$dueStmt->execute(['o' => $orgId, 'id' => $id]);
$dueReview = (int) $dueStmt->fetch()['c'];
$holdStmt = $pdo->prepare("SELECT COUNT(*) c FROM data_records WHERE organization_id = :o AND category_id = :id AND legal_hold = 1");
$holdStmt->execute(['o' => $orgId, 'id' => $id]);
$onHold = (int) $holdStmt->fetch()['c'];
$ownerName = null;
if ($category['owner_id']) {
    $os = $pdo->prepare("SELECT name FROM users WHERE id=:o"); $os->execute(['o'=>$category['owner_id']]);
    $ownerName = $os->fetch()['name'] ?? null;
}
$page_title = 'Category: ' . $category['name'];
$active_nav = 'categories';
require __DIR__ . '/../../includes/layout_header.php';
?>
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0"><?= escape_html($category['name']) ?> <?= get_framework_badge($category['compliance_framework']) ?></h1>
  <div>
    <?php if (has_role('admin','dpo')): ?><a href="<?= APP_URL ?>/categories/edit?id=<?= $id ?>" class="btn btn-outline-primary">Edit</a><?php endif; ?>
    <a href="<?= APP_URL ?>/categories" class="btn btn-secondary">Back</a>
  </div>
</div>
<div class="row g-3 mb-3">
  <div class="col-md-3"><div class="card shadow-sm"><div class="card-body"><div class="text-muted small">Active records</div><div class="h3 mb-0"><?= $active ?></div></div></div></div>
  <div class="col-md-3"><div class="card shadow-sm"><div class="card-body"><div class="text-muted small">Due for review</div><div class="h3 mb-0"><?= $dueReview ?></div></div></div></div>
  <div class="col-md-3"><div class="card shadow-sm"><div class="card-body"><div class="text-muted small">On legal hold</div><div class="h3 mb-0"><?= $onHold ?></div></div></div></div>
  <div class="col-md-3"><div class="card shadow-sm"><div class="card-body"><div class="text-muted small">Dual approval</div><div class="h3 mb-0"><?= (int)$category['requires_dual_approval'] ? 'Yes 🔐' : 'No' ?></div></div></div></div>
</div>
<div class="card shadow-sm"><div class="card-body">
  <dl class="row mb-0">
    <dt class="col-sm-3">Description</dt><dd class="col-sm-9"><?= escape_html($category['description'] ?? '—') ?></dd>
    <dt class="col-sm-3">Legal basis</dt><dd class="col-sm-9"><?= escape_html(get_legal_basis_label($category['legal_basis'])) ?></dd>
    <dt class="col-sm-3">Disposal trigger</dt><dd class="col-sm-9"><?= $category['disposal_trigger']==='consent_withdrawal' ? '👤 Consent withdrawal' : '📅 Date-based' ?></dd>
    <dt class="col-sm-3">Retention</dt><dd class="col-sm-9"><?= $category['disposal_trigger']==='consent_withdrawal' ? 'Until consent withdrawn' : escape_html($category['retention_period_label']) ?></dd>
    <dt class="col-sm-3">Disposal method</dt><dd class="col-sm-9"><?= escape_html(get_disposal_method_label($category['disposal_method'])) ?></dd>
    <dt class="col-sm-3">Review frequency</dt><dd class="col-sm-9"><?= escape_html(ucfirst($category['review_frequency'])) ?></dd>
    <dt class="col-sm-3">Owner</dt><dd class="col-sm-9"><?= escape_html($ownerName ?? '—') ?></dd>
    <dt class="col-sm-3">Source</dt><dd class="col-sm-9"><?= $category['source']==='seeded' ? '📚 Seeded' : 'Custom' ?></dd>
  </dl>
</div></div>
<?php if (has_role('admin')): ?>
<form method="post" action="<?= APP_URL ?>/categories/delete" class="mt-3" data-confirm="Soft-delete this category? Blocked if active records exist.">
  <?= csrf_field() ?>
  <input type="hidden" name="id" value="<?= $id ?>">
  <button class="btn btn-outline-danger btn-sm">Delete category</button>
</form>
<?php endif; ?>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
