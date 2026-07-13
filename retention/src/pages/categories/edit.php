<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/categories_lib.php';
require_once __DIR__ . '/../../includes/retention_rules_lib.php';
require_role('admin', 'dpo');
$pdo = get_db();
$id = (int) ($_GET['id'] ?? 0);
$category = $id > 0 ? fetch_category($pdo, $id) : null;
if ($category === null) { http_response_code(404); require __DIR__ . '/../../../404.php'; exit; }
$error = null;
$ruleMsg = null;

$owners = list_org_users($pdo, "role = 'data_owner'");
$regulationsList = list_regulations($pdo);
$rules = list_category_retention_rules($pdo, $id);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $action = $_POST['action'] ?? 'save_category';
    if ($action === 'add_rule') {
        try {
            create_retention_rule($pdo, $id, [
                'rule_name'              => trim($_POST['rule_name'] ?? ''),
                'legal_basis'            => $_POST['rule_legal_basis'] ?? 'legal_obligation',
                'processing_purpose'     => trim($_POST['processing_purpose'] ?? ''),
                'institution_type'       => $_POST['institution_type'] ?? 'all',
                'retention_period_days'  => (int) ($_POST['rule_retention_days'] ?? 0),
                'retention_period_label' => trim($_POST['rule_retention_label'] ?? ''),
                'disposal_method'        => $_POST['rule_disposal_method'] ?? 'delete',
                'disposal_trigger'       => $_POST['rule_disposal_trigger'] ?? 'date_based',
                'requires_dual_approval' => isset($_POST['rule_requires_dual_approval']) ? 1 : 0,
                'is_default'             => 0,
            ]);
            flash('success', 'Retention rule added.');
            redirect(APP_URL . '/categories/edit?id=' . $id);
        } catch (Throwable $e) {
            $ruleMsg = $e->getMessage();
        }
    } elseif ($action === 'remove_rule') {
        $rid = (int) ($_POST['rule_id'] ?? 0);
        if (!deactivate_retention_rule($pdo, $rid)) {
            flash('error', 'Cannot remove this rule — it is the default or has active records.');
        } else {
            flash('success', 'Retention rule removed.');
        }
        redirect(APP_URL . '/categories/edit?id=' . $id);
    } else {
        try {
            if (trim($_POST['name'] ?? '') === '') { throw new InvalidArgumentException('Name is required.'); }
            
            $selectedFrameworks = $_POST['compliance_framework'] ?? [];
            if (empty($selectedFrameworks)) {
                throw new InvalidArgumentException('At least one regulation framework must be selected.');
            }
            $frameworkString = implode(',', $selectedFrameworks);

            $res = update_category($pdo, $id, [
                'name' => trim($_POST['name']),
                'description' => trim($_POST['description'] ?? ''),
                'retention_reason' => trim($_POST['retention_reason'] ?? ''),
                'compliance_framework' => $frameworkString,
                'legal_basis' => $_POST['legal_basis'] ?? 'legal_obligation',
                'retention_period_days' => (int) ($_POST['retention_period_days'] ?? 0),
                'retention_period_label' => trim($_POST['retention_period_label'] ?? ''),
                'disposal_method' => $_POST['disposal_method'] ?? 'delete',
                'disposal_trigger' => $_POST['disposal_trigger'] ?? 'date_based',
                'requires_dual_approval' => isset($_POST['requires_dual_approval']) ? 1 : 0,
                'owner_id' => ($_POST['owner_id'] ?? '') !== '' ? (int) $_POST['owner_id'] : null,
                'review_frequency' => $_POST['review_frequency'] ?? 'quarterly',
            ], (int) current_user()['id']);
            
            $msg = 'Category updated.';
            if ($res['recalc_queued'] > 0) {
                $msg .= " {$res['recalc_queued']} record(s) queued for recalculation review — no record dates changed.";
            }
            flash('success', $msg);
            redirect(APP_URL . '/categories');
        } catch (Throwable $e) {
            $error = $e->getMessage();
        }
    }
}
$page_title = 'Edit Category';
$active_nav = 'categories';
require __DIR__ . '/../../includes/layout_header.php';
$cur = fn($k) => escape_html($_POST[$k] ?? (string) ($category[$k] ?? ''));
$currentFrameworks = array_filter(array_map('trim', explode(',', $category['compliance_framework'] ?? '')));
?>
<div class="card shadow-sm" style="max-width:820px"><div class="card-body">
  <h1 class="h4 mb-3 fw-bold text-dark">Edit Data Category</h1>
  <?php if ($category['source'] === 'seeded'): ?><div class="alert alert-info">📚 Seeded from the compliance library — edits are allowed.</div><?php endif; ?>
  <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
  <div class="alert alert-warning small">Changing the default retention period will queue affected records for DPO recalculation review (B2). No record dates change until reviewed.</div>
  
  <form method="post">
    <?= csrf_field() ?>
    <input type="hidden" name="action" value="save_category">
    
    <div class="mb-3"><label class="form-label">Name *</label>
      <input name="name" class="form-control" required value="<?= $cur('name') ?>"></div>
    <div class="mb-3"><label class="form-label">Description</label>
      <textarea name="description" class="form-control" rows="2"><?= $cur('description') ?></textarea></div>
    <div class="mb-3"><label class="form-label">Retention Reason / Lawful Purpose</label>
      <textarea name="retention_reason" class="form-control" rows="2" placeholder="Describe the business/legal necessity..."><?= $cur('retention_reason') ?></textarea></div>
    
    <div class="mb-3">
      <label class="form-label d-block">Applicable Regulations *</label>
      <div class="row g-2">
        <?php foreach ($regulationsList as $reg):
          $checked = in_array($reg['code'], $_POST['compliance_framework'] ?? $currentFrameworks) ? 'checked' : '';
        ?>
          <div class="col-md-6">
            <div class="form-check border p-2 rounded bg-light-subtle">
              <input class="form-check-input ms-0 me-2" type="checkbox" name="compliance_framework[]" value="<?= escape_html($reg['code']) ?>" id="reg-<?= escape_html($reg['code']) ?>" <?= $checked ?>>
              <label class="form-check-label small" for="reg-<?= escape_html($reg['code']) ?>">
                <strong><?= escape_html($reg['code']) ?></strong> — <?= escape_html($reg['name']) ?>
              </label>
            </div>
          </div>
        <?php endforeach; ?>
      </div>
    </div>

    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Legal basis *</label>
        <select name="legal_basis" class="form-select">
          <?php foreach (['legal_obligation','contract','consent','legitimate_interest','vital_interest','public_task'] as $o): ?>
            <option value="<?= $o ?>" <?= ($_POST['legal_basis'] ?? $category['legal_basis'])===$o?'selected':'' ?>><?= escape_html(get_legal_basis_label($o)) ?></option>
          <?php endforeach; ?>
        </select></div>
      <div class="col-md-6 mb-3"><label class="form-label">Disposal trigger *</label>
        <select name="disposal_trigger" id="trigger" class="form-select">
          <option value="date_based" <?= ($_POST['disposal_trigger'] ?? $category['disposal_trigger'])==='date_based'?'selected':'' ?>>📅 Date-based</option>
          <option value="consent_withdrawal" <?= ($_POST['disposal_trigger'] ?? $category['disposal_trigger'])==='consent_withdrawal'?'selected':'' ?>>👤 Consent withdrawal</option>
        </select></div>
    </div>

    <div id="retentionBlock" class="row">
      <div class="col-md-4 mb-3"><label class="form-label">Retention days</label>
        <input type="number" name="retention_period_days" class="form-control" value="<?= $cur('retention_period_days') ?>"></div>
      <div class="col-md-8 mb-3"><label class="form-label">Retention label</label>
        <input name="retention_period_label" class="form-control" value="<?= $cur('retention_period_label') ?>"></div>
    </div>

    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Disposal method *</label>
        <select name="disposal_method" class="form-select">
          <?php foreach (['delete','anonymise','archive'] as $o): ?><option value="<?= $o ?>" <?= ($_POST['disposal_method'] ?? $category['disposal_method'])===$o?'selected':'' ?>><?= escape_html(get_disposal_method_label($o)) ?></option><?php endforeach; ?>
        </select></div>
      <div class="col-md-6 mb-3"><label class="form-label">Review frequency *</label>
        <select name="review_frequency" class="form-select">
          <?php foreach (['monthly','quarterly','annually'] as $o): ?><option <?= ($_POST['review_frequency'] ?? $category['review_frequency'])===$o?'selected':'' ?>><?= ucfirst($o) ?></option><?php endforeach; ?>
        </select></div>
    </div>

    <div class="mb-3"><label class="form-label">Data Owner</label>
      <select name="owner_id" class="form-select"><option value="">— none —</option>
        <?php foreach ($owners as $o): ?><option value="<?= (int)$o['id'] ?>" <?= ((int)($_POST['owner_id'] ?? $category['owner_id'])===(int)$o['id'])?'selected':'' ?>><?= escape_html($o['name']) ?></option><?php endforeach; ?>
      </select></div>
    
    <div class="form-check mb-4 border p-3 rounded onboarding-card">
      <input type="checkbox" class="form-check-input ms-0 me-2" id="dual" name="requires_dual_approval" value="1" <?= ($_POST['requires_dual_approval'] ?? $category['requires_dual_approval'])?'checked':'' ?>>
      <label class="form-check-label fw-semibold" for="dual">🔐 Classify as Sensitive Category (Dual-Signature Purging)</label>
      <div class="form-text small ms-0 mt-1">If enabled, system cron will NEVER delete overdue items automatically. Manual approval signatures from both the Data Owner and the DPO will be mandatory to proceed with disposal.</div>
    </div>
    
    <button class="btn btn-primary">Save changes</button>
    <a href="<?= APP_URL ?>/categories" class="btn btn-secondary ms-2">Cancel</a>
  </form>
</div></div>

<div class="card shadow-sm mt-4" style="max-width:820px"><div class="card-body">
  <h2 class="h5 mb-3 fw-bold text-dark">Retention rules</h2>
  <p class="text-muted small">A category can have multiple retention periods — e.g. by legal basis, processing purpose, or organisation type. The <strong>default</strong> rule is edited above; add variants below.</p>
  <?php if ($ruleMsg): ?><div class="alert alert-danger"><?= escape_html($ruleMsg) ?></div><?php endif; ?>
  <div class="table-responsive mb-4">
    <table class="table table-sm align-middle">
      <thead><tr>
        <th>Rule</th><th>Legal basis</th><th>Purpose / type</th><th>Retention</th><th>Dual</th><th></th>
      </tr></thead>
      <tbody>
      <?php foreach ($rules as $r): ?>
        <tr>
          <td><?= escape_html($r['rule_name']) ?><?= (int)$r['is_default'] ? ' <span class="badge bg-primary">Default</span>' : '' ?></td>
          <td><?= escape_html(get_legal_basis_label($r['legal_basis'])) ?></td>
          <td class="small">
            <?= escape_html($r['processing_purpose'] ?: '—') ?>
            <?php if ($r['institution_type'] !== 'all'): ?><br><span class="text-muted"><?= escape_html(institution_type_label($r['institution_type'])) ?></span><?php endif; ?>
          </td>
          <td><?= $r['disposal_trigger'] === 'consent_withdrawal' ? 'Until consent withdrawn' : escape_html($r['retention_period_label']) ?></td>
          <td><?= (int)$r['requires_dual_approval'] ? '🔐' : '—' ?></td>
          <td>
            <?php if (!(int)$r['is_default']): ?>
            <form method="post" class="d-inline" data-confirm="Remove this retention rule?">
              <?= csrf_field() ?>
              <input type="hidden" name="action" value="remove_rule">
              <input type="hidden" name="rule_id" value="<?= (int)$r['id'] ?>">
              <button class="btn btn-sm btn-outline-danger">Remove</button>
            </form>
            <?php endif; ?>
          </td>
        </tr>
      <?php endforeach; ?>
      </tbody>
    </table>
  </div>
  <h3 class="h6 fw-bold">Add retention rule variant</h3>
  <form method="post">
    <?= csrf_field() ?>
    <input type="hidden" name="action" value="add_rule">
    <div class="mb-3"><label class="form-label">Rule name *</label>
      <input name="rule_name" class="form-control" required placeholder="e.g. Marketing consent — retail"></div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Legal basis *</label>
        <select name="rule_legal_basis" class="form-select">
          <?php foreach (['legal_obligation','contract','consent','legitimate_interest','vital_interest','public_task'] as $o): ?>
            <option value="<?= $o ?>"><?= escape_html(get_legal_basis_label($o)) ?></option>
          <?php endforeach; ?>
        </select></div>
      <div class="col-md-6 mb-3"><label class="form-label">Organisation type</label>
        <select name="institution_type" class="form-select">
          <?php foreach (institution_type_options() as $k => $lbl): ?>
            <option value="<?= $k ?>"><?= escape_html($lbl) ?></option>
          <?php endforeach; ?>
        </select></div>
    </div>
    <div class="mb-3"><label class="form-label">Processing purpose</label>
      <input name="processing_purpose" class="form-control" placeholder="e.g. AML compliance, customer marketing"></div>
    <div class="mb-3"><label class="form-label">Disposal trigger *</label>
      <select name="rule_disposal_trigger" id="rule_trigger" class="form-select">
        <option value="date_based">📅 Date-based</option>
        <option value="consent_withdrawal">👤 Consent withdrawal</option>
      </select></div>
    <div id="ruleRetentionBlock" class="row">
      <div class="col-md-4 mb-3"><label class="form-label">Retention days</label>
        <input type="number" name="rule_retention_days" class="form-control" value="365"></div>
      <div class="col-md-8 mb-3"><label class="form-label">Retention label</label>
        <input name="rule_retention_label" class="form-control" placeholder="e.g. 7 years"></div>
    </div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Disposal method</label>
        <select name="rule_disposal_method" class="form-select">
          <?php foreach (['delete','anonymise','archive'] as $o): ?><option value="<?= $o ?>"><?= escape_html(get_disposal_method_label($o)) ?></option><?php endforeach; ?>
        </select></div>
    </div>
    <div class="form-check mb-3">
      <input type="checkbox" class="form-check-input" id="rule_dual" name="rule_requires_dual_approval" value="1">
      <label class="form-check-label" for="rule_dual">Require two-person approval for disposal</label>
    </div>
    <button class="btn btn-outline-primary">Add rule</button>
  </form>
</div></div>

<script nonce="<?= csp_nonce() ?>">
function toggleRetention(){
  var el = document.getElementById('retentionBlock');
  if (el) el.style.display = (document.getElementById('trigger').value==='consent_withdrawal')?'none':'flex';
}
function toggleRuleRetention(){
  var el=document.getElementById('ruleRetentionBlock');
  if(el) el.style.display=(document.getElementById('rule_trigger').value==='consent_withdrawal')?'none':'flex';
}
document.getElementById('trigger').addEventListener('change', toggleRetention);
document.getElementById('rule_trigger')?.addEventListener('change', toggleRuleRetention);
toggleRetention();
toggleRuleRetention();
</script>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
