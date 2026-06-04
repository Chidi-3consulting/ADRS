<?php
/**
 * Enterprise outbound disposal dispatch (CLI). Cron: every 10 minutes.
 * Schedule: minute "every 10" then "* * * *" => php src/engine/disposal_dispatch_cron.php
 * Thin wrapper over enterprise_lib::process_disposal_dispatches() (real cURL webhooks).
 */
if (PHP_SAPI !== 'cli') { http_response_code(403); exit('CLI only.'); }

require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/enterprise_lib.php';

date_default_timezone_set(TIMEZONE);
$pdo = get_db();

if (get_setting($pdo, 'adrs_tier', 'core') !== 'enterprise' || get_setting($pdo, 'disposal_dispatch_enabled', '1') !== '1') {
    echo '[' . date('c') . "] Disposal dispatch: skipped (not enterprise or dispatch disabled).\n";
    exit(0);
}

$r = process_disposal_dispatches($pdo, 50);
echo '[' . date('c') . "] Disposal dispatch: sent {$r['sent']}, failed {$r['failed']}\n";
exit(0);
