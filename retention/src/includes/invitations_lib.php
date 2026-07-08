<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/tenant_lib.php';

const INVITE_EXPIRY_DAYS = 7;

/** Pending invitations for the current organisation. */
function list_pending_invitations(PDO $pdo, ?int $orgId = null): array {
    $orgId = $orgId ?? require_org_id();
    $stmt = $pdo->prepare(
        "SELECT i.*, u.name AS invited_by_name
         FROM organization_invitations i
         LEFT JOIN users u ON u.id = i.invited_by
         WHERE i.organization_id = :o AND i.accepted_at IS NULL AND i.revoked_at IS NULL
           AND i.expires_at > NOW()
         ORDER BY i.created_at DESC"
    );
    $stmt->execute(['o' => $orgId]);
    return $stmt->fetchAll();
}

/**
 * Create or refresh a team invitation. Returns ['token' => raw, 'invitation_id' => int].
 * @throws InvalidArgumentException on validation failure
 */
function create_org_invitation(PDO $pdo, string $name, string $email, string $role, int $invitedBy, ?int $orgId = null): array {
    $orgId = $orgId ?? require_org_id();
    $name = trim($name);
    $email = strtolower(trim($email));
    if ($name === '' || $email === '') {
        throw new InvalidArgumentException('Name and email are required.');
    }
    if (!in_array($role, ['admin', 'dpo', 'data_owner'], true)) {
        throw new InvalidArgumentException('Invalid role.');
    }
    if (($err = org_member_email_error($pdo, $email, $orgId)) !== null) {
        throw new InvalidArgumentException($err);
    }
    $exists = $pdo->prepare('SELECT 1 FROM users WHERE email = :e AND deleted_at IS NULL LIMIT 1');
    $exists->execute(['e' => $email]);
    if ($exists->fetch()) {
        throw new InvalidArgumentException('A user with that email already exists.');
    }

    $pdo->prepare(
        "UPDATE organization_invitations SET revoked_at = NOW()
         WHERE organization_id = :o AND email = :e AND accepted_at IS NULL AND revoked_at IS NULL"
    )->execute(['o' => $orgId, 'e' => $email]);

    $raw = bin2hex(random_bytes(32));
    $hash = hash('sha256', $raw);
    $pdo->prepare(
        "INSERT INTO organization_invitations (organization_id, email, name, role, token_hash, invited_by, expires_at)
         VALUES (:o, :e, :n, :r, :h, :by, DATE_ADD(NOW(), INTERVAL :days DAY))"
    )->execute([
        'o' => $orgId, 'e' => $email, 'n' => $name, 'r' => $role,
        'h' => $hash, 'by' => $invitedBy, 'days' => INVITE_EXPIRY_DAYS,
    ]);
    return ['token' => $raw, 'invitation_id' => (int) $pdo->lastInsertId()];
}

/** Load a valid invitation by raw token, or null. */
function find_invitation_by_token(PDO $pdo, string $rawToken): ?array {
    if ($rawToken === '') { return null; }
    $hash = hash('sha256', $rawToken);
    $stmt = $pdo->prepare(
        "SELECT i.*, o.name AS org_name, o.primary_domain
         FROM organization_invitations i
         JOIN organizations o ON o.id = i.organization_id
         WHERE i.token_hash = :h AND i.accepted_at IS NULL AND i.revoked_at IS NULL
           AND i.expires_at > NOW()
         LIMIT 1"
    );
    $stmt->execute(['h' => $hash]);
    $row = $stmt->fetch();
    return $row === false ? null : $row;
}

/** Revoke a pending invitation belonging to the org. */
function revoke_org_invitation(PDO $pdo, int $invitationId, ?int $orgId = null): bool {
    $orgId = $orgId ?? require_org_id();
    $stmt = $pdo->prepare(
        "UPDATE organization_invitations SET revoked_at = NOW()
         WHERE id = :id AND organization_id = :o AND accepted_at IS NULL AND revoked_at IS NULL"
    );
    $stmt->execute(['id' => $invitationId, 'o' => $orgId]);
    return $stmt->rowCount() > 0;
}

/**
 * Accept an invitation: create the user and mark invite accepted.
 * Returns the new user row (without secrets).
 * @throws InvalidArgumentException
 */
function accept_org_invitation(PDO $pdo, string $rawToken, string $password, ?string $nameOverride = null): array {
    $invite = find_invitation_by_token($pdo, $rawToken);
    if ($invite === null) {
        throw new InvalidArgumentException('This invitation link is invalid or has expired.');
    }
    if (($pwErr = password_policy_error($password)) !== null) {
        throw new InvalidArgumentException($pwErr);
    }
    $name = trim($nameOverride ?? $invite['name']);
    if ($name === '') {
        throw new InvalidArgumentException('Your name is required.');
    }

    $exists = $pdo->prepare('SELECT 1 FROM users WHERE email = :e AND deleted_at IS NULL LIMIT 1');
    $exists->execute(['e' => $invite['email']]);
    if ($exists->fetch()) {
        throw new InvalidArgumentException('An account with this email already exists. Sign in instead.');
    }

    $pdo->beginTransaction();
    try {
        $pdo->prepare(
            "INSERT INTO users (organization_id, name, email, password_hash, role, is_active, must_change_password, email_verified_at)
             VALUES (:oid, :n, :e, :p, :r, 1, 0, NOW())"
        )->execute([
            'oid' => (int) $invite['organization_id'],
            'n'   => $name,
            'e'   => $invite['email'],
            'p'   => password_hash($password, PASSWORD_BCRYPT),
            'r'   => $invite['role'],
        ]);
        $userId = (int) $pdo->lastInsertId();
        $pdo->prepare('UPDATE organization_invitations SET accepted_at = NOW() WHERE id = :id')
            ->execute(['id' => (int) $invite['id']]);
        $pdo->commit();
    } catch (Throwable $e) {
        $pdo->rollBack();
        throw $e;
    }

    $stmt = $pdo->prepare('SELECT * FROM users WHERE id = :id LIMIT 1');
    $stmt->execute(['id' => $userId]);
    return $stmt->fetch();
}

function invite_accept_url(string $rawToken): string {
    return APP_URL . '/invite/accept?token=' . urlencode($rawToken);
}

/** Send team invite email; returns true if dispatched. */
function send_invitation_email(PDO $pdo, string $toEmail, string $name, string $role, string $orgName, string $rawToken): bool {
    require_once __DIR__ . '/email_templates.php';
    require_once __DIR__ . '/mailer.php';
    $link = invite_accept_url($rawToken);
    [$subj, $html] = email_team_invite($name, $orgName, $role, $link);
    if (smtp_is_configured($pdo)) {
        return send_system_email($pdo, $toEmail, $subj, $html);
    }
    return send_platform_email($pdo, $toEmail, $subj, $html);
}
