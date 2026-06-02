<?php
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';

require_login();

$term = trim($_GET['q'] ?? '');
$pdo = get_pdo();
$stmt = $pdo->prepare('SELECT id, name FROM data_categories WHERE deleted_at IS NULL AND name LIKE :term LIMIT 20');
$stmt->execute(['term' => '%' . $term . '%']);
$rows = $stmt->fetchAll();

header('Content-Type: application/json; charset=utf-8');
echo json_encode($rows);
