-- Add account_closure trigger option to categories and retention rules
ALTER TABLE `data_categories` MODIFY COLUMN `disposal_trigger` ENUM('date_based', 'consent_withdrawal', 'account_closure') NOT NULL DEFAULT 'date_based';
ALTER TABLE `category_retention_rules` MODIFY COLUMN `disposal_trigger` ENUM('date_based', 'consent_withdrawal', 'account_closure') NOT NULL DEFAULT 'date_based';

-- Add signing secret for outbound webhook dispatch signatures
ALTER TABLE `connected_systems` ADD COLUMN `signing_secret` VARCHAR(255) NULL AFTER `base_url`;
