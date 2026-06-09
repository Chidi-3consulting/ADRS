-- ============================================================
-- ADRS commercial launch: billing, email verification, platform admin, licence keys.
-- ============================================================

ALTER TABLE `users`
  ADD COLUMN `email_verified_at` TIMESTAMP NULL,
  ADD COLUMN `verification_token_hash` VARCHAR(64) NULL,
  ADD COLUMN `is_platform_admin` TINYINT(1) NOT NULL DEFAULT 0;

ALTER TABLE `organizations`
  ADD COLUMN `subscription_status` ENUM('trial','active','past_due','cancelled') NOT NULL DEFAULT 'trial' AFTER `status`,
  ADD COLUMN `billing_email` VARCHAR(255) NULL AFTER `subscription_status`,
  ADD COLUMN `last_payment_at` TIMESTAMP NULL,
  ADD COLUMN `paystack_customer_code` VARCHAR(100) NULL,
  ADD COLUMN `enterprise_licence_key` VARCHAR(64) NULL;

CREATE TABLE IF NOT EXISTS `enterprise_licence_keys` (
  `id`                          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `key_hash`                    CHAR(64)     NOT NULL,
  `key_prefix`                  VARCHAR(32)  NOT NULL,
  `redeemed_by_organization_id` INT UNSIGNED NULL,
  `redeemed_at`                 TIMESTAMP    NULL,
  `created_at`                  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_licence_key_hash` (`key_hash`),
  KEY `idx_licence_redeemed` (`redeemed_by_organization_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `payment_transactions` (
  `id`              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id` INT UNSIGNED NOT NULL,
  `reference`       VARCHAR(100) NOT NULL,
  `amount_kobo`     INT UNSIGNED NOT NULL,
  `currency`        CHAR(3)      NOT NULL DEFAULT 'NGN',
  `plan_tier`       ENUM('core','enterprise') NOT NULL,
  `status`          ENUM('pending','success','failed') NOT NULL DEFAULT 'pending',
  `provider`        VARCHAR(32)  NOT NULL DEFAULT 'paystack',
  `provider_data`   JSON         NULL,
  `created_at`      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `completed_at`    TIMESTAMP    NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_payment_reference` (`reference`),
  KEY `idx_payment_org` (`organization_id`),
  CONSTRAINT `fk_payment_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO `system_settings` (`setting_key`, `setting_value`, `description`) VALUES
('paystack_public_key',         '',                       'Paystack public key (pk_test_… or pk_live_…)'),
('paystack_secret_key',         '',                       'Paystack secret key — platform billing only'),
('core_plan_amount_kobo',       '7500000',                'Core plan price in kobo (₦75,000)'),
('enterprise_plan_amount_kobo', '25000000',               'Enterprise plan price in kobo (₦250,000)'),
('trial_days',                  '14',                     'Free trial length for new organisations'),
('platform_support_email',      'projects@3consult-ng.com', 'Shown on billing and legal pages');

-- Demo Enterprise licence (raw key: ADRS-ENT-DEMO-2026-3CONSULT)
INSERT IGNORE INTO `enterprise_licence_keys` (`key_hash`, `key_prefix`) VALUES
(SHA2('ADRS-ENT-DEMO-2026-3CONSULT', 256), 'ADRS-ENT-DEMO');
