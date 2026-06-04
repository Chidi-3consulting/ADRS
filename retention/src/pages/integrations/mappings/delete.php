<?php
require_once __DIR__ . '/../../../config/database.php';
require_once __DIR__ . '/../../../includes/auth.php';
require_once __DIR__ . '/../../../includes/enterprise_lib.php';
require_role('admin');
$pdo = get_db();
require_enterprise($pdo);
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { redirect(APP_URL . '/integrations/mappings'); }
csrf_verify();
$id = (int) ($_POST['id'] ?? 0);
if ($id > 0) { $pdo->prepare("DELETE FROM field_mappings WHERE id=:id")->execute(['id'=>$id]); flash('success', 'Mapping deleted.'); }
redirect(APP_URL . '/integrations/mappings');
