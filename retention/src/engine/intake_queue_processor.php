<?php
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/helpers.php';

$pdo = get_pdo();
$pending = $pdo->prepare('SELECT id, payload, system_id, api_key_id FROM intake_queue WHERE status = "pending" ORDER BY created_at ASC LIMIT 20');
$pending->execute();
$items = $pending->fetchAll(PDO::FETCH_ASSOC);

foreach ($items as $item) {
    $pdo->beginTransaction();
    try {
        $payload = json_decode($item['payload'], true);
        if (!is_array($payload)) {
            throw new RuntimeException('Invalid payload');
        }

        if (empty($payload['record_reference']) || empty($payload['collection_date'])) {
            throw new RuntimeException('Missing record_reference or collection_date');
        }

        $categoryId = !empty($payload['category_id']) ? (int)$payload['category_id'] : null;
        if ($categoryId === null && !empty($payload['external_object_type'])) {
            $ruleStmt = $pdo->prepare(
                'SELECT category_id, condition_field, condition_value
                 FROM auto_categorization_rules
                 WHERE system_id = :system_id
                   AND object_type = :object_type
                   AND is_active = 1
                 ORDER BY priority ASC'
            );
            $ruleStmt->execute(['system_id' => $item['system_id'], 'object_type' => $payload['external_object_type']]);
            $rules = $ruleStmt->fetchAll(PDO::FETCH_ASSOC);
            foreach ($rules as $rule) {
                if (empty($rule['condition_field']) || ($payload[$rule['condition_field']] ?? null) === $rule['condition_value']) {
                    $categoryId = (int)$rule['category_id'];
                    break;
                }
            }
        }

        if ($categoryId === null) {
            throw new RuntimeException('Unable to resolve category for intake queue item');
        }

        $retentionEndDate = $payload['retention_end_date'] ?? null;
        if ($retentionEndDate === null) {
            $categoryStmt = $pdo->prepare('SELECT retention_period_days FROM data_categories WHERE id = :id LIMIT 1');
            $categoryStmt->execute(['id' => $categoryId]);
            $category = $categoryStmt->fetch(PDO::FETCH_ASSOC);
            if ($category && (int)$category['retention_period_days'] > 0) {
                $retentionEndDate = date('Y-m-d', strtotime($payload['collection_date'] . ' + ' . (int)$category['retention_period_days'] . ' days'));
            }
        }

        $insert = $pdo->prepare(
            'INSERT INTO data_records (category_id, original_category_id, record_reference, data_subject_type, collection_date, retention_end_date, status, created_by)
             VALUES (:category_id, :original_category_id, :reference, :subject_type, :collection_date, :retention_end_date, "active", NULL)'
        );
        $insert->execute([
            'category_id' => $categoryId,
            'original_category_id' => $categoryId,
            'reference' => $payload['record_reference'],
            'subject_type' => $payload['data_subject_type'] ?? null,
            'collection_date' => $payload['collection_date'],
            'retention_end_date' => $retentionEndDate,
        ]);

        $recordId = (int)$pdo->lastInsertId();
        $update = $pdo->prepare('UPDATE intake_queue SET status = "completed", processed_at = NOW(), attempts = attempts + 1, record_id = :record_id, category_id = :category_id WHERE id = :id');
        $update->execute(['record_id' => $recordId, 'category_id' => $categoryId, 'id' => $item['id']]);

        if (!empty($item['system_id'])) {
            $pdo->prepare('UPDATE connected_systems SET records_synced = records_synced + 1 WHERE id = :id')
                ->execute(['id' => $item['system_id']]);
        }

        $pdo->commit();
    } catch (Throwable $e) {
        $pdo->rollBack();
        $fail = $pdo->prepare('UPDATE intake_queue SET status = "failed", error = :error, attempts = attempts + 1 WHERE id = :id');
        $fail->execute(['error' => $e->getMessage(), 'id' => $item['id']]);
    }
}

echo 'Intake queue processor completed.';
