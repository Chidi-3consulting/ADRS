<?php
/**
 * Daily retention engine (CLI only). Cron examples:
 *   0 1 * * *        php src/engine/retention_cron.php
 *   0 8 1 1,4,7,10 * php src/engine/retention_cron.php --task=quarterly_review
 * Thin wrapper around engine_lib.php so the logic stays unit-testable.
 */
if (PHP_SAPI !== 'cli') { http_response_code(403); exit('CLI only.'); }

require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/engine_lib.php';

date_default_timezone_set(TIMEZONE);
set_time_limit(0);

$task = 'daily';
foreach ($argv as $arg) { if (str_starts_with($arg, '--task=')) { $task = substr($arg, 7); } }

$logFile = rtrim(LOG_PATH, '/\\') . DIRECTORY_SEPARATOR . 'retention_cron.log';
if (!is_dir(LOG_PATH)) { @mkdir(LOG_PATH, 0755, true); }
$log = function (string $m) use ($logFile) {
    $line = '[' . date('Y-m-d H:i:s') . '] ' . $m . PHP_EOL;
    @file_put_contents($logFile, $line, FILE_APPEND);
    echo $line;
};

$pdo = get_db();
$start = microtime(true);

try {
    if ($task === 'quarterly_review') {
        $r = run_quarterly_review($pdo);
        $log("Quarterly review complete: " . json_encode($r));
    } else {
        $log('=== Retention engine START ===');
        $s = run_retention_engine($pdo);
        $log("Flagged: {$s['flagged']} | Consent-disposed: {$s['consent_disposed']} | Auto-disposed: {$s['auto_disposed']} | Dual-approval SKIPPED: {$s['dual_skipped']} | Escalated: {$s['escalated']} | DSAR alerts: {$s['dsar_alerts']} | Review notifications: {$s['review_notifications']}");
        $log('=== Engine COMPLETE in ' . round(microtime(true) - $start, 2) . 's ===');
    }
    exit(0);
} catch (Throwable $e) {
    $errFile = rtrim(LOG_PATH, '/\\') . DIRECTORY_SEPARATOR . 'cron_errors.log';
    @file_put_contents($errFile, '[' . date('c') . '] ' . $e->getMessage() . PHP_EOL . $e->getTraceAsString() . PHP_EOL, FILE_APPEND);
    $log('ERROR: ' . $e->getMessage() . ' — see cron_errors.log');
    exit(1);
}
