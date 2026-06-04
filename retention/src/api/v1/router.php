<?php
require_once __DIR__ . '/bootstrap.php';

$pdo = get_pdo();
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$path = '/' . trim(str_replace('/retention/src/api/v1', '', $path), '/');

switch ($path) {
    case 'health':
        require __DIR__ . '/endpoints/health.php';
        break;
    case 'ingest':
        require __DIR__ . '/endpoints/ingest.php';
        break;
    case 'consent_withdraw':
        require __DIR__ . '/endpoints/consent_withdraw.php';
        break;
    case 'categories':
        require __DIR__ . '/endpoints/categories.php';
        break;
    case 'record_status':
        require __DIR__ . '/endpoints/record_status.php';
        break;
    default:
        send_json(['error' => 'Endpoint not found'], 404);
}
