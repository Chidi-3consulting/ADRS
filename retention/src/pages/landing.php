<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/tenant_lib.php';
require_once __DIR__ . '/../includes/public_layout.php';

if (is_logged_in()) { redirect(APP_URL . '/dashboard'); }
if (!setup_is_complete(get_db())) { redirect(APP_URL . '/setup'); }

$pdo = get_db();
$saas = is_saas_deployment($pdo);
public_page_head('Automated Data Retention System', $pdo);
public_page_nav($pdo);
?>
<main class="flex-grow-1">
  <section class="text-white py-5" style="background:linear-gradient(135deg,var(--3c-dark) 0%,var(--3c-teal) 100%); background-size:cover; min-height:600px;">
    <div class="container py-4">
      <div class="row align-items-center">
        <div class="col-lg-7">
          <p class="text-uppercase small fw-semibold mb-2" style="color:var(--3c-yellow)">3Consulting · GDPR &amp; NDPR</p>
          <h1 class="display-5 fw-bold mb-3">Turn compliance from a burden into a competitive advantage</h1>
          <p class="lead mb-4 opacity-90">
            ADRS governs personal data from the moment it is collected to the day it is securely disposed of —
            with a documented retention register, an automated enforcement engine, immutable audit evidence,
            and data-subject-rights workflows built for regulator scrutiny.
          </p>
          <?php if ($saas): ?>
            <div class="d-flex flex-wrap gap-3">
              <a href="<?= APP_URL ?>/register?tier=core" class="btn btn-light btn-lg text-dark px-4">Start free trial — Core</a>
              <a href="<?= APP_URL ?>/register?tier=enterprise" class="btn btn-outline-light btn-lg px-4">Start free trial — Enterprise</a>
            </div>
          <?php elseif (public_signup_enabled($pdo)): ?>
            <a href="<?= APP_URL ?>/signup" class="btn btn-primary btn-lg">Create an account</a>
          <?php else: ?>
            <a href="<?= APP_URL ?>/login" class="btn btn-primary btn-lg">Sign in to your portal</a>
          <?php endif; ?>
        </div>
        <div class="col-lg-5 mt-4 mt-lg-0">
          <div class="card shadow border-0">
            <div class="card-body p-4">
              <h2 class="h5">Five-stage governed lifecycle</h2>
              <ol class="small mb-0 ps-3">
                <li class="mb-1">Collection &amp; registration</li>
                <li class="mb-1">Active use monitoring</li>
                <li class="mb-1">Retention alerts (30-day warning)</li>
                <li class="mb-1">Review &amp; decision (14-day escalation)</li>
                <li>Secure disposal with full audit trail</li>
              </ol>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="py-5 bg-white">
    <div class="container">
      <h2 class="h3 text-center mb-4">One product. Two tiers. No dead ends.</h2>
      <div class="row g-4">
        <div class="col-lg-6">
          <div class="card h-100 border-primary shadow-sm">
            <div class="card-header card-header-teal"><h3 class="h5 mb-0">ADRS Core</h3><span class="small">Entry-level deployment</span></div>
            <div class="card-body">
              <p class="text-muted small">Standalone compliance portal. Your team registers records; the engine automates alerts, escalations, deadlines, and disposal workflows.</p>
              <ul class="small">
                <li>30 pre-built GDPR/NDPR categories</li>
                <li>Automated retention engine &amp; dual-approval safeguard</li>
                <li>Immutable audit trail · NDPR annual report</li>
                <li>Role-based access (Admin / DPO / Data Owner)</li>
                <li>Deploy without changing existing systems</li>
              </ul>
              <?php if ($saas): ?>
                <a href="<?= APP_URL ?>/register?tier=core" class="btn btn-primary">Start Core trial</a>
              <?php endif; ?>
            </div>
          </div>
        </div>
        <div class="col-lg-6">
          <div class="card h-100 border-success shadow-sm">
            <div class="card-header" style="background:#1E7D34;color:#fff"><h3 class="h5 mb-0">ADRS Enterprise</h3><span class="small">Integration tier</span></div>
            <div class="card-body">
              <p class="text-muted small">Everything in Core, plus API integration with your CRM, core banking, HR, and customer databases — automatic capture at the point data is created.</p>
              <ul class="small">
                <li>REST API · async intake queue · auto-categorisation</li>
                <li>Consent-signal matching &amp; outbound disposal dispatch</li>
                <li>Real-time retention enforcement across connected systems</li>
                <li>Integration management UI &amp; enterprise SLA support</li>
              </ul>
              <?php if ($saas): ?>
                <a href="<?= APP_URL ?>/register?tier=enterprise" class="btn btn-success">Start Enterprise trial</a>
              <?php endif; ?>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="py-5">
    <div class="container">
      <h2 class="h4 text-center mb-4">Built for organisations that cannot afford data slipping through</h2>
      <div class="row g-4">
        <?php
        $sectors = [
            ['Financial services', 'KYC, transactions, and customer records — CBN-aligned retention for banks and fintechs.'],
            ['Professional services', 'Governed client and employee data across engagements without disrupting workflows.'],
            ['Healthcare', 'Patient and staff categories with dual-approval safeguards for sensitive disposals.'],
            ['Technology &amp; digital', 'High-volume cross-border obligations with Enterprise API capture at scale.'],
        ];
        foreach ($sectors as [$title, $desc]): ?>
        <div class="col-md-6 col-lg-3">
          <div class="card h-100 shadow-sm border-0">
            <div class="card-body">
              <h3 class="h6"><?= $title ?></h3>
              <p class="text-muted small mb-0"><?= $desc ?></p>
            </div>
          </div>
        </div>
        <?php endforeach; ?>
      </div>
    </div>
  </section>

  <section class="py-5 bg-white">
    <div class="container text-center">
      <h2 class="h4 mb-3">Ready to go from zero governance to audit-ready?</h2>
      <p class="text-muted mb-4">Core organisations are typically operational in 4–6 weeks. Enterprise integrations in 10–14 weeks with guided onboarding.</p>
      <?php if ($saas): ?>
        <a href="<?= APP_URL ?>/register?tier=core" class="btn btn-primary btn-lg me-2">Create your organisation</a>
        <a href="<?= APP_URL ?>/login" class="btn btn-outline-secondary btn-lg">Sign in</a>
      <?php else: ?>
        <a href="<?= APP_URL ?>/login" class="btn btn-primary btn-lg">Sign in</a>
      <?php endif; ?>
    </div>
  </section>
</main>
<?php public_page_foot(); ?>
