-- Organisation primary domain: one tenant per company domain (SaaS integrity).
ALTER TABLE `organizations`
  ADD COLUMN `primary_domain` VARCHAR(255) NULL AFTER `slug`;

-- Backfill legacy rows from billing email or slug placeholder.
UPDATE `organizations` o
SET o.`primary_domain` = LOWER(SUBSTRING_INDEX(o.`billing_email`, '@', -1))
WHERE o.`primary_domain` IS NULL AND o.`billing_email` IS NOT NULL AND o.`billing_email` LIKE '%@%';

UPDATE `organizations`
SET `primary_domain` = CONCAT(`slug`, '.local')
WHERE `primary_domain` IS NULL OR `primary_domain` = '';

ALTER TABLE `organizations`
  MODIFY COLUMN `primary_domain` VARCHAR(255) NOT NULL,
  ADD UNIQUE KEY `uq_organizations_primary_domain` (`primary_domain`);
