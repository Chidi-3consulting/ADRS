<?php
/**
 * Automated database backup (CLI). Cron: daily.
 * Schedule: 0 3 * * * => php src/engine/backup_cron.php
 */
if (PHP_SAPI !== 'cli') { http_response_code(403); exit('CLI only.'); }

require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/backups_lib.php';

date_default_timezone_set(TIMEZONE);
$pdo = get_db();
$dir = rtrim(defined('UPLOAD_PATH') ? dirname(UPLOAD_PATH) : __DIR__ . '/../../storage', '/\\') . DIRECTORY_SEPARATOR . 'backups';

$res = backup_database($pdo, $dir);
$pruned = prune_backups($pdo, $dir, (int) get_setting($pdo, 'backup_retention_days', '30'));
echo '[' . date('c') . "] Backup {$res['status']}: " . basename($res['file']) . " ({$res['size']} bytes); pruned $pruned old.\n";
exit($res['status'] === 'success' ? 0 : 1);
