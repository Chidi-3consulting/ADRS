<?php
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/public_layout.php';

$page = $_GET['page'] ?? 'terms';
$pages = [
    'terms' => ['Terms of Service', 'terms'],
    'privacy' => ['Privacy Policy', 'privacy'],
    'dpa' => ['Data Processing Agreement', 'dpa'],
];
if (!isset($pages[$page])) { $page = 'terms'; }
[$title] = $pages[$page];

public_page_head($title);
public_page_nav(get_db());
?>
<main class="flex-grow-1 py-5">
  <div class="container" style="max-width:800px;">
    <div class="card shadow-sm"><div class="card-body">
      <nav class="mb-4">
        <a href="<?= APP_URL ?>/legal?page=terms" class="<?= $page === 'terms' ? 'fw-bold' : '' ?>">Terms</a> ·
        <a href="<?= APP_URL ?>/legal?page=privacy" class="<?= $page === 'privacy' ? 'fw-bold' : '' ?>">Privacy</a> ·
        <a href="<?= APP_URL ?>/legal?page=dpa" class="<?= $page === 'dpa' ? 'fw-bold' : '' ?>">DPA</a>
      </nav>
      <?php if ($page === 'terms'): ?>
        <h1 class="h4">Terms of Service</h1>
        <p class="text-muted small">Last updated: <?= date('F Y') ?></p>
        <p>By registering for ADRS you agree that 3Consulting Limited provides the Automated Data Retention System as a software service. You are responsible for configuring retention categories, lawful bases, and disposal decisions for your organisation's data inventory.</p>
        <p>ADRS automates alerts, escalations, and authorised disposals according to your configuration. You remain the data controller; ADRS is a compliance tool. Do not use the service to store credentials or payment card data.</p>
        <p>Trials convert to paid subscriptions unless cancelled before the trial end date. Fees are non-refundable except where required by law. We may suspend accounts for non-payment or misuse.</p>
      <?php elseif ($page === 'privacy'): ?>
        <h1 class="h4">Privacy Policy</h1>
        <p class="text-muted small">Last updated: <?= date('F Y') ?></p>
        <p>We process account registration data (name, email, organisation name) to provide ADRS. Customer data entered into your tenant remains yours; we do not sell it to third parties.</p>
        <p>We use essential cookies for session authentication. Audit logs within your tenant are stored in your isolated database partition (organisation scope).</p>
        <p>Contact <?= escape_html(get_setting(get_db(), 'platform_support_email', 'privacy@3consult-ng.com')) ?> for data subject requests relating to your ADRS account.</p>
      <?php else: ?>
        <h1 class="h4">Data Processing Agreement (summary)</h1>
        <p class="text-muted small">For enterprise customers requiring a full DPA, contact 3Consulting.</p>
        <p>When you use ADRS to manage personal data on behalf of your organisation, 3Consulting acts as a data processor for account metadata and as a software provider for data you control in your tenant.</p>
        <p>Processor obligations include: access controls, encryption in transit (TLS), audit logging, and subprocessors limited to hosting and payment providers you configure (e.g. Paystack).</p>
        <p>Data location follows your chosen hosting region. Backups and retention of platform logs are described in your deployment runbook.</p>
      <?php endif; ?>
      <p class="mt-4 mb-0"><a href="<?= APP_URL ?>/">&larr; Back to home</a></p>
    </div></div>
  </div>
</main>
<?php public_page_foot(); ?>
