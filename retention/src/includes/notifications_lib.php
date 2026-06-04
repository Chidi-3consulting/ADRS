<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';

/**
 * In-app + (later) email notifications. In Milestone 1B these create rows with
 * status='pending'; the email layer (Milestone 1D) flips them to 'sent' when dispatched.
 */

/** Insert a single notification row. Returns the new id. */
function create_notification(
    PDO $pdo, int $recipient_id, string $type, string $subject, string $message,
    ?int $related_record_id = null, ?int $related_dsar_id = null, bool $owner_missing = false
): int {
    $stmt = $pdo->prepare(
        "INSERT INTO notifications
           (recipient_id, type, related_record_id, related_dsar_id, subject, message, owner_missing, status)
         VALUES (:r, :t, :rr, :rd, :s, :m, :om, 'pending')"
    );
    $stmt->execute([
        'r' => $recipient_id, 't' => $type, 'rr' => $related_record_id, 'rd' => $related_dsar_id,
        's' => $subject, 'm' => $message, 'om' => $owner_missing ? 1 : 0,
    ]);
    return (int) $pdo->lastInsertId();
}

/** Notify every active user holding any of the given roles. Returns count notified. */
function notify_role(
    PDO $pdo, array $roles, string $type, string $subject, string $message, ?int $related_record_id = null
): int {
    $place = implode(',', array_fill(0, count($roles), '?'));
    $stmt = $pdo->prepare("SELECT id FROM users WHERE is_active = 1 AND deleted_at IS NULL AND role IN ($place)");
    $stmt->execute(array_values($roles));
    $n = 0;
    foreach ($stmt->fetchAll() as $u) {
        create_notification($pdo, (int) $u['id'], $type, $subject, $message, $related_record_id);
        $n++;
    }
    return $n;
}

/** All active users with a given role. */
function users_with_role(PDO $pdo, string $role): array {
    $stmt = $pdo->prepare("SELECT * FROM users WHERE role = :r AND is_active = 1 AND deleted_at IS NULL");
    $stmt->execute(['r' => $role]);
    return $stmt->fetchAll();
}
