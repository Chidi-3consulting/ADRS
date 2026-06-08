-- ============================================================
-- 3Consulting ADRS — Database Schema v4 (AUDIT-FIXED)
-- Fixes: BUG-01 password_resets table, BUG-06 DSAR FK
-- MySQL 8.0 | utf8mb4 | InnoDB
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------------------------------------
-- 1. USERS
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
  `id`            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name`          VARCHAR(255) NOT NULL,
  `email`         VARCHAR(255) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `role`          ENUM('admin','dpo','data_owner') NOT NULL DEFAULT 'data_owner',
  `is_active`     TINYINT(1)   NOT NULL DEFAULT 1,
  `last_login_at` TIMESTAMP    NULL,
  `created_at`    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted_at`    TIMESTAMP    NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 2. PASSWORD RESETS  ← BUG-01 FIX: was missing entirely
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `password_resets` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `email`      VARCHAR(255) NOT NULL,
  `token_hash` VARCHAR(64)  NOT NULL COMMENT 'SHA-256 hash of the raw token sent by email',
  `expires_at` TIMESTAMP    NOT NULL COMMENT 'Valid for 1 hour from creation',
  `used`       TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '1 = token consumed, cannot be reused',
  `created_at` TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_resets_email`   (`email`),
  KEY `idx_resets_expires` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 3. DATA CATEGORIES
--    BUG-03 FIX: disposal_trigger + requires_dual_approval
--    are explicit columns — seed file sets them correctly
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `data_categories` (
  `id`                     INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `name`                   VARCHAR(255)  NOT NULL,
  `description`            TEXT,
  `compliance_framework`   ENUM('GDPR','NDPR','BOTH') NOT NULL DEFAULT 'GDPR',
  `legal_basis`            ENUM(
                             'legal_obligation','contract','consent',
                             'legitimate_interest','vital_interest','public_task'
                           ) NOT NULL,
  `retention_period_days`  INT UNSIGNED  NOT NULL DEFAULT 0
                             COMMENT '0 means disposal_trigger=consent_withdrawal',
  `retention_period_label` VARCHAR(100)  NOT NULL,
  `disposal_method`        ENUM('delete','anonymise','archive') NOT NULL DEFAULT 'delete',
  `disposal_trigger`       ENUM('date_based','consent_withdrawal') NOT NULL DEFAULT 'date_based'
                             COMMENT 'BUG-02 FIX: explicitly set in seed — no UPDATE needed',
  `requires_dual_approval` TINYINT(1)    NOT NULL DEFAULT 0
                             COMMENT 'BUG-02 FIX: explicitly set in seed for sensitive categories',
  `owner_id`               INT UNSIGNED  NULL,
  `review_frequency`       ENUM('monthly','quarterly','annually') NOT NULL DEFAULT 'quarterly',
  `source`                 ENUM('seeded','custom') NOT NULL DEFAULT 'custom',
  `is_active`              TINYINT(1)    NOT NULL DEFAULT 1,
  `created_at`             TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`             TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted_at`             TIMESTAMP     NULL,
  PRIMARY KEY (`id`),
  KEY `idx_categories_framework`        (`compliance_framework`),
  KEY `idx_categories_owner`            (`owner_id`),
  KEY `idx_categories_disposal_trigger` (`disposal_trigger`),
  KEY `idx_categories_dual_approval`    (`requires_dual_approval`),
  CONSTRAINT `fk_categories_owner`
    FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 4. DATA RECORDS
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `data_records` (
  `id`                      INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `category_id`             INT UNSIGNED  NOT NULL,
  `original_category_id`    INT UNSIGNED  NULL
                              COMMENT 'B3: set on first reassignment, never overwritten',
  `record_reference`        VARCHAR(255)  NOT NULL,
  `data_subject_type`       VARCHAR(100)  NULL,
  `collection_date`         DATE          NOT NULL,
  `retention_end_date`      DATE          NULL
                              COMMENT 'NULL for consent_withdrawal until withdrawal logged',
  `status`                  ENUM(
                              'active',
                              'due_review',
                              'disposal_requested',
                              'legal_hold',
                              'disposed'
                            ) NOT NULL DEFAULT 'active',
  `created_by_owner`        TINYINT(1)    NOT NULL DEFAULT 0,
  `consent_withdrawn_at`    TIMESTAMP     NULL,
  `consent_withdrawn_by`    INT UNSIGNED  NULL,
  `category_reassigned_at`  TIMESTAMP     NULL,
  `category_reassigned_by`  INT UNSIGNED  NULL,
  `disposal_requested_at`   TIMESTAMP     NULL,
  `disposal_requested_by`   INT UNSIGNED  NULL,
  `review_flagged_at`       TIMESTAMP     NULL,
  `escalation_sent_at`      TIMESTAMP     NULL,
  `legal_hold`              TINYINT(1)    NOT NULL DEFAULT 0,
  `legal_hold_reason`       TEXT          NULL,
  `legal_hold_by`           INT UNSIGNED  NULL,
  `legal_hold_at`           TIMESTAMP     NULL,
  `legal_hold_lifted_at`    TIMESTAMP     NULL,
  `disposed_at`             TIMESTAMP     NULL,
  `disposed_by`             INT UNSIGNED  NULL,
  `notes`                   TEXT          NULL,
  `created_by`              INT UNSIGNED  NULL,
  `created_at`              TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`              TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted_at`              TIMESTAMP     NULL,
  PRIMARY KEY (`id`),
  KEY `idx_records_category`           (`category_id`),
  KEY `idx_records_status`             (`status`),
  KEY `idx_records_retention_end`      (`retention_end_date`),
  KEY `idx_records_legal_hold`         (`legal_hold`),
  KEY `idx_records_review_flagged`     (`review_flagged_at`),
  KEY `idx_records_consent_withdrawn`  (`consent_withdrawn_at`),
  KEY `idx_records_escalation`         (`escalation_sent_at`),
  CONSTRAINT `fk_records_category`          FOREIGN KEY (`category_id`)           REFERENCES `data_categories` (`id`),
  CONSTRAINT `fk_records_orig_category`     FOREIGN KEY (`original_category_id`)  REFERENCES `data_categories` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_records_hold_by`           FOREIGN KEY (`legal_hold_by`)         REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_records_disposed_by`       FOREIGN KEY (`disposed_by`)           REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_records_created_by`        FOREIGN KEY (`created_by`)            REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_records_consent_by`        FOREIGN KEY (`consent_withdrawn_by`)  REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_records_disposal_req_by`   FOREIGN KEY (`disposal_requested_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_records_reassigned_by`     FOREIGN KEY (`category_reassigned_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 5. AUDIT LOG (append-only — REVOKE UPDATE/DELETE after setup)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `audit_log` (
  `id`           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `action`       ENUM(
                   'record_created','record_updated','record_flagged_review',
                   'record_disposed_delete','record_disposed_anonymise','record_disposed_archive',
                   'record_reassigned','consent_withdrawn',
                   'disposal_requested','disposal_request_approved','disposal_request_rejected',
                   'legal_hold_set','legal_hold_lifted',
                   'category_created','category_updated','category_deleted',
                   'recalculation_reviewed',
                   'user_created','user_updated','user_deleted',
                   'notification_sent','schedule_reviewed',
                   'user_login','user_logout','export_generated',
                   'bulk_import','escalation_sent',
                   'attachment_uploaded','attachment_deleted',
                   'dsar_created','dsar_updated','dsar_completed',
                   'password_reset_requested','password_reset_completed'
                 ) NOT NULL,
  `entity_type`  ENUM('data_record','data_category','user','notification',
                      'attachment','dsar','system') NOT NULL,
  `entity_id`    INT UNSIGNED  NULL,
  `performed_by` INT UNSIGNED  NULL COMMENT 'NULL = automated cron',
  `details`      JSON          NULL,
  `ip_address`   VARCHAR(45)   NULL,
  `created_at`   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_audit_action`       (`action`),
  KEY `idx_audit_entity`       (`entity_type`, `entity_id`),
  KEY `idx_audit_performed_by` (`performed_by`),
  KEY `idx_audit_created_at`   (`created_at`),
  CONSTRAINT `fk_audit_performed_by`
    FOREIGN KEY (`performed_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 6. NOTIFICATIONS
--    BUG-06 FIX: added FK constraint for related_dsar_id
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `notifications` (
  `id`                INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `recipient_id`      INT UNSIGNED  NOT NULL,
  `type`              ENUM(
                        'review_due','disposal_due','disposal_requested',
                        'disposal_approved','disposal_rejected',
                        'legal_hold_set','legal_hold_lifted',
                        'quarterly_review','disposal_confirmation',
                        'consent_withdrawal_due','escalation_alert',
                        'recalculation_pending','bulk_import_complete',
                        'dsar_received','dsar_due_soon','dsar_overdue',
                        'record_created_by_owner','password_reset'
                      ) NOT NULL,
  `related_record_id` INT UNSIGNED  NULL,
  `related_dsar_id`   INT UNSIGNED  NULL COMMENT 'BUG-06 FIX: FK added below',
  `subject`           VARCHAR(255)  NOT NULL,
  `message`           TEXT          NOT NULL,
  `owner_missing`     TINYINT(1)    NOT NULL DEFAULT 0,
  `status`            ENUM('sent','failed','pending') NOT NULL DEFAULT 'pending',
  `read_at`           TIMESTAMP     NULL,
  `sent_at`           TIMESTAMP     NULL,
  `attempts`          TINYINT       NOT NULL DEFAULT 0,
  `created_at`        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_notifications_recipient` (`recipient_id`),
  KEY `idx_notifications_type`      (`type`),
  KEY `idx_notifications_read`      (`read_at`),
  KEY `idx_notifications_status`    (`status`),
  CONSTRAINT `fk_notifications_recipient`
    FOREIGN KEY (`recipient_id`)      REFERENCES `users` (`id`),
  CONSTRAINT `fk_notifications_record`
    FOREIGN KEY (`related_record_id`) REFERENCES `data_records` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_notifications_dsar`
    FOREIGN KEY (`related_dsar_id`)   REFERENCES `dsar_requests` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 7. SCHEDULE REVIEWS
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `schedule_reviews` (
  `id`               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `category_id`      INT UNSIGNED NOT NULL,
  `reviewed_by`      INT UNSIGNED NOT NULL,
  `review_date`      DATE         NOT NULL,
  `outcome`          ENUM('no_change','updated','flagged','escalated') NOT NULL DEFAULT 'no_change',
  `notes`            TEXT         NULL,
  `next_review_date` DATE         NULL,
  `created_at`       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_reviews_category` (`category_id`),
  KEY `idx_reviews_reviewer` (`reviewed_by`),
  KEY `idx_reviews_date`     (`review_date`),
  CONSTRAINT `fk_reviews_category` FOREIGN KEY (`category_id`) REFERENCES `data_categories` (`id`),
  CONSTRAINT `fk_reviews_reviewer` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 8. PENDING RECALCULATIONS (B2)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `pending_recalculations` (
  `id`                     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `record_id`              INT UNSIGNED NOT NULL,
  `category_id`            INT UNSIGNED NOT NULL,
  `old_retention_end_date` DATE         NOT NULL,
  `new_retention_end_date` DATE         NOT NULL,
  `triggered_by`           INT UNSIGNED NULL,
  `status`                 ENUM('pending','recalculate','keep_original','ignored') NOT NULL DEFAULT 'pending',
  `reviewed_by`            INT UNSIGNED NULL,
  `reviewed_at`            TIMESTAMP    NULL,
  `created_at`             TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_recalc_record`  (`record_id`),
  KEY `idx_recalc_status`  (`status`),
  KEY `idx_recalc_category`(`category_id`),
  CONSTRAINT `fk_recalc_record`    FOREIGN KEY (`record_id`)   REFERENCES `data_records` (`id`),
  CONSTRAINT `fk_recalc_category`  FOREIGN KEY (`category_id`) REFERENCES `data_categories` (`id`),
  CONSTRAINT `fk_recalc_triggered` FOREIGN KEY (`triggered_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_recalc_reviewed`  FOREIGN KEY (`reviewed_by`)  REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 9. ATTACHMENTS (S8) — stored outside public_html
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `attachments` (
  `id`                INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `record_id`         INT UNSIGNED  NOT NULL,
  `original_filename` VARCHAR(255)  NOT NULL,
  `stored_filename`   VARCHAR(255)  NOT NULL COMMENT 'UUID-based, no path traversal possible',
  `file_size`         INT UNSIGNED  NOT NULL COMMENT 'Bytes',
  `mime_type`         VARCHAR(100)  NOT NULL,
  `uploaded_by`       INT UNSIGNED  NULL,
  `created_at`        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `deleted_at`        TIMESTAMP     NULL,
  PRIMARY KEY (`id`),
  KEY `idx_attachments_record` (`record_id`),
  KEY `idx_attachments_uploader` (`uploaded_by`),
  CONSTRAINT `fk_attachments_record`   FOREIGN KEY (`record_id`)   REFERENCES `data_records` (`id`),
  CONSTRAINT `fk_attachments_uploader` FOREIGN KEY (`uploaded_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 10. DSAR REQUESTS (C1)
--     NOTE: notifications.related_dsar_id FK references this table
--     Defined before notifications table for FK resolution
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `dsar_requests` (
  `id`                    INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `reference`             VARCHAR(100)  NOT NULL COMMENT 'DSAR-YYYY-NNNN auto-generated',
  `request_type`          ENUM(
                            'access','rectification','erasure',
                            'restriction','portability','objection'
                          ) NOT NULL,
  `compliance_framework`  ENUM('GDPR','NDPR','BOTH') NOT NULL DEFAULT 'GDPR',
  `data_subject_name`     VARCHAR(255)  NOT NULL,
  `data_subject_email`    VARCHAR(255)  NULL,
  `data_subject_phone`    VARCHAR(50)   NULL,
  `data_subject_type`     VARCHAR(100)  NULL,
  `identity_verified`     TINYINT(1)    NOT NULL DEFAULT 0,
  `identity_verified_at`  TIMESTAMP     NULL,
  `identity_verified_by`  INT UNSIGNED  NULL,
  `received_date`         DATE          NOT NULL,
  `due_date`              DATE          NOT NULL COMMENT 'received_date + 30 days (GDPR Art.12)',
  `extended_due_date`     DATE          NULL,
  `extension_reason`      TEXT          NULL,
  `status`                ENUM(
                            'open','identity_check','in_progress',
                            'completed','rejected','extended'
                          ) NOT NULL DEFAULT 'open',
  `assigned_to`           INT UNSIGNED  NULL,
  `description`           TEXT          NULL,
  `internal_notes`        TEXT          NULL,
  `response_notes`        TEXT          NULL,
  `completed_at`          TIMESTAMP     NULL,
  `rejection_reason`      TEXT          NULL,
  `created_by`            INT UNSIGNED  NULL,
  `created_at`            TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_dsar_reference` (`reference`),
  KEY `idx_dsar_status`   (`status`),
  KEY `idx_dsar_due_date` (`due_date`),
  KEY `idx_dsar_assigned` (`assigned_to`),
  KEY `idx_dsar_type`     (`request_type`),
  CONSTRAINT `fk_dsar_assigned`    FOREIGN KEY (`assigned_to`)          REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_dsar_created_by`  FOREIGN KEY (`created_by`)           REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_dsar_verified_by` FOREIGN KEY (`identity_verified_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 11. BULK IMPORT JOBS (B8)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `import_jobs` (
  `id`            INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `imported_by`   INT UNSIGNED  NOT NULL,
  `filename`      VARCHAR(255)  NOT NULL,
  `total_rows`    INT UNSIGNED  NOT NULL DEFAULT 0,
  `valid_rows`    INT UNSIGNED  NOT NULL DEFAULT 0,
  `imported_rows` INT UNSIGNED  NOT NULL DEFAULT 0,
  `skipped_rows`  INT UNSIGNED  NOT NULL DEFAULT 0,
  `error_rows`    INT UNSIGNED  NOT NULL DEFAULT 0,
  `status`        ENUM('pending','validated','imported','failed') NOT NULL DEFAULT 'pending',
  `error_report`  JSON          NULL,
  `created_at`    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `completed_at`  TIMESTAMP     NULL,
  PRIMARY KEY (`id`),
  KEY `idx_import_user`   (`imported_by`),
  KEY `idx_import_status` (`status`),
  CONSTRAINT `fk_import_user` FOREIGN KEY (`imported_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 12. SYSTEM SETTINGS
--     BUG-08 FIX: SMTP lives HERE (DB) — mailer.php reads
--     from this table at runtime, NOT from config constants.
--     Config constants are ONLY for DB connection and app identity.
--     System settings page updates this table.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `system_settings` (
  `setting_key`   VARCHAR(100) NOT NULL,
  `setting_value` TEXT         NOT NULL,
  `description`   VARCHAR(255) NULL,
  `updated_at`    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`setting_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `system_settings` (`setting_key`, `setting_value`, `description`) VALUES
-- BUG-08 FIX: SMTP is source of truth in this table.
-- mailer.php reads these via get_setting($pdo, 'smtp_host') etc.
-- config.php ONLY defines DB credentials + APP_URL + APP_ENV.
('smtp_host',             'mail.yourdomain.com',               'SMTP host — set after creating cPanel email account'),
('smtp_port',             '465',                               'SMTP port (465=SSL, 587=TLS)'),
('smtp_user',             'noreply@retention.3consult-ng.com', 'SMTP username / From address'),
('smtp_pass',             '',                                  'SMTP password — set via Settings page after deploy'),
('smtp_from_name',        '3Consulting Data Retention System', 'Sender display name'),
('smtp_encryption',       'ssl',                               'ssl or tls or empty for local Mailpit'),
('smtp_debug',            '0',                                 '0=off, 2=full debug (local only)'),
-- Retention engine settings
('review_alert_days',     '30',                                'Days before end date to flag record for review'),
('escalation_days',       '14',                                'B7: Days of inaction before escalating to Admin'),
('consent_disposal_days', '30',                                'B1: Days after consent withdrawal to auto-dispose'),
-- Attachments
('attachment_max_size_mb','10',                                'S8: Max file size per attachment in MB'),
('attachment_allowed_types','pdf,doc,docx,xls,xlsx,jpg,jpeg,png', 'S8: Allowed file extensions'),
-- DSAR
('dsar_response_days',    '30',                                'C1: GDPR Art.12 initial response deadline in days'),
('dsar_extension_days',   '60',                                'C1: Max extension period in days'),
-- Import
('max_import_rows',       '500',                               'B8: Max rows per bulk CSV upload'),
-- Display
('rows_per_page',         '25',                                'Default pagination rows'),
('app_name',              '3Consulting Data Retention System', 'Application display name'),
('timezone',              'Africa/Lagos',                      'System timezone for display');

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------------------------------------
-- POST-INSTALL SECURITY (run manually after DB user creation)
-- ----------------------------------------------------------
-- REVOKE UPDATE, DELETE ON your_db.audit_log FROM 'app_user'@'localhost';
-- FLUSH PRIVILEGES;

-- ============================================================
-- ENTERPRISE TIER TABLES (v2 — Two-Tier ADRS)
-- Only active when system_settings.adrs_tier = 'enterprise'
-- ============================================================

-- ----------------------------------------------------------
-- E1. CONNECTED SYSTEMS
-- Registry of every external system integrated with ADRS
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `connected_systems` (
  `id`              INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `name`            VARCHAR(255)  NOT NULL COMMENT 'Human label e.g. "Salesforce CRM"',
  `system_type`     ENUM(
                      'crm','core_banking','hr_platform','customer_db',
                      'loan_management','ecommerce','custom'
                    ) NOT NULL DEFAULT 'custom',
  `base_url`        VARCHAR(500)  NULL COMMENT 'Base URL of the external system API if bidirectional',
  `description`     TEXT          NULL,
  `is_active`       TINYINT(1)    NOT NULL DEFAULT 1,
  `health_status`   ENUM('healthy','degraded','offline','unknown') NOT NULL DEFAULT 'unknown',
  `last_ping_at`    TIMESTAMP     NULL,
  `records_synced`  INT UNSIGNED  NOT NULL DEFAULT 0 COMMENT 'Total records ever received from this system',
  `created_by`      INT UNSIGNED  NULL,
  `created_at`      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_systems_type`   (`system_type`),
  KEY `idx_systems_active` (`is_active`),
  CONSTRAINT `fk_systems_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- E2. API KEYS
-- Authentication tokens for external systems calling ADRS API
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `api_keys` (
  `id`               INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `system_id`        INT UNSIGNED  NOT NULL COMMENT 'Which connected system owns this key',
  `key_name`         VARCHAR(100)  NOT NULL COMMENT 'Human label e.g. "Production Key"',
  `key_hash`         VARCHAR(64)   NOT NULL COMMENT 'SHA-256 of the raw key — raw key shown once at creation',
  `key_prefix`       VARCHAR(12)   NOT NULL COMMENT 'First 8 chars of raw key for display e.g. "adrs_k1_"',
  `permissions`      JSON          NULL COMMENT '["ingest","batch","consent","health","categories"]',
  `rate_limit_per_min` INT UNSIGNED NOT NULL DEFAULT 60,
  `is_active`        TINYINT(1)    NOT NULL DEFAULT 1,
  `last_used_at`     TIMESTAMP     NULL,
  `expires_at`       TIMESTAMP     NULL COMMENT 'NULL = never expires',
  `created_by`       INT UNSIGNED  NULL,
  `created_at`       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `revoked_at`       TIMESTAMP     NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_api_key_hash` (`key_hash`),
  KEY `idx_api_keys_system`  (`system_id`),
  KEY `idx_api_keys_prefix`  (`key_prefix`),
  CONSTRAINT `fk_api_keys_system`     FOREIGN KEY (`system_id`)  REFERENCES `connected_systems` (`id`),
  CONSTRAINT `fk_api_keys_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- E3. FIELD MAPPINGS
-- Maps external system fields to ADRS data categories + fields
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `field_mappings` (
  `id`                   INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `system_id`            INT UNSIGNED  NOT NULL,
  `external_object_type` VARCHAR(100)  NOT NULL COMMENT 'e.g. "customer", "loan_application", "employee"',
  `category_id`          INT UNSIGNED  NOT NULL COMMENT 'Maps to this ADRS data category',
  `external_field`       VARCHAR(255)  NOT NULL COMMENT 'Field name in external system e.g. "customer_name"',
  `adrs_field`           VARCHAR(100)  NOT NULL COMMENT 'ADRS field to map to e.g. "record_reference"',
  `transform`            VARCHAR(255)  NULL COMMENT 'Optional PHP expression e.g. "strtoupper({value})"',
  `is_required`          TINYINT(1)    NOT NULL DEFAULT 0,
  `created_at`           TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_mappings_system`   (`system_id`),
  KEY `idx_mappings_category` (`category_id`),
  CONSTRAINT `fk_mappings_system`   FOREIGN KEY (`system_id`)   REFERENCES `connected_systems` (`id`),
  CONSTRAINT `fk_mappings_category` FOREIGN KEY (`category_id`) REFERENCES `data_categories`   (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- E4. AUTO-CATEGORISATION RULES
-- Rules engine: when X arrives from system Y → assign category Z
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `auto_categorization_rules` (
  `id`             INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `system_id`      INT UNSIGNED  NOT NULL,
  `rule_name`      VARCHAR(255)  NOT NULL,
  `object_type`    VARCHAR(100)  NOT NULL COMMENT 'Object type from external system e.g. "loan_application"',
  `condition_field` VARCHAR(255) NULL COMMENT 'Optional field to inspect e.g. "status"',
  `condition_value` VARCHAR(255) NULL COMMENT 'Value that triggers this rule e.g. "rejected"',
  `category_id`    INT UNSIGNED  NOT NULL COMMENT 'Category to assign when rule matches',
  `priority`       INT           NOT NULL DEFAULT 10 COMMENT 'Lower = higher priority when rules overlap',
  `is_active`      TINYINT(1)    NOT NULL DEFAULT 1,
  `created_by`     INT UNSIGNED  NULL,
  `created_at`     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_rules_system`   (`system_id`),
  KEY `idx_rules_category` (`category_id`),
  KEY `idx_rules_priority` (`priority`),
  CONSTRAINT `fk_rules_system`      FOREIGN KEY (`system_id`)  REFERENCES `connected_systems` (`id`),
  CONSTRAINT `fk_rules_category`    FOREIGN KEY (`category_id`) REFERENCES `data_categories`  (`id`),
  CONSTRAINT `fk_rules_created_by`  FOREIGN KEY (`created_by`)  REFERENCES `users`            (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- E5. INTEGRATION LOGS
-- Full log of all API calls in + out (ingest, dispatch, etc.)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `integration_logs` (
  `id`             INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `system_id`      INT UNSIGNED  NULL,
  `api_key_id`     INT UNSIGNED  NULL,
  `direction`      ENUM('inbound','outbound') NOT NULL,
  `endpoint`       VARCHAR(255)  NOT NULL COMMENT 'e.g. "/api/v1/ingest"',
  `method`         VARCHAR(10)   NOT NULL COMMENT 'GET|POST|DELETE etc.',
  `status_code`    SMALLINT      NOT NULL,
  `request_body`   JSON          NULL COMMENT 'Stored truncated if >64KB',
  `response_body`  JSON          NULL,
  `records_affected` INT UNSIGNED NOT NULL DEFAULT 0,
  `duration_ms`    INT UNSIGNED  NULL COMMENT 'Request processing time in milliseconds',
  `ip_address`     VARCHAR(45)   NULL,
  `error_message`  TEXT          NULL,
  `created_at`     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_int_logs_system`    (`system_id`),
  KEY `idx_int_logs_direction` (`direction`),
  KEY `idx_int_logs_status`    (`status_code`),
  KEY `idx_int_logs_created`   (`created_at`),
  CONSTRAINT `fk_int_logs_system`  FOREIGN KEY (`system_id`)  REFERENCES `connected_systems` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_int_logs_api_key` FOREIGN KEY (`api_key_id`) REFERENCES `api_keys`          (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- E6. INTAKE QUEUE
-- Async buffer for batch/high-volume record intake from APIs
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `intake_queue` (
  `id`          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `system_id`   INT UNSIGNED  NOT NULL,
  `api_key_id`  INT UNSIGNED  NULL,
  `batch_id`    VARCHAR(64)   NULL COMMENT 'Groups records from same batch request',
  `payload`     JSON          NOT NULL COMMENT 'Raw incoming record data',
  `status`      ENUM('pending','processing','completed','failed','duplicate') NOT NULL DEFAULT 'pending',
  `category_id` INT UNSIGNED  NULL COMMENT 'Resolved after auto-categorisation',
  `record_id`   INT UNSIGNED  NULL COMMENT 'Created data_records.id after successful processing',
  `error`       TEXT          NULL,
  `attempts`    TINYINT       NOT NULL DEFAULT 0,
  `processed_at` TIMESTAMP    NULL,
  `created_at`  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_queue_system`  (`system_id`),
  KEY `idx_queue_status`  (`status`),
  KEY `idx_queue_batch`   (`batch_id`),
  KEY `idx_queue_created` (`created_at`),
  CONSTRAINT `fk_queue_system`   FOREIGN KEY (`system_id`)  REFERENCES `connected_systems` (`id`),
  CONSTRAINT `fk_queue_category` FOREIGN KEY (`category_id`) REFERENCES `data_categories`  (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_queue_record`   FOREIGN KEY (`record_id`)   REFERENCES `data_records`     (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- E7. DISPOSAL DISPATCHES
-- Outbound disposal instructions sent to connected systems
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `disposal_dispatches` (
  `id`             INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `record_id`      INT UNSIGNED  NOT NULL,
  `system_id`      INT UNSIGNED  NOT NULL,
  `dispatch_type`  ENUM('delete','anonymise','archive') NOT NULL,
  `external_ref`   VARCHAR(255)  NULL COMMENT 'The external system record identifier',
  `endpoint_url`   VARCHAR(500)  NULL COMMENT 'Webhook URL to call on the connected system',
  `payload`        JSON          NULL COMMENT 'Instruction payload sent to external system',
  `status`         ENUM('pending','sent','confirmed','failed') NOT NULL DEFAULT 'pending',
  `response_code`  SMALLINT      NULL,
  `response_body`  TEXT          NULL,
  `attempts`       TINYINT       NOT NULL DEFAULT 0,
  `sent_at`        TIMESTAMP     NULL,
  `confirmed_at`   TIMESTAMP     NULL,
  `created_at`     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_dispatch_record` (`record_id`),
  KEY `idx_dispatch_system` (`system_id`),
  KEY `idx_dispatch_status` (`status`),
  CONSTRAINT `fk_dispatch_record` FOREIGN KEY (`record_id`) REFERENCES `data_records`      (`id`),
  CONSTRAINT `fk_dispatch_system` FOREIGN KEY (`system_id`) REFERENCES `connected_systems` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- E8. CONSENT SIGNALS
-- Incoming consent withdrawal signals from connected systems
-- Processed into data_records.consent_withdrawn_at automatically
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `consent_signals` (
  `id`              INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `system_id`       INT UNSIGNED  NOT NULL,
  `external_ref`    VARCHAR(255)  NOT NULL COMMENT 'External identifier of the data subject',
  `signal_type`     ENUM('withdrawal','restriction','erasure_request') NOT NULL DEFAULT 'withdrawal',
  `category_id`     INT UNSIGNED  NULL COMMENT 'Category if known, NULL if resolved by rules',
  `record_id`       INT UNSIGNED  NULL COMMENT 'Matched data_records.id after processing',
  `raw_payload`     JSON          NULL,
  `status`          ENUM('pending','matched','processed','unmatched','error') NOT NULL DEFAULT 'pending',
  `processed_at`    TIMESTAMP     NULL,
  `error`           TEXT          NULL,
  `created_at`      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_signals_system`   (`system_id`),
  KEY `idx_signals_status`   (`status`),
  KEY `idx_signals_ext_ref`  (`external_ref`),
  CONSTRAINT `fk_signals_system`   FOREIGN KEY (`system_id`) REFERENCES `connected_systems` (`id`),
  CONSTRAINT `fk_signals_category` FOREIGN KEY (`category_id`) REFERENCES `data_categories` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_signals_record`   FOREIGN KEY (`record_id`)   REFERENCES `data_records`    (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- ENTERPRISE SYSTEM SETTINGS (appended to existing settings)
-- ----------------------------------------------------------
INSERT IGNORE INTO `system_settings` (`setting_key`, `setting_value`, `description`) VALUES
('adrs_tier',              'core',   'Product tier: core or enterprise — controls which features are active'),
('enterprise_api_enabled', '0',      'Enterprise: enable the REST API ingest endpoints (1=yes)'),
('api_rate_limit_per_min', '60',     'Enterprise: default API rate limit per key per minute'),
('intake_queue_enabled',   '1',      'Enterprise: use async intake queue for high-volume ingest'),
('disposal_dispatch_enabled','1',    'Enterprise: send outbound disposal instructions to connected systems'),
('consent_signal_enabled', '1',      'Enterprise: receive consent withdrawal signals via API'),
('webhook_retry_limit',    '3',      'Enterprise: max retry attempts for outbound webhook calls'),
('api_log_retention_days', '90',     'Enterprise: how long to keep integration_logs rows (days)');

-- ============================================================
-- PHASE 3 — ADVANCED FEATURES (additive)
-- ============================================================
ALTER TABLE `audit_log`
  ADD COLUMN `prev_hash` CHAR(64) NULL COMMENT 'row_hash of the previous audit row',
  ADD COLUMN `row_hash`  CHAR(64) NULL COMMENT 'SHA-256 over canonical content + prev_hash';

ALTER TABLE `users`
  ADD COLUMN `twofa_secret`   VARCHAR(64) NULL COMMENT 'Base32 TOTP secret',
  ADD COLUMN `twofa_enabled`  TINYINT(1)  NOT NULL DEFAULT 0,
  ADD COLUMN `twofa_recovery` JSON        NULL COMMENT 'Hashed one-time recovery codes';

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

CREATE TABLE IF NOT EXISTS `webhook_endpoints` (
  `id`           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name`         VARCHAR(255) NOT NULL,
  `url`          VARCHAR(500) NOT NULL,
  `event_types`  VARCHAR(500) NOT NULL DEFAULT '*',
  `is_active`    TINYINT(1) NOT NULL DEFAULT 1,
  `last_fired_at` TIMESTAMP NULL,
  `created_by`   INT UNSIGNED NULL,
  `created_at`   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_webhook_creator` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `backup_log` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `filename`   VARCHAR(255) NOT NULL,
  `size_bytes` BIGINT UNSIGNED NULL,
  `status`     ENUM('success','failed') NOT NULL,
  `message`    TEXT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO `system_settings` (`setting_key`, `setting_value`, `description`) VALUES
('white_label_name',     'ADRS - 3Consulting', 'White-label product name shown in the UI'),
('white_label_primary',  '#C85C1A',            'White-label primary colour (hex)'),
('white_label_logo_url', '',                   'White-label logo URL (optional)'),
('white_label_footer',   '3Consulting Limited','White-label footer text'),
('ops_webhooks_enabled', '0',                  'Send ops event notifications to configured webhooks'),
('backup_retention_days','30',                 'Days to keep automated DB backups'),
('require_2fa_roles',    '',                    'Comma-separated roles that MUST enable 2FA (e.g. admin,dpo). Empty = optional for all');

-- ----------------------------------------------------------
-- LOGIN ATTEMPTS (brute-force throttling)
-- ----------------------------------------------------------
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

-- Performance: index record_reference (used by API dedup + consent-signal matching).
ALTER TABLE `data_records` ADD INDEX `idx_records_reference` (`record_reference`);
