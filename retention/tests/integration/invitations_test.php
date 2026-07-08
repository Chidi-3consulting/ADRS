<?php
if (!require_db('team invitations')) { return; }

require_once __DIR__ . '/../../src/includes/billing_lib.php';
require_once __DIR__ . '/../../src/includes/invitations_lib.php';

$pdo = get_db();
$domain = 'invite-' . bin2hex(random_bytes(4)) . '.example';
$adminEmail = 'admin@' . $domain;

$result = register_organization($pdo, 'Invite Test Org', $domain, 'Invite Admin', $adminEmail, 'SecurePass1', 'core');
$orgId = (int) $result['organization_id'];
$adminId = (int) $result['user_id'];

$memberEmail = 'dpo@' . $domain;
$inv = create_org_invitation($pdo, 'Test DPO', $memberEmail, 'dpo', $adminId, $orgId);
assert_true($inv['invitation_id'] > 0, 'invitation row created');
assert_equals(64, strlen($inv['token']), 'invite token length');

$loaded = find_invitation_by_token($pdo, $inv['token']);
assert_true($loaded !== null, 'invitation found by token');
assert_equals($memberEmail, $loaded['email'], 'invite email stored');

$user = accept_org_invitation($pdo, $inv['token'], 'MemberPass1', 'Test DPO');
assert_equals($memberEmail, $user['email'], 'accepted user email');
assert_equals('dpo', $user['role'], 'accepted user role');
assert_equals($orgId, (int) $user['organization_id'], 'accepted user org');

$gone = find_invitation_by_token($pdo, $inv['token']);
assert_true($gone === null, 'token consumed after accept');

// Cleanup
$pdo->prepare('DELETE FROM users WHERE organization_id = :o')->execute(['o' => $orgId]);
$pdo->prepare('DELETE FROM organization_invitations WHERE organization_id = :o')->execute(['o' => $orgId]);
$pdo->prepare('DELETE FROM organization_settings WHERE organization_id = :o')->execute(['o' => $orgId]);
$pdo->prepare('DELETE FROM data_categories WHERE organization_id = :o')->execute(['o' => $orgId]);
$pdo->prepare('DELETE FROM organizations WHERE id = :o')->execute(['o' => $orgId]);
