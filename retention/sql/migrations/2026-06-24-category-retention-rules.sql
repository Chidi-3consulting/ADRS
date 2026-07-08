-- Multiple retention rules per data category (legal basis, purpose, institution type).
CREATE TABLE IF NOT EXISTS `category_retention_rules` (
  `id`                     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`        INT UNSIGNED NOT NULL,
  `category_id`            INT UNSIGNED NOT NULL,
  `rule_name`              VARCHAR(255) NOT NULL COMMENT 'Human label for this retention variant',
  `legal_basis`            ENUM(
                             'legal_obligation','contract','consent',
                             'legitimate_interest','vital_interest','public_task'
                           ) NOT NULL,
  `processing_purpose`     VARCHAR(500) NULL COMMENT 'What the data is used for',
  `institution_type`       ENUM(
                             'all','banking','insurance','healthcare',
                             'public_sector','telecom','retail','general'
                           ) NOT NULL DEFAULT 'all',
  `retention_period_days`  INT UNSIGNED NOT NULL DEFAULT 0,
  `retention_period_label` VARCHAR(100) NOT NULL,
  `disposal_method`        ENUM('delete','anonymise','archive') NOT NULL DEFAULT 'delete',
  `disposal_trigger`       ENUM('date_based','consent_withdrawal') NOT NULL DEFAULT 'date_based',
  `requires_dual_approval` TINYINT(1)   NOT NULL DEFAULT 0,
  `is_default`             TINYINT(1)   NOT NULL DEFAULT 0,
  `sort_order`             INT UNSIGNED NOT NULL DEFAULT 0,
  `is_active`              TINYINT(1)   NOT NULL DEFAULT 1,
  `created_at`             TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`             TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_crr_category` (`category_id`),
  KEY `idx_crr_org` (`organization_id`),
  CONSTRAINT `fk_crr_category` FOREIGN KEY (`category_id`) REFERENCES `data_categories` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `data_records`
  ADD COLUMN `retention_rule_id` INT UNSIGNED NULL AFTER `category_id`,
  ADD KEY `idx_records_retention_rule` (`retention_rule_id`),
  ADD CONSTRAINT `fk_records_retention_rule`
    FOREIGN KEY (`retention_rule_id`) REFERENCES `category_retention_rules` (`id`) ON DELETE SET NULL;

-- Seed one default rule per existing category from legacy columns.
INSERT INTO `category_retention_rules`
  (`organization_id`, `category_id`, `rule_name`, `legal_basis`, `processing_purpose`, `institution_type`,
   `retention_period_days`, `retention_period_label`, `disposal_method`, `disposal_trigger`,
   `requires_dual_approval`, `is_default`, `sort_order`, `is_active`)
SELECT
  dc.organization_id, dc.id, 'Default retention', dc.legal_basis, NULL, 'all',
  dc.retention_period_days, dc.retention_period_label, dc.disposal_method, dc.disposal_trigger,
  dc.requires_dual_approval, 1, 0, 1
FROM `data_categories` dc
WHERE dc.deleted_at IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM `category_retention_rules` r WHERE r.category_id = dc.id
  );

UPDATE `data_records` dr
JOIN `category_retention_rules` crr ON crr.category_id = dr.category_id AND crr.is_default = 1
SET dr.retention_rule_id = crr.id
WHERE dr.retention_rule_id IS NULL;

ALTER TABLE `notifications`
  MODIFY COLUMN `type` ENUM(
    'review_due','disposal_due','disposal_requested',
    'disposal_approved','disposal_rejected',
    'legal_hold_set','legal_hold_lifted',
    'quarterly_review','disposal_confirmation',
    'consent_withdrawal_due','escalation_alert',
    'recalculation_pending','bulk_import_complete',
    'dsar_received','dsar_due_soon','dsar_overdue',
    'record_created_by_owner','password_reset',
    'onboarding_setup'
  ) NOT NULL;
