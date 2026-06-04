<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';

/** Secure file attachments (S8) — files stored OUTSIDE the web root, metadata in DB. */

function attachment_allowed_extensions(): array { return ['pdf','doc','docx','xls','xlsx','jpg','jpeg','png','txt','csv']; }
function attachment_max_bytes(): int { return 10 * 1024 * 1024; } // 10 MB

/** Validate an upload by filename + size. Returns an error string, or null if acceptable. */
function attachment_validate(string $original_name, int $size): ?string {
    if ($size <= 0) { return 'Empty file.'; }
    if ($size > attachment_max_bytes()) { return 'File exceeds the 10 MB limit.'; }
    $ext = strtolower(pathinfo($original_name, PATHINFO_EXTENSION));
    if (!in_array($ext, attachment_allowed_extensions(), true)) { return 'File type not allowed: .' . $ext; }
    return null;
}

/** Generate a non-guessable, traversal-proof stored filename preserving the extension. */
function attachment_stored_name(string $original_name): string {
    $ext = strtolower(pathinfo($original_name, PATHINFO_EXTENSION));
    return bin2hex(random_bytes(16)) . ($ext !== '' ? '.' . preg_replace('/[^a-z0-9]/', '', $ext) : '');
}

/** Absolute storage directory (created on demand), outside public_html in production. */
function attachment_dir(): string {
    $dir = rtrim(UPLOAD_PATH, '/\\') . DIRECTORY_SEPARATOR;
    if (!is_dir($dir)) { @mkdir($dir, 0755, true); }
    return $dir;
}

/**
 * Persist an uploaded file for a record. $file is a $_FILES entry. $mover is an injectable
 * move callback (path, dest): bool — defaults to move_uploaded_file for real requests and
 * allows tests to simulate. Returns the new attachment id. Throws on validation failure.
 */
function store_attachment(PDO $pdo, int $record_id, array $file, int $actor_id, ?callable $mover = null): int {
    $err = attachment_validate($file['name'] ?? '', (int) ($file['size'] ?? 0));
    if ($err !== null) { throw new InvalidArgumentException($err); }
    $stored = attachment_stored_name($file['name']);
    $dest = attachment_dir() . $stored;
    $mover = $mover ?? 'move_uploaded_file';
    if (!$mover($file['tmp_name'] ?? '', $dest)) { throw new RuntimeException('Could not store the uploaded file.'); }

    $stmt = $pdo->prepare(
        "INSERT INTO attachments (record_id, original_filename, stored_filename, file_size, mime_type, uploaded_by)
         VALUES (:rid,:orig,:stored,:size,:mime,:by)"
    );
    $stmt->execute([
        'rid' => $record_id, 'orig' => $file['name'], 'stored' => $stored,
        'size' => (int) $file['size'], 'mime' => $file['type'] ?? 'application/octet-stream', 'by' => $actor_id,
    ]);
    $id = (int) $pdo->lastInsertId();
    log_audit($pdo, 'attachment_uploaded', 'attachment', $id, $actor_id, ['record_id' => $record_id, 'name' => $file['name']], get_client_ip());
    return $id;
}

function fetch_attachment(PDO $pdo, int $id): ?array {
    $stmt = $pdo->prepare("SELECT * FROM attachments WHERE id=:id AND deleted_at IS NULL LIMIT 1");
    $stmt->execute(['id' => $id]);
    $row = $stmt->fetch();
    return $row === false ? null : $row;
}
