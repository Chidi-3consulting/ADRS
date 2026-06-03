<?php
require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../includes/auth.php';
require_once __DIR__ . '/../../includes/attachments_lib.php';
require_login();
$pdo = get_db();

$att = fetch_attachment($pdo, (int) ($_GET['id'] ?? 0));
if ($att === null) { http_response_code(404); require __DIR__ . '/../../../404.php'; exit; }

$path = attachment_dir() . $att['stored_filename'];
if (!is_file($path)) { http_response_code(404); require __DIR__ . '/../../../404.php'; exit; }

$safe = preg_replace('/[^A-Za-z0-9._-]/', '_', $att['original_filename']);
header('Content-Type: ' . $att['mime_type']);
header('Content-Disposition: attachment; filename="' . $safe . '"');
header('Content-Length: ' . (int) $att['file_size']);
header('X-Content-Type-Options: nosniff');
readfile($path);
exit;
