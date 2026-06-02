<?php
// Database connection settings. Do not commit secrets to Git.
// Override with src/config/config.local.php in local environments.

$dbConfig = [
    'host' => '127.0.0.1',
    'port' => '3306',
    'name' => 'adrs',
    'user' => 'root',
    'pass' => '',
    'charset' => 'utf8mb4',
];

if (file_exists(__DIR__ . '/config.local.php')) {
    require __DIR__ . '/config.local.php';
}
