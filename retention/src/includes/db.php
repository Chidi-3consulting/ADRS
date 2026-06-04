<?php
require_once __DIR__ . '/../config/database.php';

/**
 * Returns a shared PDO connection. Sets MySQL session time zone to +01:00 (Lagos)
 * on connect — CRITICAL so all NOW()/CURDATE() math matches the app timezone.
 */
function get_db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $dsn = sprintf('mysql:host=%s;port=%s;dbname=%s;charset=%s', DB_HOST, DB_PORT, DB_NAME, DB_CHARSET);
    $options = [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES   => false,
    ];

    try {
        $pdo = new PDO($dsn, DB_USER, DB_PASS, $options);
        $pdo->exec("SET time_zone = '+01:00'");
        $pdo->exec("SET NAMES utf8mb4");
    } catch (PDOException $e) {
        if (!is_dir(LOG_PATH)) { @mkdir(LOG_PATH, 0755, true); }
        @file_put_contents(LOG_PATH . 'db_error.log', '[' . date('c') . '] ' . $e->getMessage() . PHP_EOL, FILE_APPEND);
        if (SHOW_ERRORS) { throw $e; }
        http_response_code(500);
        echo 'A database error occurred. Please try again later.';
        exit;
    }

    return $pdo;
}
