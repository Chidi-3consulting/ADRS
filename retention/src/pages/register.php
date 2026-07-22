<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/tenant_lib.php';
require_once __DIR__ . '/../includes/public_layout.php';

$pdo = get_db();
if (is_logged_in()) { redirect(APP_URL . '/dashboard'); }

$tier = 'enterprise';
$error = null;

$form = [
    'org_name'       => trim($_POST['org_name'] ?? $_GET['org_name'] ?? ''),
    'primary_domain' => trim($_POST['primary_domain'] ?? $_GET['primary_domain'] ?? ''),
    'country'        => trim($_POST['country'] ?? $_GET['country'] ?? ''),
    'name'           => trim($_POST['name'] ?? $_GET['name'] ?? ''),
    'email'          => trim($_POST['email'] ?? $_GET['email'] ?? ''),
    'accept_terms'   => !empty($_POST['accept_terms']),
];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $tier = 'enterprise';
    $form['org_name']       = trim($_POST['org_name'] ?? '');
    $form['primary_domain'] = trim($_POST['primary_domain'] ?? '');
    $form['country']        = trim($_POST['country'] ?? '');
    $form['name']           = trim($_POST['name'] ?? '');
    $form['email']          = trim($_POST['email'] ?? '');
    $form['accept_terms']   = !empty($_POST['accept_terms']);

    $password2 = $_POST['password_confirm'] ?? '';
    $password = $_POST['password'] ?? '';
    
    if ($form['country'] === '') {
        $error = 'Please select your operating country.';
    } elseif ($password !== $password2) {
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
                $tier,
                $form['country']
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

$tierLabel = 'ADRS Platform';
public_page_head('Start your free trial', $pdo);
public_page_nav($pdo);
?>
<main class="flex-grow-1 py-5">
  <div class="container" style="max-width:640px;">
    <div class="card shadow-sm border-0">
      <div class="card-header card-header-orange text-center py-4 rounded-top" style="border-bottom:0px;">
        <h1 class="h4 mb-1 fw-bold text-white">Start your free trial</h1>
        <p class="small mb-0 opacity-90"><?= escape_html($tierLabel) ?> · 14 days · no credit card</p>
      </div>
      <div class="card-body p-4">
        <p class="text-muted small">
          Register your organisation's compliance portal: one company, one account. You become the administrator and can invite your DPO and data owners after sign-up.
        </p>
        <?php if ($error): ?><div class="alert alert-danger mb-4"><?= escape_html($error) ?></div><?php endif; ?>
        
        <form method="post" novalidate id="register-form">
          <?= csrf_field() ?>
          <input type="hidden" name="tier" id="tier-field" value="<?= escape_html($tier) ?>">
          
          <div class="mb-3">
            <label class="form-label fw-medium">Organisation name *</label>
            <input name="org_name" class="form-control" required autofocus
                   placeholder="e.g. Acme Bank Ltd"
                   value="<?= escape_html($form['org_name']) ?>">
          </div>
          
          <div class="row">
            <div class="col-md-6 mb-3">
              <label class="form-label fw-medium">Company domain *</label>
              <input name="primary_domain" id="domain-input" class="form-control" required
                     placeholder="e.g. acmebank.com"
                     value="<?= escape_html($form['primary_domain']) ?>"
                     pattern="[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+"
                     title="Enter your company domain only — not www or a full URL">
            </div>
            
            <div class="col-md-6 mb-3">
              <label class="form-label fw-medium">Operating Country *</label>
              <select name="country" class="form-select text-dark" required>
                <option value="">— select your country —</option>
                <optgroup label="Popular Countries">
                  <?php 
                  $popular = ['NG', 'GB', 'US', 'EU', 'CA', 'AU', 'IN', 'AE', 'ZA', 'KE', 'GH', 'SG', 'BR', 'EG'];
                  foreach ($popular as $code) {
                      if (isset(ADRS_SUPPORTED_COUNTRIES[$code])) {
                          $sel = $form['country'] === $code ? 'selected' : '';
                          echo '<option value="' . $code . '" ' . $sel . '>' . escape_html(ADRS_SUPPORTED_COUNTRIES[$code]) . '</option>';
                      }
                  }
                  ?>
                </optgroup>
                <optgroup label="All Countries">
                  <?php 
                  foreach (ADRS_SUPPORTED_COUNTRIES as $code => $name) {
                      if (in_array($code, $popular, true)) continue;
                      $sel = $form['country'] === $code ? 'selected' : '';
                      echo '<option value="' . $code . '" ' . $sel . '>' . escape_html($name) . '</option>';
                  }
                  ?>
                </optgroup>
              </select>
            </div>
          </div>
          
          <div class="row">
            <div class="col-md-6 mb-3">
              <label class="form-label fw-medium">Your full name *</label>
              <input name="name" class="form-control" required value="<?= escape_html($form['name']) ?>" placeholder="e.g. John Doe">
            </div>
            <div class="col-md-6 mb-3">
              <label class="form-label fw-medium">Work email *</label>
              <input type="email" name="email" id="email-input" class="form-control" required value="<?= escape_html($form['email']) ?>"
                     placeholder="e.g. jdoe@acmebank.com">
            </div>
          </div>
          
          <div class="row">
            <div class="col-md-6 mb-3">
              <label class="form-label fw-medium">Password *</label>
              <input type="password" name="password" class="form-control" required minlength="10">
            </div>
            <div class="col-md-6 mb-3">
              <label class="form-label fw-medium">Confirm password *</label>
              <input type="password" name="password_confirm" class="form-control" required minlength="10">
            </div>
          </div>

          
          <div class="form-check mb-4">
            <input class="form-check-input" type="checkbox" name="accept_terms" id="accept_terms" value="1" required
              <?= $form['accept_terms'] ? 'checked' : '' ?>>
            <label class="form-check-label small text-muted" for="accept_terms">
              I agree to the <a href="<?= APP_URL ?>/legal?page=terms" target="_blank" class="text-decoration-none">Terms of Service</a>,
              <a href="<?= APP_URL ?>/legal?page=privacy" target="_blank" class="text-decoration-none">Privacy Policy</a>, and
              <a href="<?= APP_URL ?>/legal?page=dpa" target="_blank" class="text-decoration-none">DPA summary</a>.
            </label>
          </div>
          
          <button class="btn btn-primary w-100 btn-lg shadow-sm hover-lift">Create my organisation</button>
        </form>
        
        <p class="mt-4 mb-0 small text-center text-muted">
          Already have an account? <a href="<?= APP_URL ?>/login" class="text-decoration-none fw-semibold">Sign in</a>
        </p>
      </div>
    </div>
  </div>
</main>

<script nonce="<?= csp_nonce() ?>">
(function () {
  var domainInput = document.getElementById('domain-input');
  var emailInput = document.getElementById('email-input');
  
  // Auto-fill email domain hint as user types domain
  if (domainInput && emailInput) {
      domainInput.addEventListener('input', function() {
          var val = domainInput.value.trim().toLowerCase();
          if (val && !emailInput.value) {
              emailInput.placeholder = 'e.g. admin@' + val;
          }
      });
  }
})();
</script>
<?php public_page_foot(); ?>
