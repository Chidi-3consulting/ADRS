<?php
$pdo = get_pdo();
$id = (int)($_GET['id'] ?? 0);

if ($id <= 0) {
    http_response_code(404);
    echo 'Attachment not found.';
    exit;
}

$stmt = $pdo->prepare('SELECT * FROM attachments WHERE id = :id AND deleted_at IS NULL LIMIT 1');
$stmt->execute(['id' => $id]);
$attachment = $stmt->fetch();

if (!$attachment) {
    http_response_code(404);
    echo 'Attachment not found.';
    exit;
}

$path = attachment_storage_path() . DIRECTORY_SEPARATOR . $attachment['stored_filename'];
if (!is_file($path)) {
    http_response_code(404);
    echo 'File not found on disk.';
    exit;
}

header('Content-Type: ' . $attachment['mime_type']);
header('Content-Disposition: attachment; filename="' . attachment_safe_filename($attachment['original_filename']) . '"');
header('Content-Length: ' . $attachment['file_size']);
readfile($path);
exit;
?>