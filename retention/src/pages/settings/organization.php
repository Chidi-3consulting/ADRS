<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/billing_lib.php';
require_role('admin');
$pdo = get_db();
$orgId = require_org_id();
$org = fetch_organization($pdo, $orgId);
if (!$org) { http_response_code(404); exit('Organisation not found.'); }

$error = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $name = trim($_POST['name'] ?? '');
    $billingEmail = strtolower(trim($_POST['billing_email'] ?? ''));
    $timezone = trim($_POST['timezone'] ?? 'Africa/Lagos');

    if ($name === '') {
        $error = 'Organisation name is required.';
    } elseif (!filter_var($billingEmail, FILTER_VALIDATE_EMAIL)) {
        $error = 'A valid billing email is required.';
    } elseif (($memberErr = org_member_email_error($pdo, $billingEmail, $orgId)) !== null) {
        $error = $memberErr;
    } else {
        $pdo->prepare('UPDATE organizations SET name = :n, billing_email = :b WHERE id = :id')
            ->execute(['n' => $name, 'b' => $billingEmail, 'id' => $orgId]);
        set_setting($pdo, 'white_label_name', $name, $orgId);
        set_setting($pdo, 'app_name', $name, $orgId);
        set_setting($pdo, 'timezone', $timezone, $orgId);
        log_audit($pdo, 'organisation_updated', 'organization', $orgId, (int) current_user()['id'], [
            'name' => $name, 'billing_email' => $billingEmail,
        ], get_client_ip());
        flash('success', 'Organisation profile saved.');
        redirect(APP_URL . '/settings/organization');
    }
}

$trialDays = organization_trial_days_left($pdo, $orgId);
$page_title = 'Organisation profile';
$active_nav = 'settings';
require __DIR__ . '/../../includes/layout_header.php';
require __DIR__ . '/_nav.php';
echo settings_nav('organization');
?>
<div class="row g-4">
  <div class="col-lg-7">
    <div class="card shadow-sm">
      <div class="card-header bg-white fw-semibold">Your organisation</div>
      <div class="card-body">
        <p class="text-muted small mb-4">
          Each company has one ADRS tenant. Your registered domain is fixed at sign-up and defines which work emails may join your team.
        </p>
        <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
        <form method="post">
          <?= csrf_field() ?>
          <div class="mb-3">
            <label class="form-label">Organisation name *</label>
            <input name="name" class="form-control" required value="<?= escape_html($org['name']) ?>">
          </div>
          <div class="mb-3">
            <label class="form-label">Registered domain</label>
            <input class="form-control" value="<?= escape_html($org['primary_domain']) ?>" disabled>
            <div class="form-text">Team members must use <strong>@<?= escape_html($org['primary_domain']) ?></strong> work emails. Contact support to change this.</div>
          </div>
          <div class="mb-3">
            <label class="form-label">Billing contact email *</label>
            <input type="email" name="billing_email" class="form-control" required
                   value="<?= escape_html($org['billing_email'] ?? current_user()['email'] ?? '') ?>">
          </div>
          <div class="mb-3">
            <label class="form-label">Timezone</label>
            <input name="timezone" class="form-control" value="<?= escape_html(get_setting($pdo, 'timezone', 'Africa/Lagos', $orgId)) ?>"
                   placeholder="Africa/Lagos">
          </div>
          <button class="btn btn-primary">Save profile</button>
        </form>
      </div>
    </div>
  </div>
  <div class="col-lg-5">
    <div class="card shadow-sm mb-3">
      <div class="card-body">
        <h2 class="h6 text-muted mb-3">Subscription</h2>
        <p class="mb-2">Plan: <span class="badge bg-<?= $org['tier'] === 'enterprise' ? 'success' : 'secondary' ?>"><?= escape_html(org_tier_label($org['tier'])) ?></span></p>
        <p class="mb-2">Status: <?= org_status_badge($org) ?></p>
        <?php if ($trialDays !== null): ?>
          <p class="mb-0 small text-muted">Trial: <?= (int) $trialDays ?> day<?= $trialDays === 1 ? '' : 's' ?> remaining</p>
        <?php endif; ?>
        <a href="<?= APP_URL ?>/billing" class="btn btn-outline-primary btn-sm mt-3">Manage billing</a>
        <a href="<?= APP_URL ?>/integrations/tier" class="btn btn-outline-secondary btn-sm mt-3 ms-1">Tier &amp; licence</a>
      </div>
    </div>
    <div class="card shadow-sm">
      <div class="card-body small text-muted">
        <strong>Tenant ID:</strong> <?= (int) $org['id'] ?><br>
        <strong>Slug:</strong> <?= escape_html($org['slug']) ?><br>
        <strong>Registered:</strong> <?= escape_html(format_datetime($org['created_at'] ?? null)) ?>
      </div>
    </div>
  </div>
</div>
<?php require __DIR__ . '/../../includes/layout_footer.php'; ?>
