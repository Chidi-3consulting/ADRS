<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/tenant_lib.php';
require_once __DIR__ . '/../includes/public_layout.php';

$pdo = get_db();
if (is_logged_in()) { redirect(APP_URL . '/dashboard'); }
if (!is_saas_deployment($pdo)) { redirect(APP_URL . '/setup'); }

$tier = ($_GET['tier'] ?? $_POST['tier'] ?? 'core') === 'enterprise' ? 'enterprise' : 'core';
$error = null;

$form = [
    'org_name'       => trim($_POST['org_name'] ?? $_GET['org_name'] ?? ''),
    'primary_domain' => trim($_POST['primary_domain'] ?? $_GET['primary_domain'] ?? ''),
    'name'           => trim($_POST['name'] ?? $_GET['name'] ?? ''),
    'email'          => trim($_POST['email'] ?? $_GET['email'] ?? ''),
    'accept_terms'   => !empty($_POST['accept_terms']),
];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $tier = ($_POST['tier'] ?? 'core') === 'enterprise' ? 'enterprise' : 'core';
    $form['org_name']       = trim($_POST['org_name'] ?? '');
    $form['primary_domain'] = trim($_POST['primary_domain'] ?? '');
    $form['name']           = trim($_POST['name'] ?? '');
    $form['email']          = trim($_POST['email'] ?? '');
    $form['accept_terms']   = !empty($_POST['accept_terms']);

    $password2 = $_POST['password_confirm'] ?? '';
    $password = $_POST['password'] ?? '';
    if ($password !== $password2) {
        $error = 'Passwords do not match.';
    } elseif (!$form['accept_terms']) {
        $error = 'You must accept the Terms of Service and Privacy Policy.';
    } else {
        try {
            $result = register_organization(
                $pdo,
                $form['org_name'],
                $form['primary_domain'],
                $form['name'],
                $form['email'],
                $password,
                $tier
            );
            $stmt = $pdo->prepare('SELECT * FROM users WHERE id = :id LIMIT 1');
            $stmt->execute(['id' => $result['user_id']]);
            $user = $stmt->fetch();
            establish_session($pdo, $user);
            log_audit($pdo, 'user_created', 'system', $result['organization_id'], (int) $user['id'], ['registration' => true, 'tier' => $tier], get_client_ip());
            if (is_local_environment()) {
                flash('success', 'Welcome to ADRS! Your local trial is ready.');
                redirect(APP_URL . '/dashboard');
            }
            require_once __DIR__ . '/../includes/mailer.php';
            $vtoken = issue_email_verification_token($pdo, (int) $user['id']);
            $vlink = APP_URL . '/verify_email?token=' . urlencode($vtoken);
            [$vsubj, $vhtml] = email_verification($user['name'], $vlink);
            send_platform_email($pdo, $user['email'], $vsubj, $vhtml);
            flash('success', 'Welcome to ADRS! Check your email to verify your account, then start your trial.');
            redirect(APP_URL . '/verify_email');
        } catch (InvalidArgumentException $e) {
            $error = $e->getMessage();
        } catch (Throwable $e) {
            $error = 'Registration failed. Please try again or contact support.';
        }
    }
}

$tierLabel = $tier === 'enterprise' ? 'ADRS Enterprise' : 'ADRS Core';
public_page_head('Start your free trial', $pdo);
public_page_nav($pdo);
?>
<main class="flex-grow-1 py-5">
  <div class="container" style="max-width:640px;">
    <div class="card shadow-sm">
      <div class="card-header card-header-orange text-center">
        <h1 class="h4 mb-0">Start your free trial</h1>
        <p class="small mb-0 opacity-90"><?= escape_html($tierLabel) ?> · 14 days · no credit card</p>
      </div>
      <div class="card-body">
        <p class="text-muted small">
          Register your organisation's compliance portal — one company, one account. You become the administrator and can invite your DPO and data owners after sign-up.
        </p>
        <?php if ($error): ?><div class="alert alert-danger"><?= escape_html($error) ?></div><?php endif; ?>
        <form method="post" novalidate id="register-form">
          <?= csrf_field() ?>
          <input type="hidden" name="tier" id="tier-field" value="<?= escape_html($tier) ?>">
          <div class="mb-3">
            <label class="form-label">Organisation name *</label>
            <input name="org_name" class="form-control" required autofocus
                   placeholder="e.g. Acme Bank Ltd"
                   value="<?= escape_html($form['org_name']) ?>">
          </div>
          <div class="mb-3">
            <label class="form-label">Company domain *</label>
            <input name="primary_domain" class="form-control" required
                   placeholder="e.g. acmebank.com"
                   value="<?= escape_html($form['primary_domain']) ?>"
                   pattern="[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+"
                   title="Enter your company domain only — not www or a full URL">
            <div class="form-text">Your company's website domain (not <code>www</code>). Each domain can register once.</div>
          </div>
          <div class="mb-3">
            <label class="form-label">Your full name *</label>
            <input name="name" class="form-control" required value="<?= escape_html($form['name']) ?>">
          </div>
          <div class="mb-3">
            <label class="form-label">Work email *</label>
            <input type="email" name="email" class="form-control" required value="<?= escape_html($form['email']) ?>"
                   aria-describedby="email-domain-hint">
            <div class="form-text" id="email-domain-hint">Must match your company domain above (e.g. you@acmebank.com).</div>
          </div>
          <div class="mb-3">
            <label class="form-label">Password *</label>
            <input type="password" name="password" class="form-control" required minlength="10">
            <div class="form-text">At least 10 characters, including letters and numbers.</div>
          </div>
          <div class="mb-3">
            <label class="form-label">Confirm password *</label>
            <input type="password" name="password_confirm" class="form-control" required minlength="10">
          </div>
          <div class="mb-3">
            <label class="form-label d-block">Plan</label>
            <div class="btn-group" role="group" aria-label="Choose plan">
              <input type="radio" class="btn-check" name="tier_choice" id="tier-core" value="core" <?= $tier === 'core' ? 'checked' : '' ?>>
              <label class="btn btn-sm <?= $tier === 'core' ? 'btn-primary' : 'btn-outline-secondary' ?>" for="tier-core">Core</label>
              <input type="radio" class="btn-check" name="tier_choice" id="tier-enterprise" value="enterprise" <?= $tier === 'enterprise' ? 'checked' : '' ?>>
              <label class="btn btn-sm <?= $tier === 'enterprise' ? 'btn-primary' : 'btn-outline-secondary' ?>" for="tier-enterprise">Enterprise</label>
            </div>
            <div class="form-text mt-2" id="tier-hint">
              <?php if ($tier === 'enterprise'): ?>
                Enterprise includes API integration, automatic data capture, and outbound disposal dispatch.
              <?php else: ?>
                Core is the standalone compliance portal — register records manually; the engine automates everything after that.
              <?php endif; ?>
            </div>
          </div>
          <div class="form-check mb-3">
            <input class="form-check-input" type="checkbox" name="accept_terms" id="accept_terms" value="1" required
              <?= $form['accept_terms'] ? 'checked' : '' ?>>
            <label class="form-check-label small" for="accept_terms">
              I agree to the <a href="<?= APP_URL ?>/legal?page=terms" target="_blank">Terms of Service</a>,
              <a href="<?= APP_URL ?>/legal?page=privacy" target="_blank">Privacy Policy</a>, and
              <a href="<?= APP_URL ?>/legal?page=dpa" target="_blank">DPA summary</a>.
            </label>
          </div>
          <button class="btn btn-primary w-100 btn-lg">Create my organisation</button>
        </form>
        <p class="mt-3 mb-0 small text-center">
          Already have an account? <a href="<?= APP_URL ?>/login">Sign in</a>
        </p>
      </div>
    </div>
  </div>
</main>
<script nonce="<?= csp_nonce() ?>">
(function () {
  var tierField = document.getElementById('tier-field');
  var hint = document.getElementById('tier-hint');
  var hints = {
    core: 'Core is the standalone compliance portal — register records manually; the engine automates everything after that.',
    enterprise: 'Enterprise includes API integration, automatic data capture, and outbound disposal dispatch.'
  };
  document.querySelectorAll('input[name="tier_choice"]').forEach(function (el) {
    el.addEventListener('change', function () {
      tierField.value = el.value;
      hint.textContent = hints[el.value] || '';
    });
  });
})();
</script>
<?php public_page_foot(); ?>
