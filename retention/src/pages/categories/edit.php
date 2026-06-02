<?php
$pdo = get_pdo();
$id = (int)($_GET['id'] ?? 0);
$error = null;

if ($id <= 0) {
    http_response_code(404);
    echo 'Category not found.';
    exit;
}

$stmt = $pdo->prepare('SELECT * FROM data_categories WHERE id = :id AND deleted_at IS NULL LIMIT 1');
$stmt->execute(['id' => $id]);
$category = $stmt->fetch();

if (!$category) {
    http_response_code(404);
    echo 'Category not found.';
    exit;
}

$legalBases = ['legal_obligation','contract','consent','legitimate_interest','vital_interest','public_task'];
$frameworks = ['GDPR','NDPR','BOTH'];
$retentionOptions = [0 => 'Consent withdrawal only', 30 => '30 days', 90 => '90 days', 180 => '180 days', 365 => '1 year', 730 => '2 years'];
$disposalMethods = ['delete','anonymise','archive'];
$disposalTriggers = ['date_based','consent_withdrawal'];
$reviewFrequencies = ['monthly','quarterly','annually'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validate_csrf($_POST['csrf_token'] ?? '')) {
        $error = 'Invalid CSRF token.';
    } else {
        $name = trim($_POST['name'] ?? '');
        $description = trim($_POST['description'] ?? '');
        $framework = $_POST['compliance_framework'] ?? 'GDPR';
        $legalBasis = $_POST['legal_basis'] ?? 'legal_obligation';
        $retentionDays = (int)($_POST['retention_period_days'] ?? 0);
        $retentionLabel = trim($_POST['retention_period_label'] ?? '');
        $disposalMethod = $_POST['disposal_method'] ?? 'delete';
        $disposalTrigger = $_POST['disposal_trigger'] ?? 'date_based';
        $requiresDualApproval = isset($_POST['requires_dual_approval']) ? 1 : 0;
        $reviewFrequency = $_POST['review_frequency'] ?? 'quarterly';

        if ($name === '' || $retentionLabel === '') {
            $error = 'Name and retention label are required.';
        } elseif (!in_array($framework, $frameworks, true) || !in_array($legalBasis, $legalBases, true) || !in_array($disposalMethod, $disposalMethods, true) || !in_array($disposalTrigger, $disposalTriggers, true) || !in_array($reviewFrequency, $reviewFrequencies, true)) {
            $error = 'Invalid category options selected.';
        } else {
            $stmt = $pdo->prepare(
                'UPDATE data_categories SET name = :name, description = :description, compliance_framework = :framework, legal_basis = :legal_basis, retention_period_days = :retention_days, retention_period_label = :retention_label, disposal_method = :disposal_method, disposal_trigger = :disposal_trigger, requires_dual_approval = :requires_dual_approval, review_frequency = :review_frequency, updated_at = CURRENT_TIMESTAMP WHERE id = :id'
            );
            $stmt->execute([
                'name' => $name,
                'description' => $description,
                'framework' => $framework,
                'legal_basis' => $legalBasis,
                'retention_days' => $retentionDays,
                'retention_label' => $retentionLabel,
                'disposal_method' => $disposalMethod,
                'disposal_trigger' => $disposalTrigger,
                'requires_dual_approval' => $requiresDualApproval,
                'review_frequency' => $reviewFrequency,
                'id' => $id,
            ]);

            flash_set('success', 'Category updated successfully.');
            redirect('/retention/categories');
        }
    }
}
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="card shadow-sm">
  <div class="card-body">
    <h1 class="h4 mb-3">Edit Category</h1>
    <?php if ($error): ?>
      <div class="alert alert-danger"><?= escape_html($error) ?></div>
    <?php endif; ?>
    <form method="post">
      <input type="hidden" name="csrf_token" value="<?= escape_html(csrf_token()) ?>">
      <div class="mb-3">
        <label class="form-label">Name</label>
        <input type="text" name="name" class="form-control" required value="<?= escape_html($_POST['name'] ?? $category['name']) ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Description</label>
        <textarea name="description" class="form-control" rows="3"><?= escape_html($_POST['description'] ?? $category['description']) ?></textarea>
      </div>
      <div class="row">
        <div class="col-md-4 mb-3">
          <label class="form-label">Compliance framework</label>
          <select name="compliance_framework" class="form-select">
            <?php foreach ($frameworks as $frameworkOption): ?>
              <option value="<?= escape_html($frameworkOption) ?>" <?= ($_POST['compliance_framework'] ?? $category['compliance_framework']) === $frameworkOption ? 'selected' : '' ?>><?= escape_html($frameworkOption) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <div class="col-md-4 mb-3">
          <label class="form-label">Legal basis</label>
          <select name="legal_basis" class="form-select">
            <?php foreach ($legalBases as $legalOption): ?>
              <option value="<?= escape_html($legalOption) ?>" <?= ($_POST['legal_basis'] ?? $category['legal_basis']) === $legalOption ? 'selected' : '' ?>><?= escape_html(str_replace('_', ' ', ucfirst($legalOption))) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <div class="col-md-4 mb-3">
          <label class="form-label">Retention period</label>
          <select name="retention_period_days" class="form-select">
            <?php foreach ($retentionOptions as $days => $label): ?>
              <option value="<?= escape_html((string)$days) ?>" <?= ((int)($_POST['retention_period_days'] ?? $category['retention_period_days']) === $days) ? 'selected' : '' ?>><?= escape_html($label) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label">Retention label</label>
        <input type="text" name="retention_period_label" class="form-control" required value="<?= escape_html($_POST['retention_period_label'] ?? $category['retention_period_label']) ?>">
      </div>
      <div class="row">
        <div class="col-md-4 mb-3">
          <label class="form-label">Disposal method</label>
          <select name="disposal_method" class="form-select">
            <?php foreach ($disposalMethods as $method): ?>
              <option value="<?= escape_html($method) ?>" <?= ($_POST['disposal_method'] ?? $category['disposal_method']) === $method ? 'selected' : '' ?>><?= escape_html(ucfirst($method)) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <div class="col-md-4 mb-3">
          <label class="form-label">Disposal trigger</label>
          <select name="disposal_trigger" class="form-select">
            <?php foreach ($disposalTriggers as $trigger): ?>
              <option value="<?= escape_html($trigger) ?>" <?= ($_POST['disposal_trigger'] ?? $category['disposal_trigger']) === $trigger ? 'selected' : '' ?>><?= escape_html(str_replace('_', ' ', ucfirst($trigger))) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <div class="col-md-4 mb-3">
          <label class="form-label">Review frequency</label>
          <select name="review_frequency" class="form-select">
            <?php foreach ($reviewFrequencies as $freq): ?>
              <option value="<?= escape_html($freq) ?>" <?= ($_POST['review_frequency'] ?? $category['review_frequency']) === $freq ? 'selected' : '' ?>><?= escape_html(ucfirst($freq)) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
      </div>
      <div class="form-check mb-3">
        <input class="form-check-input" type="checkbox" id="requires_dual_approval" name="requires_dual_approval" value="1" <?= ($_POST['requires_dual_approval'] ?? $category['requires_dual_approval']) ? 'checked' : '' ?>>
        <label class="form-check-label" for="requires_dual_approval">Requires dual approval</label>
      </div>
      <button class="btn btn-primary">Save changes</button>
      <a href="/retention/categories" class="btn btn-secondary ms-2">Cancel</a>
    </form>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
