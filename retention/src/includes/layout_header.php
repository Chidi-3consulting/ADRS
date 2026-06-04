<?php
require_once __DIR__ . '/auth.php';
require_login();
$__pdo = get_db();
$__user = current_user();
$page_title = $page_title ?? 'Dashboard';
$active_nav = $active_nav ?? '';
$__unread = get_unread_notification_count($__pdo, (int) $__user['id']);
function navlink(string $key, string $active, string $route, string $icon, string $label): string {
    $cls = $key === $active ? 'active' : '';
    return '<a class="' . $cls . '" href="' . APP_URL . $route . '"><i class="bi ' . $icon . '"></i> ' . escape_html($label) . '</a>';
}
?>
<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= escape_html($page_title) ?> — <?= escape_html(APP_NAME) ?></title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
<link href="<?= APP_URL ?>/src/assets/css/app.css" rel="stylesheet">
</head><body>
<div class="wrapper">
  <nav class="sidebar">
    <div class="brand">ADRS</div>
    <?= navlink('dashboard', $active_nav, '/dashboard', 'bi-house', 'Dashboard') ?>
    <?= navlink('categories', $active_nav, '/categories', 'bi-collection', 'Data Categories') ?>
    <?= navlink('records', $active_nav, '/records', 'bi-card-list', 'Retention Schedule') ?>
    <?php if (has_role('admin','dpo')): ?>
      <?= navlink('audit', $active_nav, '/audit', 'bi-shield-check', 'Audit Log') ?>
      <?= navlink('dsar', $active_nav, '/dsar', 'bi-envelope-paper', 'DSAR Requests') ?>
    <?php endif; ?>
    <?= navlink('notifications', $active_nav, '/notifications', 'bi-bell', 'Notifications') ?>
    <?php if (has_role('admin') && get_setting($__pdo, 'adrs_tier', 'core') === 'enterprise'): ?>
      <?= navlink('integrations', $active_nav, '/integrations', 'bi-hdd-network', 'Integrations') ?>
    <?php endif; ?>
    <?php if (has_role('admin')): ?>
      <?= navlink('users', $active_nav, '/users', 'bi-people', 'Users') ?>
      <?= navlink('settings', $active_nav, '/settings', 'bi-gear', 'Settings') ?>
    <?php endif; ?>
    <div class="mt-auto p-3 border-top border-secondary">
      <div class="small text-light"><?= escape_html($__user['name']) ?></div>
      <?= get_role_badge($__user['role']) ?>
      <a class="d-block mt-2 text-warning" href="<?= APP_URL ?>/logout">Logout</a>
    </div>
  </nav>
  <div class="main-content">
    <div class="topbar d-flex justify-content-between align-items-center">
      <h1 class="h5 mb-0"><?= escape_html($page_title) ?></h1>
      <a class="position-relative" href="<?= APP_URL ?>/notifications">
        <i class="bi bi-bell fs-5"></i>
        <?php if ($__unread > 0): ?><span class="badge bg-danger position-absolute top-0 start-100 translate-middle"><?= $__unread ?></span><?php endif; ?>
      </a>
    </div>
    <div class="content-area p-4">
      <?= render_flash() ?>
