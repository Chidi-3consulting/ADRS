<?php
/** GET /api/v1/health — system health for monitoring. ($pdo, $apiKey from router scope) */
api_require_permission($apiKey, 'health');

$pending = (int) $pdo->query("SELECT COUNT(*) FROM intake_queue WHERE status='pending'")->fetchColumn();
$failed  = (int) $pdo->query("SELECT COUNT(*) FROM intake_queue WHERE status='failed'")->fetchColumn();
$lastAuto = $pdo->query("SELECT MAX(created_at) FROM audit_log WHERE performed_by IS NULL")->fetchColumn();

api_response(200, [
    'status'                => 'healthy',
    'tier'                  => get_setting($pdo, 'adrs_tier', 'core'),
    'timestamp'             => date('c'),
    'queue_pending'         => $pending,
    'queue_failed'          => $failed,
    'last_automated_action' => $lastAuto,
    'connected_system'      => $apiKey['system_name'],
    'api_version'           => '1.0',
]);
