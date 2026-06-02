<?php
$user = current_user();
$flashMessages = flash_get();
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ADRS — Automated Data Retention</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.4/font/bootstrap-icons.css">
</head>
<body class="bg-light">
<nav class="navbar navbar-expand-lg navbar-dark bg-primary">
  <div class="container-fluid">
    <a class="navbar-brand" href="/retention/">ADRS</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMenu">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navMenu">
      <ul class="navbar-nav me-auto mb-2 mb-lg-0">
        <li class="nav-item"><a class="nav-link" href="/retention/dashboard">Dashboard</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/records">Records</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/dsar">DSAR</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/categories">Categories</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/notifications">Notifications</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/attachments">Attachments</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/integration-logs">Integration logs</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/connected-systems">Connected systems</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/api-keys">API keys</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/intake-queue">Intake queue</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/disposal-dispatch">Disposal dispatch</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/audit">Audit</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/settings">Settings</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/users">Users</a></li>
        <li class="nav-item"><a class="nav-link" href="/retention/help">Help</a></li>
      </ul>
      <?php if ($user): ?>
      <div class="d-flex align-items-center text-white">
        <span class="me-3"><i class="bi bi-person-circle"></i> <?= escape_html($user['name']) ?></span>
        <a href="/retention/logout" class="btn btn-outline-light btn-sm">Logout</a>
      </div>
      <?php endif; ?>
    </div>
  </div>
</nav>
<div class="container py-4">
  <?php foreach ($flashMessages as $message): ?>
  <div class="alert alert-<?= escape_html($message['type']) ?> alert-dismissible fade show" role="alert">
    <?= escape_html($message['message']) ?>
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
  </div>
  <?php endforeach; ?>
