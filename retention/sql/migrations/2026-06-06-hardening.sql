-- ============================================================
-- ADRS hardening migration (run once on an existing deployment).
-- New installs get these via schema.sql.
-- ============================================================

-- Brute-force login throttling.
CREATE TABLE IF NOT EXISTS `login_attempts` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `email`      VARCHAR(255) NULL,
  `ip_address` VARCHAR(45)  NULL,
  `success`    TINYINT(1)   NOT NULL DEFAULT 0,
  `created_at` TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_login_email_time` (`email`, `created_at`),
  KEY `idx_login_ip_time`    (`ip_address`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Performance index for high-volume reference lookups (API dedup + consent matching).
-- Safe to skip if it already exists.
ALTER TABLE `data_records` ADD INDEX `idx_records_reference` (`record_reference`);

-- Optional 2FA enforcement by role (empty = optional for everyone).
INSERT IGNORE INTO `system_settings` (`setting_key`, `setting_value`, `description`) VALUES
('require_2fa_roles', '', 'Comma-separated roles that MUST enable 2FA (e.g. admin,dpo). Empty = optional for all');
