<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/tenant_lib.php';
require_once __DIR__ . '/../includes/public_layout.php';

if (is_logged_in()) { redirect(APP_URL . '/dashboard'); }

$pdo = get_db();
$saas = is_saas_deployment($pdo);
public_page_head('Automated Data Retention System', $pdo);
public_page_nav($pdo);
?>
<main class="flex-grow-1">
  <!-- Hero Section -->
  <section class="text-white py-5 position-relative overflow-hidden" style="background: radial-gradient(circle at 80% 20%, #2e1065 0%, #0f0f1b 100%); min-height: 640px; display: flex; align-items: center;">
    <div class="position-absolute w-100 h-100 top-0 start-0 opacity-10" style="background-image: radial-gradient(rgba(200, 92, 26, 0.15) 1px, transparent 0); background-size: 24px 24px;"></div>
    <div class="container py-5 position-relative z-3">
      <div class="row align-items-center g-5">
        <div class="col-lg-7">
          <div class="badge bg-primary text-white mb-3 px-3 py-2 rounded-pill font-monospace small">COMPLIANCE LIFECYCLE MANAGEMENT</div>
          <h1 class="display-4 fw-extrabold mb-3 lh-sm" style="letter-spacing: -0.03em;">
            Turn data retention from a <span style="background: linear-gradient(to right, #ff7e33, #e8a84c); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">compliance burden</span> into a trusted asset
          </h1>
          <p class="lead mb-4 opacity-90 fs-5" style="max-width: 620px; line-height: 1.6;">
            ADRS automates the lifecycle of personal data from capture to disposal. Build immutable audit proof, fulfill DSAR requests, and manage complex retention schedules without changing your existing databases.
          </p>
          <div class="d-flex flex-wrap gap-3">
            <a href="<?= APP_URL ?>/register?tier=core" class="btn btn-primary btn-lg px-4 shadow-lg hover-lift">Start Trial — Core</a>
            <a href="<?= APP_URL ?>/register?tier=enterprise" class="btn btn-teal btn-lg px-4 shadow-lg hover-lift">Start Trial — Enterprise</a>
          </div>
          <div class="mt-4 pt-2 d-flex align-items-center gap-4 text-muted small">
            <span class="d-flex align-items-center gap-2"><i class="bi bi-shield-check text-success fs-5"></i> GDPR & NDPR Ready</span>
            <span class="d-flex align-items-center gap-2"><i class="bi bi-lock text-success fs-5"></i> Tamper-Proof Audit Chain</span>
          </div>
        </div>
        <div class="col-lg-5">
          <div class="card shadow-lg border-0 bg-dark text-white p-4 position-relative" style="background: rgba(20, 20, 38, 0.6) !important; backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08) !important;">
            <div class="position-absolute top-0 end-0 p-3"><span class="badge bg-success">Automated Cron</span></div>
            <h3 class="h5 mb-4 text-primary">5-Stage Retention Lifecycle</h3>
            
            <div class="position-relative ps-4 border-start border-secondary" style="margin-left: 10px;">
              <div class="mb-4 position-relative">
                <div class="position-absolute rounded-circle bg-primary" style="width: 12px; height: 12px; left: -31px; top: 6px;"></div>
                <h4 class="h6 mb-1 text-white">1. Capture &amp; Ingest</h4>
                <p class="text-muted small mb-0">API intake or CSV upload maps data objects to predefined policies.</p>
              </div>
              <div class="mb-4 position-relative">
                <div class="position-absolute rounded-circle bg-primary" style="width: 12px; height: 12px; left: -31px; top: 6px;"></div>
                <h4 class="h6 mb-1 text-white">2. Monitor Retention Clock</h4>
                <p class="text-muted small mb-0">Records automatically follow duration policies down to the day.</p>
              </div>
              <div class="mb-4 position-relative">
                <div class="position-absolute rounded-circle bg-warning" style="width: 12px; height: 12px; left: -31px; top: 6px;"></div>
                <h4 class="h6 mb-1 text-white">3. Review Window (30 Days)</h4>
                <p class="text-muted small mb-0">Category owners get notified. DPOs can override or request extensions.</p>
              </div>
              <div class="mb-4 position-relative">
                <div class="position-absolute rounded-circle bg-danger" style="width: 12px; height: 12px; left: -31px; top: 6px;"></div>
                <h4 class="h6 mb-1 text-white">4. Dual Approval &amp; Hold</h4>
                <p class="text-muted small mb-0">Sensitive data categories lock automatically. Requires dual signature to dispose.</p>
              </div>
              <div class="position-relative">
                <div class="position-absolute rounded-circle bg-success" style="width: 12px; height: 12px; left: -31px; top: 6px;"></div>
                <h4 class="h6 mb-1 text-white">5. Secure Cryptographic Disposal</h4>
                <p class="text-muted small mb-0">Hard delete, anonymisation, or archival with immutable hash logging.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Feature Grid -->
  <section class="py-5 bg-white">
    <div class="container py-4">
      <div class="text-center mb-5">
        <h2 class="h3 fw-bold">Built for compliance, optimized for security</h2>
        <p class="text-muted">A pure PHP platform designed to satisfy regulators and IT teams alike.</p>
      </div>
      <div class="row g-4">
        <div class="col-md-6 col-lg-4">
          <div class="card h-100 hover-lift border-0 bg-light p-4">
            <div class="text-primary mb-3"><i class="bi bi-journal-check fs-3"></i></div>
            <h3 class="h5">Retention Policy Register</h3>
            <p class="text-muted small mb-0">Establish lawful bases, retention periods, and record owners across 30+ pre-seeded compliance categories.</p>
          </div>
        </div>
        <div class="col-md-6 col-lg-4">
          <div class="card h-100 hover-lift border-0 bg-light p-4">
            <div class="text-primary mb-3"><i class="bi bi-shield-lock-fill fs-3"></i></div>
            <h3 class="h5">Immutable Audit Trails</h3>
            <p class="text-muted small mb-0">Every disposal is signed, chained cryptographically, and tamper-evident to withstand external regulator audits.</p>
          </div>
        </div>
        <div class="col-md-6 col-lg-4">
          <div class="card h-100 hover-lift border-0 bg-light p-4">
            <div class="text-primary mb-3"><i class="bi bi-people-fill fs-3"></i></div>
            <h3 class="h5">DSAR Management Portal</h3>
            <p class="text-muted small mb-0">Receive, verify, and resolve data subject rights requests (erasure, access, portability) within statutory deadlines.</p>
          </div>
        </div>
        <div class="col-md-6 col-lg-4">
          <div class="card h-100 hover-lift border-0 bg-light p-4">
            <div class="text-primary mb-3"><i class="bi bi-cpu fs-3"></i></div>
            <h3 class="h5">REST Integration API</h3>
            <p class="text-muted small mb-0">Enterprise systems ingest data dynamically. Automate categorisation and dispatch deletions to downstream systems.</p>
          </div>
        </div>
        <div class="col-md-6 col-lg-4">
          <div class="card h-100 hover-lift border-0 bg-light p-4">
            <div class="text-primary mb-3"><i class="bi bi-key-fill fs-3"></i></div>
            <h3 class="h5">Dual-Signature Safeguard</h3>
            <p class="text-muted small mb-0">Prevent accidental or malicious data loss. Highly sensitive categories require double authorization before purge.</p>
          </div>
        </div>
        <div class="col-md-6 col-lg-4">
          <div class="card h-100 hover-lift border-0 bg-light p-4">
            <div class="text-primary mb-3"><i class="bi bi-globe fs-3"></i></div>
            <h3 class="h5">Multi-Jurisdiction Scope</h3>
            <p class="text-muted small mb-0">Operate seamlessly across global guidelines including GDPR, NDPR/NDPA, CCPA, LGPD, and custom local regulations.</p>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Pricing / Plans -->
  <section class="py-5" style="background: #f1f5f9;">
    <div class="container py-4">
      <div class="text-center mb-5">
        <h2 class="h3 fw-bold text-dark">Enterprise Compliance, Simplified</h2>
        <p class="text-muted">Start with a 14-day free trial. Fully automated, API-driven compliance lifecycle.</p>
      </div>
      <div class="row g-4 justify-content-center" style="max-width: 540px; margin: 0 auto;">
        <div class="col-md-12">
          <div class="card h-100 border-0 shadow-lg p-5 bg-white position-relative" style="border-top: 5px solid var(--3c-primary) !important;">
            <div class="position-absolute top-0 end-0 bg-primary text-white px-3 py-1 rounded-bottom-left small fw-bold" style="border-bottom-left-radius: 8px;">ENTERPRISE SAAS</div>
            <h3 class="h4 fw-bold text-dark">ADRS Enterprise Plan</h3>
            <p class="text-muted small">For businesses integrating data lifecycle automation directly with their internal transactional databases, systems, and APIs.</p>
            <div class="my-4">
              <span class="display-5 fw-bold text-dark">₦250,000</span>
              <span class="text-muted"> / year</span>
            </div>
            <hr>
            <h4 class="h6 fw-bold text-dark mb-3">What's included:</h4>
            <ul class="list-unstyled mb-4 small flex-grow-1">
              <li class="mb-3"><i class="bi bi-check-circle-fill text-primary me-2"></i> REST API v1 Integration Gateway</li>
              <li class="mb-3"><i class="bi bi-check-circle-fill text-primary me-2"></i> Auto-Categorisation &amp; Custom Field Mapping</li>
              <li class="mb-3"><i class="bi bi-check-circle-fill text-primary me-2"></i> Outbound Webhook Disposal Dispatches with HMAC signatures</li>
              <li class="mb-3"><i class="bi bi-check-circle-fill text-primary me-2"></i> Event-Driven Account Closure and Disposal API Triggers</li>
              <li class="mb-3"><i class="bi bi-check-circle-fill text-primary me-2"></i> Automated Async API Intake Queue &amp; Deduplication</li>
              <li class="mb-3"><i class="bi bi-check-circle-fill text-primary me-2"></i> Secure Dual-Signature Safeguards for Sensitive Categories</li>
              <li class="mb-3"><i class="bi bi-check-circle-fill text-primary me-2"></i> Immutable Cryptographically Chained Compliance Ledger</li>
            </ul>
            <a href="<?= APP_URL ?>/register?tier=enterprise" class="btn btn-primary btn-lg w-100 mt-auto shadow-sm">Start Your 14-Day Free Trial</a>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- CTA section -->
  <section class="py-5 text-white text-center" style="background: linear-gradient(135deg, #141426 0%, #1e293b 100%);">
    <div class="container py-4">
      <h2 class="h3 fw-bold mb-3">Ready to deploy secure, audit-proof retention?</h2>
      <p class="text-muted mb-4" style="max-width: 600px; margin: 0 auto;">Join forward-thinking businesses automating data compliance. No credit card required to start your trial.</p>
      <div class="d-flex justify-content-center gap-3">
        <a href="<?= APP_URL ?>/register?tier=core" class="btn btn-primary btn-lg px-4 hover-lift">Register Organisation</a>
        <a href="<?= APP_URL ?>/login" class="btn btn-outline-light btn-lg px-4">Sign In</a>
      </div>
    </div>
  </section>
</main>
<?php public_page_foot(); ?>
