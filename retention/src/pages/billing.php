<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/billing_lib.php';
require_once __DIR__ . '/../includes/stripe_lib.php';
require_once __DIR__ . '/../includes/geo_currency.php';
require_role('admin');

$pdo = get_db();
$orgId = require_org_id();
$org = fetch_organization($pdo, $orgId);
$ngnPlans = billing_plan_catalog($pdo);
$usdPlans = stripe_plan_catalog($pdo);
$error = null;
$tier = $org['tier'] ?? 'core';
$daysLeft = organization_trial_days_left($pdo, $orgId);
$hasAccess = organization_has_access($pdo, $orgId);
$view = geo_visitor_view($pdo);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $action = $_POST['action'] ?? '';
    if ($action === 'subscribe') {
        $tier = ($_POST['plan_tier'] ?? 'core') === 'enterprise' ? 'enterprise' : 'core';
        $gateway = ($_POST['gateway'] ?? 'paystack') === 'stripe' ? 'stripe' : 'paystack';
        try {
            if ($gateway === 'stripe') {
                $init = stripe_initialize($pdo, $orgId, $tier, current_user()['email']);
            } else {
                $init = paystack_initialize($pdo, $orgId, $tier, current_user()['email']);
            }
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
<?php if (!empty($_GET['stripe_cancelled'])): ?>
  <div class="alert alert-warning">Stripe checkout was cancelled. You can try again below.</div>
<?php endif; ?>
<?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>

<div class="card shadow-sm mb-3" style="max-width:720px"><div class="card-body">
  <p class="mb-1">Organisation: <strong><?= escape_html($org['name'] ?? '') ?></strong></p>
  <p class="mb-1">Status: <span class="badge bg-<?= $hasAccess ? 'success' : 'warning' ?>"><?= escape_html($org['subscription_status'] ?? 'trial') ?></span>
     · Tier: <span class="badge bg-secondary"><?= escape_html(strtoupper($org['tier'] ?? 'core')) ?></span></p>
  <?php if ($daysLeft !== null && ($org['subscription_status'] ?? '') === 'trial'): ?>
    <p class="text-muted small mb-0"><?= (int) $daysLeft ?> day(s) left in your free trial.</p>
  <?php endif; ?>
</div></div>

<?php if (!$hasAccess || ($org['subscription_status'] ?? '') !== 'active'): ?>

<div class="d-flex justify-content-between align-items-end mb-2" style="max-width:900px">
  <h2 class="h5 mb-0">Choose a plan</h2>
  <button type="button" class="btn btn-sm btn-outline-secondary"
          data-bs-toggle="modal" data-bs-target="#currencyModal">
    <i class="bi bi-globe2"></i>
    Showing prices for <?= escape_html($view['country'] ?: '—') ?> (<?= escape_html($view['currency']) ?>)
    · Change
  </button>
</div>

<div class="row g-3" style="max-width:900px">
  <?php foreach (['core', 'enterprise'] as $planKey):
      $usd = $usdPlans[$planKey];
      $ngn = $ngnPlans[$planKey];
      $primaryIsNgn = $view['is_nigeria'];
      $primaryAmount = $primaryIsNgn ? format_ngn_kobo($ngn['amount']) : format_usd_cents($usd['amount']);
      $secondaryAmount = $primaryIsNgn
          ? format_usd_cents($usd['amount'])
          : geo_local_estimate($pdo, $usd['amount'], $view['currency'], $view['currency'] === 'NGN' ? $ngn['amount'] : null);
      $secondaryLabel = $primaryIsNgn ? 'USD' : $view['currency'];
  ?>
  <div class="col-md-6">
    <div class="card h-100 shadow-sm">
      <div class="card-body d-flex flex-column">
        <h2 class="h5 mb-1"><?= escape_html($usd['name']) ?></h2>
        <p class="text-muted small mb-3"><?= escape_html($usd['label']) ?></p>

        <div class="price-block mb-3">
          <div class="display-6 fw-semibold lh-1"><?= $primaryAmount ?><span class="fs-6 text-muted ms-1">/ year</span></div>
          <?php if ($view['currency'] !== ($primaryIsNgn ? 'NGN' : 'USD')): ?>
            <div class="small text-muted mt-1">
              ≈ <?= $secondaryAmount ?> <?= escape_html($secondaryLabel) ?>
              <span class="text-muted">(converted at checkout by your card issuer)</span>
            </div>
          <?php else: ?>
            <div class="small text-muted mt-1">
              Also available: <?= $secondaryAmount ?> <?= escape_html($secondaryLabel) ?>
            </div>
          <?php endif; ?>
        </div>

        <div class="mt-auto d-grid gap-2">
          <?php if ($primaryIsNgn): ?>
            <form method="post"><?= csrf_field() ?>
              <input type="hidden" name="action" value="subscribe">
              <input type="hidden" name="plan_tier" value="<?= $planKey ?>">
              <input type="hidden" name="gateway" value="paystack">
              <button class="btn btn-primary w-100">
                <i class="bi bi-credit-card-2-front"></i> Pay <?= format_ngn_kobo($ngn['amount']) ?> with Paystack
              </button>
            </form>
            <form method="post"><?= csrf_field() ?>
              <input type="hidden" name="action" value="subscribe">
              <input type="hidden" name="plan_tier" value="<?= $planKey ?>">
              <input type="hidden" name="gateway" value="stripe">
              <button class="btn btn-outline-primary w-100">
                <i class="bi bi-globe"></i> Pay <?= format_usd_cents($usd['amount']) ?> with Stripe
              </button>
            </form>
          <?php else: ?>
            <form method="post"><?= csrf_field() ?>
              <input type="hidden" name="action" value="subscribe">
              <input type="hidden" name="plan_tier" value="<?= $planKey ?>">
              <input type="hidden" name="gateway" value="stripe">
              <button class="btn btn-primary w-100">
                <i class="bi bi-globe"></i> Pay <?= format_usd_cents($usd['amount']) ?> with Stripe
              </button>
            </form>
            <form method="post"><?= csrf_field() ?>
              <input type="hidden" name="action" value="subscribe">
              <input type="hidden" name="plan_tier" value="<?= $planKey ?>">
              <input type="hidden" name="gateway" value="paystack">
              <button class="btn btn-outline-primary w-100">
                <i class="bi bi-credit-card-2-front"></i> Pay <?= format_ngn_kobo($ngn['amount']) ?> with Paystack
              </button>
            </form>
          <?php endif; ?>
        </div>
      </div>
    </div>
  </div>
  <?php endforeach; ?>
</div>
<p class="text-muted small mt-3" style="max-width:900px">
  Nigerian customers typically pay with Paystack (direct NGN, no card-issuer FX fees).
  International customers pay with Stripe (USD; your bank converts to your local currency at the going rate).
  All processing is handled by the respective provider — card details never touch our servers.
</p>

<!-- Currency switcher modal -->
<div class="modal fade" id="currencyModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-sm">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">Show prices for</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <form method="get" class="d-grid gap-2">
          <?php
          $quick = [
            'NG' => 'Nigeria (₦ NGN)',
            'US' => 'United States ($ USD)',
            'GB' => 'United Kingdom (£ GBP)',
            'KE' => 'Kenya (KSh KES)',
            'GH' => 'Ghana (GH₵ GHS)',
            'ZA' => 'South Africa (R ZAR)',
            'CA' => 'Canada (C$ CAD)',
            'AU' => 'Australia (A$ AUD)',
          ];
          foreach ($quick as $cc => $label):
            $active = $view['country'] === $cc; ?>
            <button name="country" value="<?= $cc ?>"
                    class="btn btn-sm <?= $active ? 'btn-primary' : 'btn-outline-secondary' ?> text-start">
              <?= $active ? '<i class="bi bi-check2"></i> ' : '' ?><?= $label ?>
            </button>
          <?php endforeach; ?>
          <hr class="my-2">
          <label class="form-label small mb-1">Other country (2-letter ISO code)</label>
          <div class="input-group input-group-sm">
            <input name="country" class="form-control text-uppercase" maxlength="2" placeholder="e.g. FR">
            <button class="btn btn-outline-primary">Apply</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</div>

<div class="card shadow-sm mt-4" style="max-width:720px"><div class="card-body">
  <h2 class="h6">Have an Enterprise licence key?</h2>
  <form method="post" class="row g-2 align-items-end">
    <?= csrf_field() ?><input type="hidden" name="action" value="licence">
    <div class="col-md-8"><input name="licence_key" class="form-control" placeholder="ADRS-ENT-XXXX-XXXX"></div>
    <div class="col-md-4"><button class="btn btn-outline-success w-100">Activate licence</button></div>
  </form>
</div></div>

<?php else: ?>
<div class="alert alert-success" style="max-width:720px">Your subscription is active. Manage tier features under <a href="<?= APP_URL ?>/integrations/tier">Tier &amp; Licence</a>.</div>
<?php endif; ?>
<?php require __DIR__ . '/../includes/layout_footer.php'; ?>
