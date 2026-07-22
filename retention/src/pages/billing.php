<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/billing_lib.php';
require_role('admin');

$pdo = get_db();
$orgId = require_org_id();
$org = fetch_organization($pdo, $orgId);
$plans = billing_plan_catalog($pdo);
$error = null;
$tier = $org['tier'] ?? 'core';
$daysLeft = organization_trial_days_left($pdo, $orgId);
$hasAccess = organization_has_access($pdo, $orgId);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $action = $_POST['action'] ?? '';
    if ($action === 'subscribe') {
        $selectedTier = $_POST['plan_tier'] ?? 'yearly';
        try {
            $init = paystack_initialize($pdo, $orgId, $selectedTier, current_user()['email']);
            redirect($init['authorization_url']);
        } catch (Throwable $e) {
            $error = $e->getMessage();
        }
    } elseif ($action === 'licence') {
        $key = trim($_POST['licence_key'] ?? '');
        if ($key === '') {
            $error = 'Enter your Enterprise licence key.';
        } elseif (!redeem_enterprise_licence($pdo, $key, $orgId)) {
            $error = 'Invalid or already-used licence key.';
        } else {
            flash('success', 'Enterprise licence activated.');
            redirect(APP_URL . '/integrations/tier');
        }
    }
}

$page_title = 'Billing & subscription';
$active_nav = 'settings';
require __DIR__ . '/../includes/layout_header.php';
?>
<h1 class="h4 mb-3">Billing &amp; subscription</h1>
<?php if (!empty($_GET['suspended'])): ?>
  <div class="alert alert-danger">This organisation is suspended. Contact <?= escape_html(get_setting($pdo, 'platform_support_email', 'support')) ?>.</div>
<?php endif; ?>
<?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>

<div class="card shadow-sm mb-3" style="max-width:720px"><div class="card-body">
  <p>Organisation: <strong><?= escape_html($org['name'] ?? '') ?></strong></p>
  <p>Status: <span class="badge bg-<?= $hasAccess ? 'success' : 'warning' ?>"><?= escape_html($org['subscription_status'] ?? 'trial') ?></span></p>
  <?php if ($daysLeft !== null && ($org['subscription_status'] ?? '') === 'trial'): ?>
    <p class="text-muted small"><?= (int) $daysLeft ?> day(s) left in your free trial.</p>
  <?php endif; ?>
</div></div>

<?php if (!$hasAccess || ($org['subscription_status'] ?? '') !== 'active'): ?>
<div class="row g-3" style="max-width:900px">
  <?php foreach (array_keys($plans) as $planKey): $p = $plans[$planKey]; ?>
  <div class="col-md-6">
    <div class="card h-100 shadow-sm">
      <div class="card-body d-flex flex-column justify-content-between">
        <div>
          <h2 class="h5 fw-bold text-dark"><?= escape_html($p['name']) ?></h2>
          <p class="display-6 fw-bold text-primary mb-1"><?= format_detected_price($pdo, $p['amount'], $orgId) ?></p>
          <span class="fs-6 text-muted d-block mb-3">/ <?= escape_html($p['interval']) ?></span>
          <p class="text-muted small"><?= escape_html($p['label']) ?></p>
        </div>
        <form method="post" class="mt-3"><?= csrf_field() ?>
          <input type="hidden" name="action" value="subscribe">
          <input type="hidden" name="plan_tier" value="<?= $planKey ?>">
          <button class="btn btn-primary w-100">Pay with Paystack</button>
        </form>
      </div>
    </div>
  </div>
  <?php endforeach; ?>
</div>
<p class="text-muted small mt-3">Payments are processed securely by Paystack. Configure <code>paystack_secret_key</code> in platform settings for live billing.</p>

<div class="card shadow-sm mt-4" style="max-width:720px"><div class="card-body">
  <h2 class="h6">Have a product licence key?</h2>
  <form method="post" class="row g-2 align-items-end">
    <?= csrf_field() ?><input type="hidden" name="action" value="licence">
    <div class="col-md-8"><input name="licence_key" class="form-control" placeholder="ADRS-LIC-XXXX-XXXX"></div>
    <div class="col-md-4"><button class="btn btn-outline-success w-100">Activate licence</button></div>
  </form>
</div></div>
<?php else: ?>
<div class="alert alert-success" style="max-width:720px">Your subscription is active. Manage tier features under <a href="<?= APP_URL ?>/integrations/tier">Tier &amp; Licence</a>.</div>
<?php endif; ?>
<?php require __DIR__ . '/../includes/layout_footer.php'; ?>
