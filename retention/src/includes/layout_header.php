<?php
require_once __DIR__ . '/auth.php';
require_login();
require_once __DIR__ . '/onboarding_lib.php';
$__pdo = get_db();
$__user = current_user();
sync_onboarding_notifications($__pdo, $__user);
$page_title = $page_title ?? 'Dashboard';
$active_nav = $active_nav ?? '';
$__unread = get_unread_notification_count($__pdo, (int) $__user['id']);
$__setupUnread = 0;
if (has_role('admin')) {
    $obCnt = $__pdo->prepare("SELECT COUNT(*) FROM notifications WHERE recipient_id = :u AND type = 'onboarding_setup' AND read_at IS NULL");
    $obCnt->execute(['u' => (int) $__user['id']]);
    $__setupUnread = (int) $obCnt->fetchColumn();
}
$__org = fetch_current_organization($__pdo);
$__trialDays = $__org ? organization_trial_days_left($__pdo, (int) $__org['id']) : null;
// White-label theming (Phase 3)
$__wlName    = get_setting($__pdo, 'white_label_name', APP_NAME) ?: APP_NAME;
$__wlPrimary = get_setting($__pdo, 'white_label_primary', '#ff914d');
if (!preg_match('/^#[0-9A-Fa-f]{6}$/', (string) $__wlPrimary)) { $__wlPrimary = '#ff914d'; }
$__wlLogo    = get_setting($__pdo, 'white_label_logo_url', '');
function navlink(string $key, string $active, string $route, string $icon, string $label): string {
    $cls = $key === $active ? 'active' : '';
    return '<a class="' . $cls . '" href="' . APP_URL . $route . '"><i class="bi ' . $icon . '"></i> ' . escape_html($label) . '</a>';
}
function navgroup(string $label): string {
    return '<div class="nav-group-label">' . escape_html($label) . '</div>';
}
?>
<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= escape_html($page_title) ?> — <?= escape_html($__wlName) ?></title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%23C85C1A'/><text x='16' y='23' font-size='18' font-weight='bold' text-anchor='middle' fill='white' font-family='Arial,sans-serif'>A</text></svg>">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet" integrity="sha384-XGjxtQfXaH2tnPFa9x+ruJTuLE3Aa6LhHSWRr1XeTyhezb4abCG4ccI5AkVDxqC+" crossorigin="anonymous">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link href="<?= APP_URL ?>/src/assets/css/app.css" rel="stylesheet">
<style>:root{ --3c-orange: <?= $__wlPrimary ?>; } .sidebar .brand{ color: <?= $__wlPrimary ?>; }</style>
</head><body>
<div class="wrapper">
  <nav class="sidebar">
    <?php if ($__org): ?>
    <div class="org-context px-3 pt-3 pb-2 border-bottom border-secondary">
      <div class="org-context-name"><?= escape_html($__org['name']) ?></div>
      <div class="org-context-meta">
        <?= org_status_badge($__org) ?>
        <?php if ($__trialDays !== null): ?>
          <span class="badge bg-warning text-dark badge-sm"><?= (int) $__trialDays ?>d trial</span>
        <?php endif; ?>
      </div>
      <div class="org-context-domain small mt-1" style="color: rgba(255, 255, 255, 0.6); font-size: 0.75rem;">@<?= escape_html($__org['primary_domain'] ?? '') ?></div>
      <?php
        require_once __DIR__ . '/country_regulation_map.php';
        $__labels = get_country_regulation_labels($__org['country'] ?? 'OTHER');
      ?>
      <div class="org-context-law small mt-2" style="font-size: 0.75rem; color: rgba(255, 255, 255, 0.85); line-height: 1.4;">
        <i class="bi bi-shield-check text-warning me-1"></i><?= escape_html($__labels['law']) ?>
      </div>
    </div>
    <?php endif; ?>
    <div class="brand pt-2"><?php if ($__wlLogo): ?><img src="<?= escape_html($__wlLogo) ?>" alt="logo" style="max-height:32px;max-width:200px"><?php else: ?><?= escape_html($__wlName) ?><?php endif; ?></div>
    
    <?= navgroup('📊 Overview') ?>
    <?= navlink('dashboard', $active_nav, '/dashboard', 'bi-house', 'Dashboard') ?>
    <?= navlink('help', $active_nav, '/help', 'bi-book', 'Solution Manual & Help') ?>
    
    <?= navgroup('📁 Data Life Cycle') ?>
    <?= navlink('categories', $active_nav, '/categories', 'bi-collection', 'Data Categories') ?>
    <?= navlink('records', $active_nav, '/records', 'bi-card-list', 'Retention Register') ?>
    
    <?php if (has_role('admin','dpo')): ?>
      <?= navgroup('🔍 Compliance & Audit') ?>
      <?= navlink('audit', $active_nav, '/audit', 'bi-shield-check', 'Audit Log') ?>
      <?= navlink('reports', $active_nav, '/reports', 'bi-graph-up', 'Analytics & Reports') ?>
    <?php endif; ?>
    
    <?= navgroup('🔔 Notifications') ?>
    <?= navlink('notifications', $active_nav, '/notifications', 'bi-bell', 'Inbox') ?>
    
    <?php if (has_role('admin')): ?>
      <?= navgroup('🔌 API & Integrations') ?>
      <?= navlink('integrations', $active_nav, '/integrations', 'bi-hdd-network', 'Integrations') ?>
    <?php endif; ?>
    
    <?php if (has_role('admin')): ?>
      <?= navgroup('⚙️ Administration') ?>
      <?= navlink('users', $active_nav, '/users', 'bi-people', 'Team Users') ?>
      <?= navlink('settings', $active_nav, '/settings', 'bi-gear', 'Settings') ?>
      <?= navlink('billing', $active_nav, '/billing', 'bi-credit-card', 'Billing & subscription') ?>
    <?php endif; ?>
    
    <?php if (!empty($__user['is_platform_admin'])): ?>
      <?= navgroup('🛡️ Platform Control') ?>
      <a href="<?= APP_URL ?>/platform" class="text-warning"><i class="bi bi-shield-lock"></i> Platform admin</a>
    <?php endif; ?>
    
    <div class="mt-auto p-3 border-top border-secondary">
      <div class="small text-light"><?= escape_html($__user['name']) ?></div>
      <?= get_role_badge($__user['role']) ?>
      <a class="d-block mt-2 small" href="<?= APP_URL ?>/profile">My profile</a>
      <a class="d-block mt-1 text-warning" href="<?= APP_URL ?>/logout">Logout</a>
    </div>
  </nav>
  <div class="main-content">
    <div class="topbar d-flex justify-content-between align-items-center">
      <div>
        <div class="h5 mb-0 fw-semibold"><?= escape_html($page_title) ?></div>
        <?php if ($__org): ?>
          <div class="small text-muted"><?= escape_html($__org['name']) ?> · <?= escape_html($__user['name']) ?> · <?= strip_tags(get_role_badge($__user['role'])) ?></div>
        <?php endif; ?>
      </div>
      <div class="d-flex align-items-center gap-3">
        <?php if ($__setupUnread > 0 && has_role('admin')): ?>
          <a href="<?= APP_URL ?>/notifications" class="btn btn-sm btn-outline-warning">
            Setup <?= (int) $__setupUnread ?>
          </a>
        <?php endif; ?>
        <a class="position-relative" href="<?= APP_URL ?>/notifications">
          <i class="bi bi-bell fs-5"></i>
          <?php if ($__unread > 0): ?><span class="badge bg-danger position-absolute top-0 start-100 translate-middle"><?= $__unread ?></span><?php endif; ?>
        </a>
      </div>
    </div>
    <div class="content-area p-4">
      <?= render_flash() ?>
