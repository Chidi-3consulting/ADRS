# Prompt 17 — Enterprise Onboarding Wizard & Tier Management
# ENTERPRISE TIER ONLY

> **Implementation Note:** This specification was originally written with PHP code examples.
> The ADRS codebase has been fully implemented in **Python (FastAPI + SQLAlchemy + Jinja2)**.
> The business logic, rules, and requirements documented below remain the authoritative
> specification. See `retention_py/` for the Python implementation.

---

## Context
The onboarding wizard guides Admins through activating Enterprise, connecting
their first system, configuring field mappings, and running a test ingestion.
It is the "getting started" flow for Enterprise deployments.
Also covers the Core → Enterprise upgrade path.

---

## `src/pages/settings/tier.php` — Tier Management Page
Admin only.

**Shows current tier** with a clear visual:

```html
<!-- Core Tier Active -->
<div class="card border-teal">
  <div class="card-header card-header-teal">
    <i class="bi bi-layers"></i> Current Deployment Tier
  </div>
  <div class="card-body">
    <div class="row align-items-center">
      <div class="col-md-6">
        <div class="d-flex align-items-center gap-3">
          <div style="font-size:3rem">📋</div>
          <div>
            <h4 class="mb-1">ADRS Core</h4>
            <p class="text-muted mb-0">Standalone compliance portal. Manual intake, automated enforcement.</p>
          </div>
        </div>
      </div>
      <div class="col-md-6 text-end">
        <a href="upgrade.php" class="btn btn-lg btn-primary">
          <i class="bi bi-arrow-up-circle"></i> Upgrade to Enterprise
        </a>
        <p class="small text-muted mt-2">Contact 3Consulting to receive your Enterprise licence key.</p>
      </div>
    </div>
  </div>
</div>
```

```html
<!-- Enterprise Tier Active -->
<div class="card border-success">
  <div class="card-header" style="background:#1E7D34;color:#fff">
    <i class="bi bi-diagram-3"></i> ADRS Enterprise — Active
  </div>
  <div class="card-body">
    <p>Enterprise tier is active. The REST API is <?= $api_enabled ? 'enabled' : 'disabled' ?>.</p>
    <a href="<?= APP_URL ?>/src/pages/integrations/onboarding/" class="btn btn-primary">
      <i class="bi bi-play-circle"></i> Onboarding Wizard
    </a>
    <a href="<?= APP_URL ?>/src/pages/integrations/" class="btn btn-outline-secondary ms-2">
      Manage Integrations
    </a>
  </div>
</div>
```

---

## `src/pages/settings/upgrade.php` — Core → Enterprise Upgrade

**Step 1: Licence Key Entry**
```html
<form method="POST">
  <?= csrf_field() ?>
  <div class="mb-3">
    <label class="form-label fw-bold">Enterprise Licence Key</label>
    <input type="text" name="licence_key" class="form-control font-monospace"
           placeholder="ADRS-ENT-XXXX-XXXX-XXXX-XXXX" required>
    <div class="form-text">
      Provided by 3Consulting Limited. Contact projects@3consult-ng.com to obtain yours.
    </div>
  </div>
  <button type="submit" class="btn btn-primary">Activate Enterprise Tier</button>
</form>
```

**POST logic:**
```php
// Validate licence key format: ADRS-ENT-[4 groups of 4 alphanumeric]
$key = strtoupper(sanitize($_POST['licence_key']));
if (!preg_match('/^ADRS-ENT-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/', $key)) {
    flash('error', 'Invalid licence key format.');
    redirect(back);
}

// In v1: simple format validation + set tier
// In production: call 3Consulting licence validation API
$pdo->prepare("UPDATE system_settings SET setting_value = 'enterprise' WHERE setting_key = 'adrs_tier'")
    ->execute();
$pdo->prepare("UPDATE system_settings SET setting_value = '1' WHERE setting_key = 'enterprise_api_enabled'")
    ->execute();
$pdo->prepare("UPDATE system_settings SET setting_value = ? WHERE setting_key = 'licence_key'")
    ->execute([$key]);

log_audit($pdo, 'user_updated', 'system', null, current_user()['id'],
    ['action' => 'tier_upgraded', 'new_tier' => 'enterprise'], get_client_ip());

flash('success', '✅ Enterprise tier activated. Start the onboarding wizard to connect your first system.');
redirect(APP_URL . '/src/pages/integrations/onboarding/');
```

---

## `src/pages/integrations/onboarding/` — Enterprise Onboarding Wizard

A multi-step wizard. Progress tracked in `$_SESSION['onboarding_step']`.

### Step 1: Welcome (`index.php`)

```html
<div class="card">
  <div class="card-header card-header-teal">
    <i class="bi bi-stars"></i> Enterprise Onboarding — Step 1 of 5
  </div>
  <div class="card-body">
    <h4>Welcome to ADRS Enterprise</h4>
    <p>This wizard will guide you through connecting your first external system.
       It takes about 15–20 minutes to complete.</p>

    <div class="row g-3 mb-4">
      <?php foreach ([
        ['1', 'Register System',   'Name and describe the system you are connecting'],
        ['2', 'Create API Key',    'Generate authentication credentials'],
        ['3', 'Field Mapping',     'Map your system\'s fields to ADRS categories'],
        ['4', 'Rules & Testing',   'Define auto-categorisation rules and send a test record'],
        ['5', 'Go Live',           'Enable the integration and start monitoring'],
      ] as [$n, $title, $desc]): ?>
      <div class="col-md-6">
        <div class="d-flex gap-3 align-items-start p-3 border rounded">
          <div class="rounded-circle bg-teal text-white d-flex align-items-center justify-content-center"
               style="width:32px;height:32px;flex-shrink:0;background:#1A6187">
            <strong><?= $n ?></strong>
          </div>
          <div>
            <strong><?= $title ?></strong>
            <div class="small text-muted"><?= $desc ?></div>
          </div>
        </div>
      </div>
      <?php endforeach; ?>
    </div>

    <a href="step2.php" class="btn btn-primary btn-lg">Begin Setup →</a>
  </div>
</div>
```

---

### Step 2: Register System (`step2.php`)

Same form as `integrations/create.php` but embedded in the wizard flow.

**Additional field:** "What data does this system create?" (multiselect of categories)
— This pre-populates suggested auto-categorisation rules in Step 4.

On save: creates `connected_systems` row, stores `system_id` in session.

---

### Step 3: Create API Key (`step3.php`)

Same form as `api_keys/create.php` but wizard-embedded.

After creation: shows the raw key in the "save this once" alert.
Provides a copy of the curl test command:

```html
<div class="card border-info mt-4">
  <div class="card-header bg-info text-white">Test your API key right now</div>
  <div class="card-body">
    <p class="small">Run this from your terminal to verify the key works:</p>
    <pre style="background:#1A1A2E;color:#79B8FF;padding:16px;border-radius:6px;font-size:12px">
curl -X GET \
  "<?= APP_URL ?>/api/v1/health" \
  -H "X-API-Key: YOUR_API_KEY_HERE"</pre>
    <p class="small text-muted">Expected response: <code>{"status":"healthy","tier":"enterprise",...}</code></p>
  </div>
</div>
```

---

### Step 4: Field Mapping & Rules (`step4.php`)

Two sub-sections on one page:

**Sub-section A: Field Mappings**
Based on the categories selected in Step 2, show a pre-filled mapping suggestion table.

Example for a bank that selected "Customer KYC":
| Object Type | Suggest External Field | Maps To ADRS Field | Required |
|---|---|---|---|
| customer_kyc | customer_id or ref | record_reference | ✅ |
| customer_kyc | customer_type | data_subject_type | |
| customer_kyc | created_at or signup_date | collection_date | ✅ |

Admin can accept the suggestions or modify each row. "Add another mapping" link below.

**Sub-section B: Auto-categorisation Rules**
Based on categories selected, show pre-built rule suggestions:

```html
<div class="card mb-3 border-success">
  <div class="card-body">
    <div class="d-flex justify-content-between align-items-center">
      <div>
        <strong>Suggested Rule:</strong> When object_type = "customer_kyc"
        → Assign: <em>Customer KYC & Onboarding Data</em> (5 years / Archive)
      </div>
      <div class="d-flex gap-2">
        <button class="btn btn-sm btn-success accept-rule" data-rule="...">✅ Accept</button>
        <button class="btn btn-sm btn-outline-secondary edit-rule">✏️ Edit</button>
      </div>
    </div>
  </div>
</div>
```

Admin accepts, edits, or skips each suggestion. Accepted rules are inserted to
`auto_categorization_rules`.

---

### Step 5: Test Ingestion (`step5.php`)

Send a test record from within the wizard UI to verify everything works end-to-end.

```html
<div class="card">
  <div class="card-header card-header-teal">Step 5: Test Your Integration</div>
  <div class="card-body">
    <p>We will send a test record to ADRS using your API key and verify it is
       correctly categorised and added to the retention schedule.</p>

    <div class="row">
      <div class="col-md-6">
        <h6>Test Payload (editable):</h6>
        <textarea id="testPayload" class="form-control font-monospace" rows="8">{
  "object_type": "<?= sanitize($suggested_object_type) ?>",
  "external_ref": "TEST-<?= date('Ymd') ?>-001",
  "data_subject_type": "Test Subject",
  "collection_date": "<?= date('Y-m-d') ?>",
  "metadata": {"source": "onboarding_test"}
}</textarea>
      </div>
      <div class="col-md-6">
        <h6>Result:</h6>
        <div id="testResult" class="p-3 border rounded" style="min-height:160px;background:#f8f9fa;font-family:monospace;font-size:12px">
          Click "Send Test Record" to see the result...
        </div>
      </div>
    </div>

    <button id="sendTest" class="btn btn-primary mt-3">
      <i class="bi bi-send"></i> Send Test Record
    </button>
  </div>
</div>
```

**JavaScript:**
```javascript
document.getElementById('sendTest').addEventListener('click', async () => {
    const payload = document.getElementById('testPayload').value;
    const result  = document.getElementById('testResult');
    result.innerHTML = '⏳ Sending...';

    try {
        const res = await fetch(`${APP_URL}/api/v1/ingest`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': '<?= sanitize($session_api_key) ?>'
            },
            body: payload
        });
        const data = await res.json();
        result.style.color = res.ok ? '#1E7D34' : '#C0392B';
        result.innerHTML = `HTTP ${res.status}\n\n` + JSON.stringify(data, null, 2);

        if (res.ok) {
            document.getElementById('goLiveBtn').removeAttribute('disabled');
        }
    } catch (e) {
        result.style.color = '#C0392B';
        result.innerHTML = 'Error: ' + e.message;
    }
});
```

After successful test: show ✅ "Test record received and categorised correctly."

**"Go Live" button** (disabled until test passes):
```html
<button id="goLiveBtn" class="btn btn-success btn-lg mt-3" disabled form="goLiveForm">
  <i class="bi bi-check-circle"></i> Complete Setup & Go Live
</button>
```

POST handler:
- Enables the connected system (`is_active = 1`)
- Enables API (`enterprise_api_enabled = 1`)
- Clears onboarding session vars
- Logs to audit_log
- Redirects to `/integrations/` with flash:
  "🎉 Integration live! [System Name] is now connected. Records will be ingested automatically."

---

## Onboarding Progress Indicator

Add to all wizard steps at top of page:

```php
$steps = ['Register System', 'API Key', 'Field Mapping', 'Rules & Test', 'Go Live'];
$current = 2; // current step number
?>
<div class="d-flex mb-4">
  <?php foreach ($steps as $i => $label): ?>
  <div class="flex-fill text-center">
    <div class="rounded-circle mx-auto d-flex align-items-center justify-content-center mb-1"
         style="width:32px;height:32px;
                background:<?= ($i+1) < $current ? '#1E7D34' : (($i+1) === $current ? '#1A6187' : '#dee2e6') ?>;
                color:white">
      <?= ($i+1) < $current ? '✓' : ($i+1) ?>
    </div>
    <div class="small <?= ($i+1) === $current ? 'fw-bold text-primary' : 'text-muted' ?>">
      <?= $label ?>
    </div>
  </div>
  <?php if ($i < count($steps)-1): ?>
  <div class="flex-fill" style="padding-top:16px">
    <hr style="border-color:<?= ($i+1) < $current ? '#1E7D34' : '#dee2e6' ?>">
  </div>
  <?php endif; ?>
  <?php endforeach; ?>
</div>
```
