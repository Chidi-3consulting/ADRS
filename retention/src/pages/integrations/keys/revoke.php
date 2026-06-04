<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { redirect(APP_URL . '/integrations/keys'); }
csrf_verify();
$id = (int) ($_POST['id'] ?? 0);
if ($id > 0) { revoke_api_key($pdo, $id, (int) current_user()['id']); flash('success', 'API key revoked.'); }
redirect(APP_URL . '/integrations/keys');
