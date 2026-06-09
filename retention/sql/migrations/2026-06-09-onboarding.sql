-- ============================================================
-- ADRS onboarding migration (run once on an existing deployment).
-- New installs get these via schema.sql.
-- ============================================================

ALTER TABLE `users`
  ADD COLUMN `must_change_password` TINYINT(1) NOT NULL DEFAULT 0
    COMMENT 'Force password change on next login (seeded/temp passwords)';

INSERT IGNORE INTO `system_settings` (`setting_key`, `setting_value`, `description`) VALUES
('setup_complete',      '1', 'Set to 1 after initial setup wizard completes (auto-set if admin exists)'),
('allow_public_signup', '0', 'Allow public self-registration (creates data_owner role)');

-- Existing seeded deployments: flag default-password users for forced change.
UPDATE `users` SET `must_change_password` = 1
 WHERE `email` IN ('admin@3consult-ng.com', 'dpo@3consult-ng.com')
   AND `deleted_at` IS NULL;
