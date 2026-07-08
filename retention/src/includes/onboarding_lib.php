<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/tenant_lib.php';
require_once __DIR__ . '/billing_lib.php';
require_once __DIR__ . '/invitations_lib.php';
require_once __DIR__ . '/notifications_lib.php';

const ONBOARDING_NOTIF_PREFIX = '[onboarding:';

/**
 * Onboarding checklist for new organisation administrators (SaaS trial).
 * Returns ['steps' => [...], 'complete' => bool, 'done_count' => int, 'total' => int].
 */
function org_onboarding_checklist(PDO $pdo, array $user): array {
    if (($user['role'] ?? '') !== 'admin') {
        return ['steps' => [], 'complete' => true, 'done_count' => 0, 'total' => 0];
    }
    $orgId = (int) ($user['organization_id'] ?? 0);
    if ($orgId <= 0) {
        return ['steps' => [], 'complete' => true, 'done_count' => 0, 'total' => 0];
    }
    if (get_setting($pdo, 'onboarding_dismissed', '0', $orgId) === '1') {
        return ['steps' => [], 'complete' => true, 'done_count' => 0, 'total' => 0];
    }

    $org = fetch_organization($pdo, $orgId);
    $emailVerified = !empty($user['email_verified_at']) || is_local_environment();
    $smtpOk = smtp_is_configured($pdo);
    $teamStmt = $pdo->prepare('SELECT COUNT(*) FROM users WHERE organization_id = :o AND deleted_at IS NULL AND is_active = 1');
    $teamStmt->execute(['o' => $orgId]);
    $teamCount = (int) $teamStmt->fetchColumn();
    $dpoStmt = $pdo->prepare("SELECT COUNT(*) FROM users WHERE organization_id = :o AND role = 'dpo' AND deleted_at IS NULL");
    $dpoStmt->execute(['o' => $orgId]);
    $hasDpo = (int) $dpoStmt->fetchColumn() > 0;
    $pendingInvites = count(list_pending_invitations($pdo, $orgId));
    $teamReady = $teamCount > 1 || $hasDpo || $pendingInvites > 0;
    $recStmt = $pdo->prepare('SELECT COUNT(*) FROM data_records WHERE organization_id = :o AND deleted_at IS NULL');
    $recStmt->execute(['o' => $orgId]);
    $hasRecords = (int) $recStmt->fetchColumn() > 0;
    $profileOk = $org && trim((string) ($org['billing_email'] ?? '')) !== '';

    $steps = [
        [
            'key'  => 'verify_email',
            'label'=> 'Verify your work email',
            'hint' => 'Confirm your administrator account.',
            'done' => $emailVerified,
            'href' => APP_URL . '/verify_email',
        ],
        [
            'key'  => 'org_profile',
            'label'=> 'Complete organisation profile',
            'hint' => 'Billing contact and timezone.',
            'done' => $profileOk,
            'href' => APP_URL . '/settings/organization',
        ],
        [
            'key'  => 'smtp',
            'label'=> 'Configure email delivery',
            'hint' => 'SMTP for alerts, escalations, and compliance notices.',
            'done' => $smtpOk,
            'href' => APP_URL . '/settings?tab=email',
        ],
        [
            'key'  => 'team',
            'label'=> 'Invite your DPO or data owners',
            'hint' => 'Add colleagues with @' . ($org['primary_domain'] ?? 'your-domain') . ' emails.',
            'done' => $teamReady,
            'href' => APP_URL . '/users/invite',
        ],
        [
            'key'  => 'first_record',
            'label'=> 'Register your first retention record',
            'hint' => 'Start building your compliance register.',
            'done' => $hasRecords,
            'href' => APP_URL . '/records/create',
        ],
    ];

    $doneCount = count(array_filter($steps, fn($s) => $s['done']));
    $complete = $doneCount === count($steps);
    if ($complete) {
        set_setting($pdo, 'onboarding_complete', '1', $orgId);
    }

    return [
        'steps'      => $steps,
        'complete'   => $complete,
        'done_count' => $doneCount,
        'total'      => count($steps),
    ];
}

/** Encode onboarding step key in notification message for deduplication. */
function onboarding_notif_token(string $stepKey): string {
    return ONBOARDING_NOTIF_PREFIX . $stepKey . ']';
}

/** Extract step key from onboarding notification message. */
function onboarding_step_from_message(string $message): ?string {
    if (preg_match('/\[onboarding:([a-z_]+)\]/', $message, $m)) {
        return $m[1];
    }
    return null;
}

/** Extract action URL from onboarding notification message. */
function onboarding_href_from_message(string $message): ?string {
    if (preg_match('/\[action:([^\]]+)\]/', $message, $m)) {
        return $m[1];
    }
    return null;
}

/**
 * Sync incomplete onboarding steps to in-app notifications (replaces dashboard checklist).
 * Idempotent: one unread onboarding notification per pending step.
 */
function sync_onboarding_notifications(PDO $pdo, array $user): void {
    if (($user['role'] ?? '') !== 'admin') { return; }
    $checklist = org_onboarding_checklist($pdo, $user);
    if ($checklist['complete'] || empty($checklist['steps'])) {
        dismiss_onboarding_notifications($pdo, (int) $user['id']);
        return;
    }

    $uid = (int) $user['id'];
    $pendingKeys = [];
    foreach ($checklist['steps'] as $step) {
        if ($step['done']) { continue; }
        $pendingKeys[] = $step['key'];
        $token = onboarding_notif_token($step['key']);
        $exists = $pdo->prepare(
            "SELECT id FROM notifications
             WHERE recipient_id = :u AND type = 'onboarding_setup' AND read_at IS NULL
               AND message LIKE :tok LIMIT 1"
        );
        $exists->execute(['u' => $uid, 'tok' => '%' . $token . '%']);
        if ($exists->fetch()) { continue; }

        $msg = $token . ' ' . $step['hint'] . ' [action:' . $step['href'] . ']';
        create_notification($pdo, $uid, 'onboarding_setup', 'Setup: ' . $step['label'], $msg);
    }

    // Mark notifications read for completed steps.
    if ($pendingKeys) {
        $stmt = $pdo->prepare(
            "SELECT id, message FROM notifications
             WHERE recipient_id = :u AND type = 'onboarding_setup' AND read_at IS NULL"
        );
        $stmt->execute(['u' => $uid]);
        foreach ($stmt->fetchAll() as $n) {
            $key = onboarding_step_from_message($n['message']);
            if ($key && !in_array($key, $pendingKeys, true)) {
                $pdo->prepare('UPDATE notifications SET read_at = NOW() WHERE id = :id')
                    ->execute(['id' => (int) $n['id']]);
            }
        }
    }
}

/** Mark all onboarding notifications read (dismiss guide). */
function dismiss_onboarding_notifications(PDO $pdo, int $userId): void {
    $pdo->prepare(
        "UPDATE notifications SET read_at = NOW()
         WHERE recipient_id = :u AND type = 'onboarding_setup' AND read_at IS NULL"
    )->execute(['u' => $userId]);
}
