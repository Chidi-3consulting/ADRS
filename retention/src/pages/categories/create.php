<?php
$pdo = get_pdo();
$error = null;

$frameworkOptions = ['GDPR', 'NDPR', 'BOTH'];
$legalBasisOptions = ['legal_obligation', 'contract', 'consent', 'legitimate_interest', 'vital_interest', 'public_task'];
$methodOptions = ['delete', 'anonymise', 'archive'];
$triggerOptions = ['date_based', 'consent_withdrawal'];
$reviewFrequencyOptions = ['monthly', 'quarterly', 'annually'];

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
        $method = $_POST['disposal_method'] ?? 'delete';
        $trigger = $_POST['disposal_trigger'] ?? 'date_based';
        $requiresDual = isset($_POST['requires_dual_approval']) ? 1 : 0;
        $reviewFrequency = $_POST['review_frequency'] ?? 'quarterly';

        if ($name === '' || $retentionLabel === '') {
            $error = 'Name and retention label are required.';
        } else {
            $stmt = $pdo->prepare('INSERT INTO data_categories
                (name, description, compliance_framework, legal_basis, retention_period_days, retention_period_label, disposal_method, disposal_trigger, requires_dual_approval, review_frequency, source)
                VALUES (:name, :description, :framework, :legal_basis, :retention_days, :retention_label, :method, :trigger, :requires_dual_approval, :review_frequency, "custom")');
            $stmt->execute([
                'name' => $name,
                'description' => $description,
                'framework' => $framework,
                'legal_basis' => $legalBasis,
                'retention_days' => $retentionDays,
                'retention_label' => $retentionLabel,
                'method' => $method,
                'trigger' => $trigger,
                'requires_dual_approval' => $requiresDual,
                'review_frequency' => $reviewFrequency,
            ]);

            flash_set('success', 'Category created successfully.');
            redirect('/retention/categories');
        }
    }
}
?>
<?php require __DIR__ . '/../../includes/layout_header.php'; ?>
<div class="card shadow-sm">
  <div class="card-body">
    <h1 class="h4 mb-3">Create Data Category</h1>
    <?php if ($error): ?>
      <div class="alert alert-danger"><?= escape_html($error) ?></div>
    <?php endif; ?>
    <form method="post">
      <input type="hidden" name="csrf_token" value="<?= escape_html(csrf_token()) ?>">
      <div class="mb-3">
        <label class="form-label">Name</label>
        <input type="text" name="name" class="form-control" required value="<?= escape_html($_POST['name'] ?? '') ?>">
      </div>
      <div class="mb-3">
        <label class="form-label">Description</label>
        <textarea name="description" class="form-control" rows="3"><?= escape_html($_POST['description'] ?? '') ?></textarea>
      </div>
      <div class="row">
        <div class="col-md-6 mb-3">
          <label class="form-label">Compliance framework</label>
          <select name="compliance_framework" class="form-select">
            <?php foreach ($frameworkOptions as $option): ?>
            <option value="<?= escape_html($option) ?>" <?= ($_POST['compliance_framework'] ?? '') === $option ? 'selected' : '' ?>><?= escape_html($option) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <div class="col-md-6 mb-3">
          <label class="form-label">Legal basis</label>
          <select name="legal_basis" class="form-select">
            <?php foreach ($legalBasisOptions as $option): ?>
            <option value="<?= escape_html($option) ?>" <?= ($_POST['legal_basis'] ?? '') === $option ? 'selected' : '' ?>><?= escape_html($option) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
      </div>
      <div class="row">
        <div class="col-md-4 mb-3">
          <label class="form-label">Retention days</label>
          <input type="number" name="retention_period_days" class="form-control" value="<?= escape_html($_POST['retention_period_days'] ?? '0') ?>">
        </div>
        <div class="col-md-8 mb-3">
          <label class="form-label">Retention label</label>
          <input type="text" name="retention_period_label" class="form-control" required value="<?= escape_html($_POST['retention_period_label'] ?? '') ?>">
        </div>
      </div>
      <div class="row">
        <div class="col-md-6 mb-3">
          <label class="form-label">Disposal method</label>
          <select name="disposal_method" class="form-select">
            <?php foreach ($methodOptions as $option): ?>
            <option value="<?= escape_html($option) ?>" <?= ($_POST['disposal_method'] ?? '') === $option ? 'selected' : '' ?>><?= escape_html($option) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
        <div class="col-md-6 mb-3">
          <label class="form-label">Disposal trigger</label>
          <select name="disposal_trigger" class="form-select">
            <?php foreach ($triggerOptions as $option): ?>
            <option value="<?= escape_html($option) ?>" <?= ($_POST['disposal_trigger'] ?? '') === $option ? 'selected' : '' ?>><?= escape_html($option) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
      </div>
      <div class="mb-3 form-check">
        <input type="checkbox" name="requires_dual_approval" id="dualApproval" class="form-check-input" <?= isset($_POST['requires_dual_approval']) ? 'checked' : '' ?>>
        <label class="form-check-label" for="dualApproval">Requires dual approval</label>
      </div>
      <div class="mb-3">
        <label class="form-label">Review frequency</label>
        <select name="review_frequency" class="form-select">
          <?php foreach ($reviewFrequencyOptions as $option): ?>
          <option value="<?= escape_html($option) ?>" <?= ($_POST['review_frequency'] ?? '') === $option ? 'selected' : '' ?>><?= escape_html(ucfirst($option)) ?></option>
          <?php endforeach; ?>
        </select>
      </div>
      <button class="btn btn-primary">Create category</button>
      <a href="/retention/categories" class="btn btn-secondary ms-2">Cancel</a>
    </form>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
