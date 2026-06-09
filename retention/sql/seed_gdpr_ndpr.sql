-- ============================================================
-- 3Consulting ADRS — GDPR + NDPR Seed Library v4 (AUDIT-FIXED)
-- BUG-02 FIX: disposal_trigger set directly in INSERT (no UPDATE needed)
-- BUG-03 FIX: requires_dual_approval set directly in INSERT
-- 30 Pre-built Categories | 2 Default Users
-- ============================================================

SET NAMES utf8mb4;

-- Default users (password: 'password' — CHANGE ON FIRST LOGIN)
-- BCrypt hash of 'password'
INSERT IGNORE INTO `organizations` (`id`, `name`, `slug`, `tier`, `status`) VALUES
(1, '3Consulting Demo', '3consulting-demo', 'core', 'active');

INSERT INTO `users` (`organization_id`, `name`, `email`, `password_hash`, `role`, `must_change_password`, `is_platform_admin`, `email_verified_at`) VALUES
(1, 'System Administrator', 'admin@3consult-ng.com',
 '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'admin', 1, 1, NOW()),
(1, 'Data Protection Officer', 'dpo@3consult-ng.com',
 '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'dpo', 1, 0, NOW());

INSERT INTO `system_settings` (`setting_key`, `setting_value`, `description`) VALUES
('deployment_mode', 'single', 'Dev/demo install uses single-tenant mode'),
('setup_complete', '1', 'Set to 1 after initial setup wizard completes')
ON DUPLICATE KEY UPDATE `setting_value` = VALUES(`setting_value`);

INSERT IGNORE INTO `organization_settings` (`organization_id`, `setting_key`, `setting_value`, `description`)
SELECT 1, `setting_key`, `setting_value`, `description` FROM `system_settings`
WHERE `setting_key` NOT IN ('deployment_mode', 'setup_complete', 'allow_public_signup');

-- ============================================================
-- Column order for INSERT:
-- (name, description, compliance_framework, legal_basis,
--  retention_period_days, retention_period_label,
--  disposal_method, disposal_trigger, requires_dual_approval,
--  review_frequency, source)
-- ============================================================

-- ------------------------------------------------------------
-- GDPR CATEGORIES (EU / UK) — 15 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

-- 1 — Standard date-based
('Employee Personnel Records',
 'Full employment records: contracts, appraisals, disciplinary actions, payroll history, termination documents.',
 'GDPR','legal_obligation',2190,'6 years post-employment',
 'delete','date_based',0,'annually','seeded'),

-- 2
('Employee Payroll & Tax Records',
 'Payroll runs, P60s, P45s, HMRC submissions, tax codes, National Insurance records.',
 'GDPR','legal_obligation',2555,'7 years (HMRC requirement)',
 'archive','date_based',0,'annually','seeded'),

-- 3
('Recruitment & Application Data',
 'CVs, cover letters, interview notes, and assessment results for unsuccessful candidates.',
 'GDPR','legitimate_interest',180,'6 months post-rejection',
 'delete','date_based',0,'quarterly','seeded'),

-- 4
('Customer Contracts & Agreements',
 'Signed contracts, SOWs, MSAs, NDAs, and service agreements with clients.',
 'GDPR','contract',2555,'7 years post-expiry',
 'archive','date_based',0,'annually','seeded'),

-- 5 — CONSENT-BASED (BUG-02 FIX: disposal_trigger explicitly set)
('Marketing Consent Records',
 'Email opt-in records, consent timestamps, preference centre logs, and withdrawal records.',
 'GDPR','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded'),

-- 6
('Website & Server Access Logs',
 'Web server logs, access logs, error logs, IP addresses of visitors.',
 'GDPR','legitimate_interest',180,'6 months',
 'delete','date_based',0,'quarterly','seeded'),

-- 7
('Customer Support Tickets',
 'Support communications, complaint records, resolution logs, and related correspondence.',
 'GDPR','contract',1095,'3 years post-resolution',
 'anonymise','date_based',0,'quarterly','seeded'),

-- 8
('Financial Transactions & Invoices',
 'Invoices, receipts, purchase orders, bank statements, and VAT records.',
 'GDPR','legal_obligation',2555,'7 years (HMRC/Companies Act)',
 'archive','date_based',0,'annually','seeded'),

-- 9 — SENSITIVE: dual approval (BUG-02 FIX: requires_dual_approval=1)
('Health & Medical Records (Employees)',
 'Occupational health reports, sick notes, disability assessments, return-to-work plans.',
 'GDPR','legal_obligation',3650,'10 years post-employment',
 'delete','date_based',1,'annually','seeded'),

-- 10
('CCTV Footage',
 'Video surveillance footage from office and facility cameras.',
 'GDPR','legitimate_interest',30,'30 days',
 'delete','date_based',0,'monthly','seeded'),

-- 11
('Data Breach Incident Records',
 'Records of personal data breaches, impact assessments, notifications to ICO and data subjects.',
 'GDPR','legal_obligation',1825,'5 years (ICO requirement)',
 'archive','date_based',0,'annually','seeded'),

-- 12
('DSAR Records',
 'All requests received under Articles 15-22 GDPR: access, rectification, erasure, portability.',
 'GDPR','legal_obligation',1095,'3 years post-closure',
 'archive','date_based',0,'annually','seeded'),

-- 13
('Supplier & Vendor Contracts',
 'Third-party processing agreements, DPAs, supplier due diligence records.',
 'GDPR','contract',2555,'7 years post-expiry',
 'archive','date_based',0,'annually','seeded'),

-- 14
('DPIA Reports',
 'Data Protection Impact Assessments under Article 35 GDPR.',
 'GDPR','legal_obligation',1825,'5 years or life of processing',
 'archive','date_based',0,'annually','seeded'),

-- 15
('Training & Certification Records',
 'Data protection training completion records, certificates, awareness logs.',
 'GDPR','legal_obligation',1095,'3 years',
 'delete','date_based',0,'annually','seeded'),

-- ------------------------------------------------------------
-- NDPR CATEGORIES (Nigeria) — 10 entries
-- ------------------------------------------------------------

-- 16
('Customer KYC & Onboarding Data',
 'KYC records, identity verification, CAC documents, utility bills, onboarding forms (CBN / NITDA).',
 'NDPR','legal_obligation',1825,'5 years post-relationship (CBN AML)',
 'archive','date_based',0,'annually','seeded'),

-- 17
('Employee Personal Data (NDPR)',
 'Nigerian employee records: BVN, NIN, state of origin, guarantor forms, employment contracts.',
 'NDPR','legal_obligation',2555,'7 years post-employment',
 'delete','date_based',0,'annually','seeded'),

-- 18
('Financial Records (FIRS Compliance)',
 'Tax filings, WHT, VAT returns, CIT records, FIRS correspondence.',
 'NDPR','legal_obligation',2190,'6 years (FIRS requirement)',
 'archive','date_based',0,'annually','seeded'),

-- 19
('Customer Personal Data (Nigeria)',
 'Names, phone numbers, email addresses, addresses, DOB of Nigerian customers.',
 'NDPR','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

-- 20 — SENSITIVE: dual approval
('Health Data (Employees - Nigeria)',
 'HMO records, hospital referral letters, sick leave records, health fund documentation.',
 'NDPR','legal_obligation',3650,'10 years',
 'delete','date_based',1,'annually','seeded'),

-- 21 — CONSENT-BASED
('Consent Records (NDPR)',
 'Written or electronic consent under NDPR Section 2.2 for marketing, data sharing, or processing.',
 'NDPR','consent',0,'Duration of purpose + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded'),

-- 22
('Third-Party Data Sharing Agreements',
 'Contracts and DPAs with third parties processing personal data of Nigerian data subjects.',
 'NDPR','legal_obligation',2555,'7 years',
 'archive','date_based',0,'annually','seeded'),

-- 23
('Data Breach Records (NDPR)',
 'Breach notifications to NITDA, data subject notifications, incident reports per NDPR Article 4.1.',
 'NDPR','legal_obligation',1825,'5 years',
 'archive','date_based',0,'annually','seeded'),

-- 24
('Annual Data Audit Reports',
 'Annual data protection audit reports for NITDA or internal use per NDPR Framework.',
 'NDPR','legal_obligation',2555,'7 years',
 'archive','date_based',0,'annually','seeded'),

-- 25
('Procurement & Tender Records (Nigeria)',
 'Procurement records, supplier evaluations, tender documents under NDPR and Public Procurement Act.',
 'NDPR','legal_obligation',2190,'6 years',
 'archive','date_based',0,'annually','seeded'),

-- ------------------------------------------------------------
-- DUAL-FRAMEWORK (GDPR + NDPR) — 5 entries
-- ------------------------------------------------------------

-- 26
('Cross-Border Data Transfer Records',
 'Records of personal data transfers outside Nigeria or UK/EU: SCCs, adequacy decisions, transfer mechanisms.',
 'BOTH','legal_obligation',1825,'5 years',
 'archive','date_based',0,'annually','seeded'),

-- 27
('Privacy Notices & Policy Versions',
 'All versions of privacy notices, cookie policies, and terms of service with effective dates.',
 'BOTH','legal_obligation',1825,'5 years from version retirement',
 'archive','date_based',0,'annually','seeded'),

-- 28 — SENSITIVE: dual approval + consent-based (BUG-02 FIX)
('Children\'s Data (Under 13/18)',
 'Any personal data of minors, parental consent records, age verification logs.',
 'BOTH','consent',0,'5 years or until data subject turns 21',
 'delete','consent_withdrawal',1,'quarterly','seeded'),

-- 29
('Whistleblowing & Grievance Records',
 'Internal reports, investigation records, outcomes related to data protection complaints.',
 'BOTH','legal_obligation',1825,'5 years post-closure',
 'archive','date_based',0,'annually','seeded'),

-- 30 — SENSITIVE: dual approval + consent-based (BUG-02 FIX)
('Biometric Data',
 'Fingerprints, facial recognition data, voice prints, retina scans used for access or verification.',
 'BOTH','consent',0,'Until consent withdrawn or employment/relationship ends',
 'delete','consent_withdrawal',1,'quarterly','seeded');

-- ============================================================
-- VERIFICATION QUERY (run after import to confirm)
-- ============================================================
-- SELECT disposal_trigger, requires_dual_approval, COUNT(*) as cnt
-- FROM data_categories GROUP BY disposal_trigger, requires_dual_approval;
--
-- Expected results:
-- consent_withdrawal | 0 | 3  (Marketing Consent, NDPR Consent, Children's*)
-- consent_withdrawal | 1 | 2  (Children's Data, Biometric Data)
-- Wait — Children's is consent_withdrawal + dual=1, Biometric is consent_withdrawal + dual=1
-- Marketing Consent is consent_withdrawal + dual=0
-- NDPR Consent is consent_withdrawal + dual=0
-- So: consent_withdrawal/0 = 2, consent_withdrawal/1 = 2, date_based/0 = 22, date_based/1 = 4
