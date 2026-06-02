<?php require __DIR__ . '/../includes/layout_header.php'; ?>
<div class="card shadow-sm">
  <div class="card-body">
    <h1 class="h4">Help & Compliance Notes</h1>
    <p>This portal is built to support Automated Data Retention System requirements for GDPR and NDPR.</p>
    <ul>
      <li>All pages require authenticated access.</li>
      <li>Data categories map retention policy and disposal rules.</li>
      <li>Daily cron jobs handle review flagging and disposal automation.</li>
      <li>Audit logs are append-only and can be added from the backend when actions occur.</li>
    </ul>
    <p>Deploy the database schema from <code>sql/schema.sql</code> and seed with <code>sql/seed_gdpr_ndpr.sql</code>.</p>
  </div>
</div>
<?php require __DIR__ . '/../includes/layout_footer.php'; ?>
