<?php
/**
 * Enterprise intake queue processor (CLI). Cron: every 5 minutes.
 * Schedule: minute "every 5" then "* * * *" => php src/engine/intake_queue_processor.php
 * Thin wrapper over enterprise_lib::process_intake_queue().
 */
if (PHP_SAPI !== 'cli') { http_response_code(403); exit('CLI only.'); }

require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/enterprise_lib.php';

date_default_timezone_set(TIMEZONE);
$pdo = get_db();

if (get_setting($pdo, 'adrs_tier', 'core') !== 'enterprise' || get_setting($pdo, 'intake_queue_enabled', '1') !== '1') {
    echo '[' . date('c') . "] Intake processor: skipped (not enterprise or queue disabled).\n";
    exit(0);
}

$r = process_intake_queue($pdo, 100);
echo '[' . date('c') . "] Intake: processed {$r['processed']}, created {$r['created']}, duplicate {$r['duplicate']}, failed {$r['failed']}\n";
exit(0);
