<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';

/** Organisation-type labels for retention rule scoping. */
function institution_type_options(): array {
    return [
        'all'           => 'All organisation types',
        'banking'       => 'Banking / financial services',
        'insurance'     => 'Insurance',
        'healthcare'    => 'Healthcare',
        'public_sector' => 'Public sector',
        'telecom'       => 'Telecom',
        'retail'        => 'Retail / e-commerce',
        'general'       => 'General / other',
    ];
}

function institution_type_label(string $type): string {
    return institution_type_options()[$type] ?? ucfirst(str_replace('_', ' ', $type));
}

/** Ensure every category has at least one default rule (migrates legacy column data). */
function ensure_category_default_rule(PDO $pdo, int $categoryId): int {
    $stmt = $pdo->prepare(
        "SELECT id FROM category_retention_rules
         WHERE category_id = :cid AND is_default = 1 AND is_active = 1 LIMIT 1"
    );
    $stmt->execute(['cid' => $categoryId]);
    $existing = $stmt->fetch();
    if ($existing) { return (int) $existing['id']; }

    $cat = $pdo->prepare("SELECT * FROM data_categories WHERE id = :id AND deleted_at IS NULL LIMIT 1");
    $cat->execute(['id' => $categoryId]);
    $row = $cat->fetch();
    if (!$row) { throw new RuntimeException('Category not found'); }

    return create_retention_rule($pdo, $categoryId, [
        'rule_name'              => 'Default retention',
        'legal_basis'            => $row['legal_basis'],
        'processing_purpose'     => null,
        'institution_type'       => 'all',
        'retention_period_days'  => (int) $row['retention_period_days'],
        'retention_period_label' => $row['retention_period_label'],
        'disposal_method'        => $row['disposal_method'],
        'disposal_trigger'       => $row['disposal_trigger'],
        'requires_dual_approval' => (int) $row['requires_dual_approval'],
        'is_default'             => 1,
    ]);
}

/** All active rules for a category, default first. */
function list_category_retention_rules(PDO $pdo, int $categoryId, bool $activeOnly = true): array {
    ensure_category_default_rule($pdo, $categoryId);
    $sql = 'SELECT * FROM category_retention_rules WHERE category_id = :cid';
    if ($activeOnly) { $sql .= ' AND is_active = 1'; }
    $sql .= ' ORDER BY is_default DESC, sort_order ASC, id ASC';
    $stmt = $pdo->prepare($sql);
    $stmt->execute(['cid' => $categoryId]);
    return $stmt->fetchAll();
}

function fetch_retention_rule(PDO $pdo, int $ruleId): ?array {
    $orgId = function_exists('current_org_id') ? current_org_id() : null;
    if ($orgId !== null) {
        $stmt = $pdo->prepare(
            "SELECT * FROM category_retention_rules
             WHERE id = :id AND organization_id = :o AND is_active = 1 LIMIT 1"
        );
        $stmt->execute(['id' => $ruleId, 'o' => $orgId]);
    } else {
        $stmt = $pdo->prepare("SELECT * FROM category_retention_rules WHERE id = :id AND is_active = 1 LIMIT 1");
        $stmt->execute(['id' => $ruleId]);
    }
    $row = $stmt->fetch();
    return $row === false ? null : $row;
}

/** Default rule for a category. */
function fetch_default_retention_rule(PDO $pdo, int $categoryId): ?array {
    ensure_category_default_rule($pdo, $categoryId);
    $stmt = $pdo->prepare(
        "SELECT * FROM category_retention_rules
         WHERE category_id = :cid AND is_default = 1 AND is_active = 1 LIMIT 1"
    );
    $stmt->execute(['cid' => $categoryId]);
    $row = $stmt->fetch();
    return $row === false ? null : $row;
}

/** Resolve rule for a record (explicit rule id or category default). */
function resolve_record_retention_rule(PDO $pdo, int $categoryId, ?int $ruleId = null): array {
    if ($ruleId !== null && $ruleId > 0) {
        $rule = fetch_retention_rule($pdo, $ruleId);
        if ($rule === null || (int) $rule['category_id'] !== $categoryId) {
            throw new InvalidArgumentException('Selected retention rule is not valid for this category.');
        }
        return $rule;
    }
    $rule = fetch_default_retention_rule($pdo, $categoryId);
    if ($rule === null) {
        throw new InvalidArgumentException('No retention rule configured for this category.');
    }
    return $rule;
}

/** Rule array → shape used by compute_retention_end and engine (backward compatible). */
function retention_rule_as_category(array $rule): array {
    return [
        'disposal_trigger'       => $rule['disposal_trigger'],
        'retention_period_days'  => (int) $rule['retention_period_days'],
        'retention_period_label' => $rule['retention_period_label'],
        'disposal_method'        => $rule['disposal_method'],
        'requires_dual_approval' => (int) $rule['requires_dual_approval'],
        'legal_basis'            => $rule['legal_basis'],
    ];
}

/** Count rules per category for list views. */
function count_rules_by_category(PDO $pdo, array $categoryIds): array {
    if (!$categoryIds) { return []; }
    $place = implode(',', array_fill(0, count($categoryIds), '?'));
    $stmt = $pdo->prepare(
        "SELECT category_id, COUNT(*) AS c FROM category_retention_rules
         WHERE category_id IN ($place) AND is_active = 1 GROUP BY category_id"
    );
    $stmt->execute(array_values($categoryIds));
    $out = [];
    foreach ($stmt->fetchAll() as $r) { $out[(int) $r['category_id']] = (int) $r['c']; }
    return $out;
}

/** Create a retention rule; syncs legacy category columns when is_default. Returns rule id. */
function create_retention_rule(PDO $pdo, int $categoryId, array $in): int {
    $catStmt = $pdo->prepare("SELECT organization_id FROM data_categories WHERE id = :id AND deleted_at IS NULL LIMIT 1");
    $catStmt->execute(['id' => $categoryId]);
    $cat = $catStmt->fetch();
    if (!$cat) { throw new RuntimeException('Category not found'); }

    $trigger = ($in['disposal_trigger'] ?? 'date_based') === 'consent_withdrawal' ? 'consent_withdrawal' : 'date_based';
    $days = $trigger === 'consent_withdrawal' ? 0 : max(0, (int) ($in['retention_period_days'] ?? 0));
    $isDefault = !empty($in['is_default']);

    if ($isDefault) {
        $pdo->prepare('UPDATE category_retention_rules SET is_default = 0 WHERE category_id = :cid')
            ->execute(['cid' => $categoryId]);
    }

    $stmt = $pdo->prepare(
        "INSERT INTO category_retention_rules
           (organization_id, category_id, rule_name, legal_basis, processing_purpose, institution_type,
            retention_period_days, retention_period_label, disposal_method, disposal_trigger,
            requires_dual_approval, is_default, sort_order, is_active)
         VALUES (:oid,:cid,:name,:lb,:purpose,:inst,:days,:label,:dm,:dt,:dual,:def,:sort,1)"
    );
    $stmt->execute([
        'oid'     => (int) $cat['organization_id'],
        'cid'     => $categoryId,
        'name'    => trim((string) ($in['rule_name'] ?? 'Retention rule')),
        'lb'      => $in['legal_basis'] ?? 'legal_obligation',
        'purpose' => ($in['processing_purpose'] ?? '') !== '' ? trim((string) $in['processing_purpose']) : null,
        'inst'    => $in['institution_type'] ?? 'all',
        'days'    => $days,
        'label'   => $in['retention_period_label'] ?? ($days > 0 ? "$days days" : 'Until consent withdrawn'),
        'dm'      => $in['disposal_method'] ?? 'delete',
        'dt'      => $trigger,
        'dual'    => !empty($in['requires_dual_approval']) ? 1 : 0,
        'def'     => $isDefault ? 1 : 0,
        'sort'    => (int) ($in['sort_order'] ?? 0),
    ]);
    $id = (int) $pdo->lastInsertId();

    if ($isDefault) {
        sync_category_from_default_rule($pdo, $categoryId);
    }
    return $id;
}

/** Update a rule; syncs category when default rule changes. */
function update_retention_rule(PDO $pdo, int $ruleId, array $in): void {
    $rule = fetch_retention_rule($pdo, $ruleId);
    if ($rule === null) { throw new RuntimeException('Rule not found'); }

    $trigger = ($in['disposal_trigger'] ?? $rule['disposal_trigger']) === 'consent_withdrawal' ? 'consent_withdrawal' : 'date_based';
    $days = $trigger === 'consent_withdrawal' ? 0 : max(0, (int) ($in['retention_period_days'] ?? $rule['retention_period_days']));

    $pdo->prepare(
        "UPDATE category_retention_rules SET
           rule_name=:name, legal_basis=:lb, processing_purpose=:purpose, institution_type=:inst,
           retention_period_days=:days, retention_period_label=:label, disposal_method=:dm,
           disposal_trigger=:dt, requires_dual_approval=:dual, sort_order=:sort
         WHERE id=:id"
    )->execute([
        'name'    => trim((string) ($in['rule_name'] ?? $rule['rule_name'])),
        'lb'      => $in['legal_basis'] ?? $rule['legal_basis'],
        'purpose' => array_key_exists('processing_purpose', $in)
            ? (($in['processing_purpose'] ?? '') !== '' ? trim((string) $in['processing_purpose']) : null)
            : $rule['processing_purpose'],
        'inst'    => $in['institution_type'] ?? $rule['institution_type'],
        'days'    => $days,
        'label'   => $in['retention_period_label'] ?? $rule['retention_period_label'],
        'dm'      => $in['disposal_method'] ?? $rule['disposal_method'],
        'dt'      => $trigger,
        'dual'    => !empty($in['requires_dual_approval']) ? 1 : 0,
        'sort'    => (int) ($in['sort_order'] ?? $rule['sort_order']),
        'id'      => $ruleId,
    ]);

    if ((int) $rule['is_default'] === 1) {
        sync_category_from_default_rule($pdo, (int) $rule['category_id']);
    }
}

/** Deactivate a non-default rule (blocked if records reference it). */
function deactivate_retention_rule(PDO $pdo, int $ruleId): bool {
    $rule = fetch_retention_rule($pdo, $ruleId);
    if ($rule === null || (int) $rule['is_default'] === 1) { return false; }
    $used = $pdo->prepare(
        "SELECT COUNT(*) FROM data_records WHERE retention_rule_id = :rid AND deleted_at IS NULL AND status != 'disposed'"
    );
    $used->execute(['rid' => $ruleId]);
    if ((int) $used->fetchColumn() > 0) { return false; }
    $pdo->prepare('UPDATE category_retention_rules SET is_active = 0 WHERE id = :id')->execute(['id' => $ruleId]);
    return true;
}

/** Keep legacy data_categories columns aligned with the default rule (list views, exports). */
function sync_category_from_default_rule(PDO $pdo, int $categoryId): void {
    $rule = fetch_default_retention_rule($pdo, $categoryId);
    if ($rule === null) { return; }
    $pdo->prepare(
        "UPDATE data_categories SET
           legal_basis=:lb, retention_period_days=:days, retention_period_label=:label,
           disposal_method=:dm, disposal_trigger=:dt, requires_dual_approval=:dual
         WHERE id=:id"
    )->execute([
        'lb'    => $rule['legal_basis'],
        'days'  => (int) $rule['retention_period_days'],
        'label' => $rule['retention_period_label'],
        'dm'    => $rule['disposal_method'],
        'dt'    => $rule['disposal_trigger'],
        'dual'  => (int) $rule['requires_dual_approval'],
        'id'    => $categoryId,
    ]);
}

/** Clone rules when provisioning categories for a new tenant. */
function clone_category_retention_rules(PDO $pdo, int $fromCategoryId, int $toCategoryId, int $orgId): void {
    $stmt = $pdo->prepare(
        "SELECT * FROM category_retention_rules WHERE category_id = :from AND is_active = 1 ORDER BY sort_order, id"
    );
    $stmt->execute(['from' => $fromCategoryId]);
    foreach ($stmt->fetchAll() as $r) {
        create_retention_rule($pdo, $toCategoryId, [
            'rule_name'              => $r['rule_name'],
            'legal_basis'            => $r['legal_basis'],
            'processing_purpose'     => $r['processing_purpose'],
            'institution_type'       => $r['institution_type'],
            'retention_period_days'  => (int) $r['retention_period_days'],
            'retention_period_label' => $r['retention_period_label'],
            'disposal_method'        => $r['disposal_method'],
            'disposal_trigger'       => $r['disposal_trigger'],
            'requires_dual_approval' => (int) $r['requires_dual_approval'],
            'is_default'             => (int) $r['is_default'],
            'sort_order'             => (int) $r['sort_order'],
        ]);
    }
}
