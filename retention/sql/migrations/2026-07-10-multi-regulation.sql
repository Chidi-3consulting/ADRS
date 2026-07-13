-- ============================================================
-- 3Consulting ADRS — Multi-Regulation & Country Support Migration
-- ============================================================

-- 1. Add country to organizations
ALTER TABLE `organizations` ADD COLUMN `country` VARCHAR(2) NULL AFTER `primary_domain`;

-- 2. Modify compliance_framework columns to allow dynamic regulations
ALTER TABLE `data_categories` MODIFY `compliance_framework` VARCHAR(50) NOT NULL DEFAULT 'GDPR';
ALTER TABLE `dsar_requests` MODIFY `compliance_framework` VARCHAR(50) NOT NULL DEFAULT 'GDPR';

-- 3. Add retention_reason to data_categories
ALTER TABLE `data_categories` ADD COLUMN `retention_reason` TEXT NULL AFTER `description`;

-- 4. Create regulations registry table
CREATE TABLE IF NOT EXISTS `regulations` (
  `code`        VARCHAR(20) NOT NULL,
  `name`        VARCHAR(255) NOT NULL,
  `country`     VARCHAR(2) NULL COMMENT 'ISO 3166-1 alpha-2 or NULL for global/regional',
  `continent`   VARCHAR(20) NULL,
  `description` TEXT NULL,
  `is_active`   TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Seed standard regulations
INSERT IGNORE INTO `regulations` (`code`, `name`, `country`, `continent`, `description`) VALUES
('GDPR', 'EU GDPR (General Data Protection Regulation)', NULL, 'Europe', 'European Union general data protection regulation'),
('NDPR', 'Nigeria NDPR/NDPA (Nigeria Data Protection)', 'NG', 'Africa', 'Nigeria Data Protection Regulation & Act'),
('CCPA', 'US CCPA/CPRA (California Consumer Privacy Act)', 'US', 'North America', 'California Consumer Privacy Act'),
('LGPD', 'Brazil LGPD (Lei Geral de Proteção de Dados)', 'BR', 'South America', 'Brazilian General Data Protection Law'),
('POPIA', 'South Africa POPIA (Protection of Personal Information Act)', 'ZA', 'Africa', 'South African personal information protection law'),
('DPA_KE', 'Kenya DPA (Data Protection Act)', 'KE', 'Africa', 'Kenyan Data Protection Act'),
('UK_GDPR', 'United Kingdom GDPR', 'GB', 'Europe', 'UK General Data Protection Regulation'),
('DPA_GH', 'Ghana DPA (Data Protection Act)', 'GH', 'Africa', 'Ghanaian Data Protection Act'),
('PDPA_SG', 'Singapore PDPA (Personal Data Protection Act)', 'SG', 'Asia', 'Singapore Personal Data Protection Act');
