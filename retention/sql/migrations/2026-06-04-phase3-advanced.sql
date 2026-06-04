-- ============================================================
-- ADRS Phase 3 — Advanced features (additive migration)
-- Run once on an existing deployment. New installs get these via schema.sql.
-- ============================================================

-- Tamper-evident audit log: hash-chain columns (append-only friendly; set at INSERT).
ALTER TABLE `audit_log`
  ADD COLUMN `prev_hash` CHAR(64) NULL COMMENT 'row_hash of the previous audit row',
  ADD COLUMN `row_hash`  CHAR(64) NULL COMMENT 'SHA-256 over canonical content + prev_hash';

-- Two-factor authentication (TOTP).
ALTER TABLE `users`
  ADD COLUMN `twofa_secret`   VARCHAR(64) NULL COMMENT 'Base32 TOTP secret',
  ADD COLUMN `twofa_enabled`  TINYINT(1)  NOT NULL DEFAULT 0,
  ADD COLUMN `twofa_recovery` JSON        NULL COMMENT 'Hashed one-time recovery codes';

-- RoPA / Article 30 Record of Processing Activities (one per processing activity).
CREATE TABLE IF NOT EXISTS `ropa_entries` (
  `id`                 INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `category_id`        INT UNSIGNED NULL,
  `activity_name`      VARCHAR(255) NOT NULL,
  `controller_name`    VARCHAR(255) NULL,
  `controller_contact` VARCHAR(255) NULL,
  `dpo_contact`        VARCHAR(255) NULL,
  `purpose`            TEXT NULL,
  `lawful_basis`       VARCHAR(100) NULL,
  `data_subjects`      TEXT NULL,
  `data_categories`    TEXT NULL,
  `recipients`         TEXT NULL,
  `third_country_transfers` TEXT NULL,
  `retention_summary`  VARCHAR(255) NULL,
  `security_measures`  TEXT NULL,
  `created_by`         INT UNSIGNED NULL,
  `created_at`         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_ropa_category` (`category_id`),
  CONSTRAINT `fk_ropa_category` FOREIGN KEY (`category_id`) REFERENCES `data_categories` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_ropa_creator`  FOREIGN KEY (`created_by`)  REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- DPIA — Data Protection Impact Assessments.
CREATE TABLE IF NOT EXISTS `dpia_assessments` (
  `id`            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `title`         VARCHAR(255) NOT NULL,
  `category_id`   INT UNSIGNED NULL,
  `description`   TEXT NULL,
  `necessity_score`      TINYINT NOT NULL DEFAULT 1,
  `proportionality_score`TINYINT NOT NULL DEFAULT 1,
  `likelihood_score`     TINYINT NOT NULL DEFAULT 1,
  `severity_score`       TINYINT NOT NULL DEFAULT 1,
  `risk_score`    INT NOT NULL DEFAULT 0 COMMENT 'likelihood * severity',
  `risk_level`    ENUM('low','medium','high') NOT NULL DEFAULT 'low',
  `mitigation`    TEXT NULL,
  `status`        ENUM('draft','in_review','approved','rejected') NOT NULL DEFAULT 'draft',
  `assessed_by`   INT UNSIGNED NULL,
  `approved_by`   INT UNSIGNED NULL,
  `approved_at`   TIMESTAMP NULL,
  `created_at`    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_dpia_status` (`status`),
  CONSTRAINT `fk_dpia_category` FOREIGN KEY (`category_id`) REFERENCES `data_categories` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_dpia_assessor` FOREIGN KEY (`assessed_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_dpia_approver` FOREIGN KEY (`approved_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Data breach incident register (GDPR Art. 33/34 — 72-hour notification tracking).
CREATE TABLE IF NOT EXISTS `breach_incidents` (
  `id`            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `reference`     VARCHAR(50) NOT NULL,
  `title`         VARCHAR(255) NOT NULL,
  `description`   TEXT NULL,
  `discovered_at` DATETIME NOT NULL,
  `occurred_at`   DATETIME NULL,
  `severity`      ENUM('low','medium','high','critical') NOT NULL DEFAULT 'medium',
  `affected_records` INT UNSIGNED NULL,
  `status`        ENUM('open','contained','notified','closed') NOT NULL DEFAULT 'open',
  `notify_deadline`       DATETIME NOT NULL COMMENT 'discovered_at + 72h',
  `notified_authority_at` DATETIME NULL,
  `notified_subjects_at`  DATETIME NULL,
  `reported_by`   INT UNSIGNED NULL,
  `created_at`    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_breach_ref` (`reference`),
  KEY `idx_breach_status` (`status`),
  CONSTRAINT `fk_breach_reporter` FOREIGN KEY (`reported_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Consent receipts (evidence of consent given/withdrawn).
CREATE TABLE IF NOT EXISTS `consent_receipts` (
  `id`             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `record_id`      INT UNSIGNED NULL,
  `data_subject_ref` VARCHAR(255) NOT NULL,
  `purpose`        VARCHAR(255) NOT NULL,
  `lawful_basis`   VARCHAR(100) NULL,
  `channel`        VARCHAR(100) NULL,
  `given_at`       DATETIME NOT NULL,
  `withdrawn_at`   DATETIME NULL,
  `receipt_hash`   CHAR(64) NOT NULL,
  `created_by`     INT UNSIGNED NULL,
  `created_at`     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_receipt_record` (`record_id`),
  KEY `idx_receipt_subject` (`data_subject_ref`),
  CONSTRAINT `fk_receipt_record`  FOREIGN KEY (`record_id`)  REFERENCES `data_records` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_receipt_creator` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Outbound ops webhooks (Slack/Teams/generic) for key events.
CREATE TABLE IF NOT EXISTS `webhook_endpoints` (
  `id`           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name`         VARCHAR(255) NOT NULL,
  `url`          VARCHAR(500) NOT NULL,
  `event_types`  VARCHAR(500) NOT NULL DEFAULT '*' COMMENT 'CSV of event keys or * for all',
  `is_active`    TINYINT(1) NOT NULL DEFAULT 1,
  `last_fired_at` TIMESTAMP NULL,
  `created_by`   INT UNSIGNED NULL,
  `created_at`   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_webhook_creator` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Automated database backup log.
CREATE TABLE IF NOT EXISTS `backup_log` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `filename`   VARCHAR(255) NOT NULL,
  `size_bytes` BIGINT UNSIGNED NULL,
  `status`     ENUM('success','failed') NOT NULL,
  `message`    TEXT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Phase 3 settings.
INSERT IGNORE INTO `system_settings` (`setting_key`, `setting_value`, `description`) VALUES
('white_label_name',     'ADRS — 3Consulting', 'White-label product name shown in the UI'),
('white_label_primary',  '#C85C1A',            'White-label primary colour (hex)'),
('white_label_logo_url', '',                   'White-label logo URL (optional)'),
('white_label_footer',   '3Consulting Limited','White-label footer text'),
('ops_webhooks_enabled', '0',                  'Send ops event notifications to configured webhooks'),
('backup_retention_days','30',                 'Days to keep automated DB backups');
