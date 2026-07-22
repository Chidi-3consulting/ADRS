<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/helpers.php';
require_once __DIR__ . '/../includes/country_regulation_map.php';

$pdo = get_db();
$org = fetch_current_organization($pdo);
$labels = get_country_regulation_labels($org['country'] ?? 'OTHER');

$page_title = 'Solution Manual & Help';
$active_nav = 'help';
require __DIR__ . '/../includes/layout_header.php';
?>
<div class="container-fluid px-0" style="max-width: 960px;">
  <!-- Title / Introduction -->
  <div class="d-flex align-items-center gap-3 mb-4">
    <div class="bg-primary text-white rounded-3 p-3 d-flex align-items-center justify-content-center" style="width: 56px; height: 56px;">
      <i class="bi bi-book fs-3"></i>
    </div>
    <div>
      <h1 class="h3 mb-1 fw-bold text-dark">ADRS Platform Manual</h1>
      <p class="text-muted mb-0">The complete guide to automated data retention, disposal, and regulatory compliance.</p>
    </div>
  </div>

  <!-- Localized Alert box -->
  <div class="alert alert-info border-0 shadow-sm d-flex gap-3 mb-5 p-4 rounded-3">
    <div class="fs-3"><i class="bi bi-shield-check text-info"></i></div>
    <div>
      <h4 class="h6 fw-bold text-dark">Active Compliance Setting</h4>
      <p class="small mb-0 text-muted">
        Your ADRS account is registered under <strong><?= escape_html(ADRS_SUPPORTED_COUNTRIES[$org['country'] ?? 'OTHER'] ?? 'General') ?></strong>. 
        Your categories and automated timelines are dynamically tailored to the <strong><?= escape_html($labels['law']) ?></strong> regulated by the <strong><?= escape_html($labels['authority']) ?></strong>.
      </p>
    </div>
  </div>

  <!-- Grid of Sections -->
  <div class="row g-4">
    <!-- Part 1: Lifecycle Concepts -->
    <div class="col-12">
      <div class="card shadow-sm border-0 bg-white">
        <div class="card-body p-4">
          <h2 class="h5 fw-bold text-dark mb-3"><i class="bi bi-diagram-3 text-primary me-2"></i> 1. Core Lifecycle Concepts</h2>
          <p class="text-muted small">ADRS is built around three fundamental blocks to help businesses manage data lifecycles cleanly:</p>
          
          <div class="row g-3 mt-2">
            <div class="col-md-4">
              <div class="p-3 bg-light-subtle rounded border h-100" style="background-color: #fafbfc;">
                <h3 class="h6 fw-bold text-dark">Data Categories</h3>
                <p class="small text-muted mb-0">These are the retention policies (e.g. Employee Records, Customer PII). Each category defines its retention period, lawful basis, review frequency, and disposal method.</p>
              </div>
            </div>
            <div class="col-md-4">
              <div class="p-3 bg-light-subtle rounded border h-100" style="background-color: #fafbfc;">
                <h3 class="h6 fw-bold text-dark">Data Records</h3>
                <p class="small text-muted mb-0">Individual data references created when you collect customer/employee data. ADRS monitors these records to track their exact expiration dates in real-time.</p>
              </div>
            </div>
            <div class="col-md-4">
              <div class="p-3 bg-light-subtle rounded border h-100" style="background-color: #fafbfc;">
                <h3 class="h6 fw-bold text-dark">Disposal Actions</h3>
                <p class="small text-muted mb-0">When records expire, ADRS instructs your system to carry out the designated action: <strong>Secure Delete</strong>, <strong>Anonymise</strong>, or <strong>Archive</strong>.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Part 2: Operating Manual / Checklist -->
    <div class="col-md-6">
      <div class="card shadow-sm border-0 bg-white h-100">
        <div class="card-body p-4">
          <h2 class="h5 fw-bold text-dark mb-3"><i class="bi bi-list-task text-primary me-2"></i> 2. Business Compliance Checklist</h2>
          <div class="d-flex gap-3 mb-3">
            <div class="font-monospace text-primary fw-bold">01</div>
            <div>
              <h4 class="h6 fw-bold mb-1">Define Your Inventory</h4>
              <p class="small text-muted">Create data categories corresponding to the data your organization handles. Choose categories based on the pre-built templates suggested for your region.</p>
            </div>
          </div>
          <div class="d-flex gap-3 mb-3">
            <div class="font-monospace text-primary fw-bold">02</div>
            <div>
              <h4 class="h6 fw-bold mb-1">Integrate Data Sources</h4>
              <p class="small text-muted">Connect your CRM, database, or payment system. Generate API credentials in settings so records flow automatically when captured.</p>
            </div>
          </div>
          <div class="d-flex gap-3 mb-3">
            <div class="font-monospace text-primary fw-bold">03</div>
            <div>
              <h4 class="h6 fw-bold mb-1">Audit and Approve Expirations</h4>
              <p class="small text-muted">When a retention timeline is reached, DPOs receive alerts. Approve disposal lists or freeze them with legal holds when necessary.</p>
            </div>
          </div>
          <div class="d-flex gap-3">
            <div class="font-monospace text-primary fw-bold">04</div>
            <div>
              <h4 class="h6 fw-bold mb-1">Annual Compliance Audit</h4>
              <p class="small text-muted">At the end of the fiscal year, export the compliance report to prove to auditors and regulators that expired data has been successfully purged.</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Part 3: Safeguards & API -->
    <div class="col-md-6">
      <div class="card shadow-sm border-0 bg-white h-100">
        <div class="card-body p-4">
          <h2 class="h5 fw-bold text-dark mb-3"><i class="bi bi-shield-lock text-primary me-2"></i> 3. Security & Safe Disposal</h2>
          <h4 class="h6 fw-bold text-dark mb-1">Dual-Signature Control</h4>
          <p class="small text-muted mb-3">Sensitive categories like children's data or biometric files require two authorized users (DPO and Admin) to sign off before disposal is executed, avoiding accidental loss.</p>

          <h4 class="h6 fw-bold text-dark mb-1">Tamper-Proof Ledger</h4>
          <p class="small text-muted mb-3">Every change to categories, policy audits, and data purges is cryptographically signed and stored in the immutable audit log chain, which can be verified at any time in general settings.</p>

          <h4 class="h6 fw-bold text-dark mb-1">Secure Webhooks</h4>
          <p class="small text-muted mb-0">When dispatching disposal commands, ADRS computes an HMAC-SHA256 signature using a shared secret so your backend systems can securely authenticate incoming calls.</p>
        </div>
      </div>
    </div>

    <!-- Part 4: API Quickstart snippet -->
    <div class="col-12">
      <div class="card shadow-sm border-0 bg-white">
        <div class="card-body p-4">
          <h2 class="h5 fw-bold text-dark mb-2"><i class="bi bi-code-slash text-primary me-2"></i> 4. REST API Quickstart</h2>
          <p class="text-muted small">Push new records from your CRM or core backend into ADRS during ingestion:</p>
          <pre class="bg-dark text-light p-3 rounded font-monospace small mb-0 overflow-x-auto">
POST <?= escape_html(APP_URL) ?>/api/v1/records
Header: Authorization: Bearer {your_api_key}
Body:
{
  "record_reference": "USER-4929",
  "category_id": 12,
  "collection_date": "<?= date('Y-m-d') ?>"
}</pre>
        </div>
      </div>
    </div>
  </div>
</div>
<?php require __DIR__ . '/../includes/layout_footer.php'; ?>
