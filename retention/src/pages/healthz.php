<?php
/**
 * Public health check for uptime monitors / load balancers / SIEM probes.
 * No authentication, no secrets — just liveness + DB reachability.
 * 200 = healthy, 503 = degraded.
 */
require_once __DIR__ . '/../config/database.php';
header('Content-Type: application/json');
header('Cache-Control: no-store, no-cache');
header('X-Content-Type-Options: nosniff');

$out = ['status' => 'ok', 'time' => date('c'), 'checks' => []];
$code = 200;

try {
    $dsn = sprintf('mysql:host=%s;port=%s;dbname=%s;charset=%s', DB_HOST, DB_PORT, DB_NAME, DB_CHARSET);
    $pdo = new PDO($dsn, DB_USER, DB_PASS, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_TIMEOUT => 3]);
    $pdo->query('SELECT 1')->fetch();
    $out['checks']['database'] = 'ok';
} catch (Throwable $e) {
    $out['status'] = 'degraded';
    $out['checks']['database'] = 'fail';
    $code = 503;
}

http_response_code($code);
echo json_encode($out);
