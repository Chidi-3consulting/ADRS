<?php
if (!require_db('email dispatch')) { return; }
require_once __DIR__ . '/../../src/includes/mailer.php';
require_once __DIR__ . '/../../src/includes/notifications_lib.php';

$pdo = get_db();
// Deterministic slate: other test files share this DB and queue notifications.
$pdo->exec("DELETE FROM notifications");
$pdo->exec("INSERT INTO users (name,email,password_hash,role,is_active) VALUES ('Mail User','mail@x.io','x','dpo',1)");
$uid = (int) $pdo->lastInsertId();

create_notification($pdo, $uid, 'review_due', 'Subject One', 'Message one');
create_notification($pdo, $uid, 'review_due', 'Subject Two', 'Message two');

// Capturing fake transport that always succeeds.
$captured = [];
$ok = dispatch_pending_notifications($pdo, function (string $to, string $subj, string $html) use (&$captured): bool {
    $captured[] = [$to, $subj]; return true;
});
assert_equals(2, $ok['sent'], 'both pending notifications sent');
assert_equals(0, $ok['failed'], 'none failed');
assert_equals('mail@x.io', $captured[0][0], 'sent to the recipient email');

$sentCount = (int) $pdo->query("SELECT COUNT(*) c FROM notifications WHERE recipient_id={$uid} AND status='sent' AND sent_at IS NOT NULL")->fetch()['c'];
assert_equals(2, $sentCount, 'notifications marked sent with timestamp');

// A failing transport marks failed + increments attempts (and is re-tried until attempts=3).
create_notification($pdo, $uid, 'review_due', 'Will Fail', 'nope');
$res = dispatch_pending_notifications($pdo, fn($t, $s, $h): bool => false);
assert_equals(1, $res['failed'], 'failing transport marks one failed');
$row = $pdo->query("SELECT status, attempts FROM notifications WHERE recipient_id={$uid} AND subject='Will Fail'")->fetch();
assert_equals('failed', $row['status'], 'status failed');
assert_equals(1, (int) $row['attempts'], 'attempts incremented');
