-- ============================================================
-- ADRS SaaS multi-tenant migration (run once on existing deployments).
-- New installs get these structures via schema.sql.
-- ============================================================

CREATE TABLE IF NOT EXISTS `organizations` (
  `id`            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name`          VARCHAR(255) NOT NULL,
  `slug`          VARCHAR(100) NOT NULL,
  `tier`          ENUM('core','enterprise') NOT NULL DEFAULT 'core',
  `status`        ENUM('active','trial','suspended') NOT NULL DEFAULT 'trial',
  `trial_ends_at` TIMESTAMP NULL,
  `created_at`    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_organizations_slug` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `organization_settings` (
  `organization_id` INT UNSIGNED NOT NULL,
  `setting_key`     VARCHAR(100) NOT NULL,
  `setting_value`   TEXT         NOT NULL,
  `description`     VARCHAR(255) NULL,
  `updated_at`      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`organization_id`, `setting_key`),
  CONSTRAINT `fk_org_settings_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Default organisation for existing single-tenant data.
INSERT IGNORE INTO `organizations` (`id`, `name`, `slug`, `tier`, `status`)
VALUES (1, 'Default Organisation', 'default', 'core', 'active');

-- Tenant-scoped tables (organization_id = 1 for legacy rows).
ALTER TABLE `users` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `data_categories` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `data_records` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `audit_log` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `notifications` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `schedule_reviews` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `pending_recalculations` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `attachments` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `dsar_requests` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `import_jobs` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `connected_systems` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `api_keys` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `field_mappings` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `auto_categorization_rules` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `integration_logs` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `intake_queue` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `disposal_dispatches` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `consent_signals` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `ropa_entries` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `dpia_assessments` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `breach_incidents` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `consent_receipts` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;
ALTER TABLE `webhook_endpoints` ADD COLUMN `organization_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`;

-- Copy global settings into org 1 (legacy installs keep working).
INSERT IGNORE INTO `organization_settings` (`organization_id`, `setting_key`, `setting_value`, `description`)
SELECT 1, `setting_key`, `setting_value`, `description` FROM `system_settings`
WHERE `setting_key` NOT IN ('deployment_mode', 'setup_complete', 'allow_public_signup');

INSERT IGNORE INTO `system_settings` (`setting_key`, `setting_value`, `description`) VALUES
('deployment_mode', 'single', 'single = one org per install; saas = multi-tenant self-service registration'),
('setup_complete', '1', 'Legacy single-tenant installs are already configured');
