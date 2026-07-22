-- ============================================================
-- 3Consulting ADRS — Global Regulation Coverage Migration
-- Adds missing regulations and seed categories for full
-- country-tailored onboarding.
-- ============================================================

-- 1. Insert missing regulations
INSERT IGNORE INTO `regulations` (`code`, `name`, `country`, `continent`, `description`) VALUES
('DPDP',    'India DPDP Act (Digital Personal Data Protection)',   'IN', 'Asia',          'India Digital Personal Data Protection Act 2023'),
('PDPL',    'UAE PDPL (Personal Data Protection Law)',             'AE', 'Middle East',   'UAE Federal Decree-Law No. 45 of 2021 on Personal Data Protection'),
('PIPEDA',  'Canada PIPEDA (Personal Information Protection)',     'CA', 'North America', 'Personal Information Protection and Electronic Documents Act'),
('APPs',    'Australia Privacy Act / APPs (Australian Privacy Principles)', 'AU', 'Oceania', 'Australian Privacy Principles under the Privacy Act 1988'),
('EGDPL',   'Egypt EGDPL (Data Protection Law)',                   'EG', 'Africa',        'Egyptian Personal Data Protection Law No. 151 of 2020'),
('BOTH',    'Cross-Framework (GDPR & NDPR)',                       NULL, NULL,            'Data categories applicable under both GDPR and NDPR frameworks');

-- ============================================================
-- 2. Seed category templates for new frameworks (org_id = 0)
-- ============================================================

-- ------------------------------------------------------------
-- DPDP CATEGORIES (India) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`organization_id`,`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

(0, 'Customer Personal Data (India DPDP)',
 'Names, Aadhaar references, phone numbers, email addresses of Indian data principals.',
 'DPDP','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

(0, 'Employee Records (India)',
 'Employment contracts, PF/ESI records, Form 16, and payroll data under Indian labour law.',
 'DPDP','legal_obligation',2555,'7 years post-employment',
 'delete','date_based',0,'annually','seeded'),

(0, 'Consent Records (DPDP)',
 'Consent collection and withdrawal logs under DPDP Act Section 6.',
 'DPDP','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- PDPL CATEGORIES (UAE) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`organization_id`,`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

(0, 'Customer Personal Data (UAE PDPL)',
 'Names, Emirates ID references, phone numbers, email addresses of UAE data subjects.',
 'PDPL','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

(0, 'Employee Records (UAE)',
 'Employment contracts, WPS payroll records, visa and labour card data under UAE labour law.',
 'PDPL','legal_obligation',730,'2 years post-employment (UAE Labour Law)',
 'delete','date_based',0,'annually','seeded'),

(0, 'Consent Records (PDPL)',
 'Consent collection and withdrawal logs under UAE PDPL.',
 'PDPL','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- PIPEDA CATEGORIES (Canada) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`organization_id`,`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

(0, 'Customer Personal Information (Canada PIPEDA)',
 'Names, SIN references, phone numbers, email addresses of Canadian individuals.',
 'PIPEDA','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

(0, 'Employee Records (Canada)',
 'Employment contracts, T4 records, payroll, and benefits data under CRA requirements.',
 'PIPEDA','legal_obligation',2555,'7 years post-employment (CRA)',
 'delete','date_based',0,'annually','seeded'),

(0, 'Consent Records (PIPEDA)',
 'Consent collection and withdrawal logs under PIPEDA Principle 3.',
 'PIPEDA','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- APPs CATEGORIES (Australia) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`organization_id`,`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

(0, 'Customer Personal Information (Australia APPs)',
 'Names, TFN references, phone numbers, email addresses of Australian individuals.',
 'APPs','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

(0, 'Employee Records (Australia)',
 'Employment contracts, superannuation, payroll, and tax records under Fair Work Act and ATO requirements.',
 'APPs','legal_obligation',2555,'7 years post-employment (ATO)',
 'delete','date_based',0,'annually','seeded'),

(0, 'Consent Records (APPs)',
 'Consent collection and withdrawal logs under Australian Privacy Principle 3.',
 'APPs','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- EGDPL CATEGORIES (Egypt) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`organization_id`,`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

(0, 'Customer Personal Data (Egypt EGDPL)',
 'Names, national ID numbers, phone numbers, email addresses of Egyptian data subjects.',
 'EGDPL','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

(0, 'Employee Records (Egypt)',
 'Employment contracts, social insurance records, and payroll data under Egyptian labour law.',
 'EGDPL','legal_obligation',1825,'5 years post-employment',
 'delete','date_based',0,'annually','seeded'),

(0, 'Consent Records (EGDPL)',
 'Consent collection and withdrawal logs under Egypt Data Protection Law No. 151.',
 'EGDPL','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');
