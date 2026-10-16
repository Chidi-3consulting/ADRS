<?php
require_once __DIR__ . '/tenant_lib.php';

/** Shared chrome for unauthenticated pages (landing, login, signup, setup). */

function public_page_head(string $title, ?PDO $pdo = null): void {
    $pdo = $pdo ?? get_db();
    $appName = get_setting($pdo, 'white_label_name', APP_NAME) ?: APP_NAME;
    $primary = get_setting($pdo, 'white_label_primary', '#C85C1A');
    if (!preg_match('/^#[0-9A-Fa-f]{6}$/', (string) $primary)) { $primary = '#C85C1A'; }
    $footer = get_setting($pdo, 'white_label_footer', '3Consulting Limited');
    $GLOBALS['__public_footer'] = $footer;
    $GLOBALS['__public_app_name'] = $appName;
    ?><!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= escape_html($title) ?> — <?= escape_html($appName) ?></title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%23C85C1A'/><text x='16' y='23' font-size='18' font-weight='bold' text-anchor='middle' fill='white' font-family='Arial,sans-serif'>A</text></svg>">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet" integrity="sha384-XGjxtQfXaH2tnPFa9x+ruJTuLE3Aa6LhHSWRr1XeTyhezb4abCG4ccI5AkVDxqC+" crossorigin="anonymous">
<link href="<?= APP_URL ?>/src/assets/css/app.css" rel="stylesheet">
<style>:root{ --3c-orange: <?= $primary ?>; }</style>
</head><body class="public-page"><?php
}

function public_page_nav(?PDO $pdo = null): void {
    $pdo = $pdo ?? get_db();
    $appName = $GLOBALS['__public_app_name'] ?? (get_setting($pdo, 'white_label_name', APP_NAME) ?: APP_NAME);
    ?><nav class="navbar navbar-expand-lg navbar-dark" style="background:var(--3c-dark);">
  <div class="container">
    <a class="navbar-brand fw-bold" href="<?= APP_URL ?>/" style="color:var(--3c-orange)"><?= escape_html($appName) ?></a>
    <div class="d-flex gap-2">
      <?php if (function_exists('is_saas_deployment') && is_saas_deployment($pdo)): ?>
        <a class="btn btn-outline-light btn-sm" href="<?= APP_URL ?>/register?tier=core">Start free trial</a>
      <?php elseif (public_signup_enabled($pdo)): ?>
        <a class="btn btn-outline-light btn-sm" href="<?= APP_URL ?>/signup">Create account</a>
      <?php endif; ?>
      <a class="btn btn-primary btn-sm" href="<?= APP_URL ?>/login">Sign in</a>
    </div>
  </div>
</nav><?php
}

function public_page_foot(): void {
    $footer = $GLOBALS['__public_footer'] ?? '3Consulting Limited';
    $appName = $GLOBALS['__public_app_name'] ?? APP_NAME;
    ?><footer class="text-center text-muted small py-4 mt-auto">
  &copy; <?= date('Y') ?> <?= escape_html($footer) ?> · <?= escape_html($appName) ?>
  <div class="mt-1">
    <a href="<?= APP_URL ?>/legal?page=terms" class="text-muted">Terms</a> ·
    <a href="<?= APP_URL ?>/legal?page=privacy" class="text-muted">Privacy</a> ·
    <a href="<?= APP_URL ?>/legal?page=dpa" class="text-muted">DPA</a>
  </div>
</footer>
</body></html><?php
}

/** Import the 30-category GDPR/NDPR library for an organisation when empty. */
function import_category_seed(PDO $pdo, int $organizationId = 1): int {
    $stmt = $pdo->prepare('SELECT COUNT(*) FROM data_categories WHERE organization_id = :o AND deleted_at IS NULL');
    $stmt->execute(['o' => $organizationId]);
    if ((int) $stmt->fetchColumn() > 0) { return 0; }
    $file = dirname(__DIR__, 2) . '/sql/seed_categories_only.sql';
    if (!is_file($file)) { return 0; }
    $sql = file_get_contents($file);
    // The seed is one multi-row INSERT with comments between rows, so rewriting its VALUES
    // tuples is fragile. Load it into a temporary copy of the table instead, then copy the
    // rows across with the target organisation id.
    if (!preg_match('/INSERT INTO `data_categories`\s*\(([^)]*)\)/i', $sql, $m)) { return 0; }
    $cols = implode(',', array_map('trim', explode(',', $m[1])));
    $sql = preg_replace('/INSERT INTO `data_categories`/i', 'INSERT INTO `tmp_seed_categories`', $sql);
    $pdo->exec('DROP TEMPORARY TABLE IF EXISTS `tmp_seed_categories`');
    $pdo->exec('CREATE TEMPORARY TABLE `tmp_seed_categories` LIKE `data_categories`');
    $pdo->exec($sql);
    $ins = $pdo->prepare("INSERT INTO `data_categories` (`organization_id`, $cols)
                          SELECT :o, $cols FROM `tmp_seed_categories` ORDER BY `id`");
    $ins->execute(['o' => $organizationId]);
    $pdo->exec('DROP TEMPORARY TABLE IF EXISTS `tmp_seed_categories`');
    $stmt->execute(['o' => $organizationId]);
    return (int) $stmt->fetchColumn();
}
