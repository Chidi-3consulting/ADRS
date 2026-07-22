-- Categories only (no default users). Used by the setup wizard.
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
-- SELECT compliance_framework, COUNT(*) cnt FROM data_categories
-- WHERE organization_id = 0 GROUP BY compliance_framework;

-- ------------------------------------------------------------
-- CCPA CATEGORIES (United States) — 5 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

('Consumer Request Records (CCPA)',
 'Records of consumer access, deletion, and opt-out requests under CCPA/CPRA Section 1798.105.',
 'CCPA','legal_obligation',730,'2 years from request date',
 'archive','date_based',0,'annually','seeded'),

('Marketing Opt-Out Records (CCPA)',
 'Do-Not-Sell / Do-Not-Share consumer preference logs under CCPA Section 1798.120.',
 'CCPA','consent',0,'Until consumer withdraws opt-out or 2 years evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded'),

('Employee and Applicant Data (CCPA)',
 'Employee personal data, applicant records, and B2B contact details covered by CCPA/CPRA.',
 'CCPA','legal_obligation',2555,'7 years post-employment',
 'delete','date_based',0,'annually','seeded'),

('Financial Transaction Records (US)',
 'Payment records, invoices, receipts subject to IRS retention rules.',
 'CCPA','legal_obligation',2555,'7 years (IRS requirement)',
 'archive','date_based',0,'annually','seeded'),

('Customer PII (CCPA)',
 'Names, emails, phone numbers, addresses, and identifiers of California consumers.',
 'CCPA','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- LGPD CATEGORIES (Brazil) — 5 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

('Data Subject Request Records (LGPD)',
 'Records of data subject rights requests under LGPD Articles 17-22: access, correction, deletion, portability.',
 'LGPD','legal_obligation',1825,'5 years from request closure',
 'archive','date_based',0,'annually','seeded'),

('Consent Records (LGPD)',
 'Consent collection and withdrawal logs under LGPD Article 8.',
 'LGPD','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded'),

('Employee Records (LGPD/CLT)',
 'Employment contracts, payroll, FGTS, INSS, and termination records under CLT requirements.',
 'LGPD','legal_obligation',1825,'5 years post-employment (CLT)',
 'delete','date_based',0,'annually','seeded'),

('Financial Records (Brazil)',
 'Tax filings, NF-e invoices, and Receita Federal correspondence.',
 'LGPD','legal_obligation',1825,'5 years (Receita Federal)',
 'archive','date_based',0,'annually','seeded'),

('Customer Personal Data (Brazil)',
 'Names, CPF numbers, emails, phone numbers of Brazilian customers.',
 'LGPD','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- POPIA CATEGORIES (South Africa) — 5 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

('PAIA Request Records',
 'Records of access requests under Promotion of Access to Information Act (PAIA).',
 'POPIA','legal_obligation',1095,'3 years post-closure',
 'archive','date_based',0,'annually','seeded'),

('Employee Records (BCEA)',
 'Employment contracts, payroll, UIF records, and termination documents under Basic Conditions of Employment Act.',
 'POPIA','legal_obligation',1825,'5 years post-employment',
 'delete','date_based',0,'annually','seeded'),

('Customer Personal Information (SA)',
 'Names, ID numbers, contact details, and addresses of South African data subjects.',
 'POPIA','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

('Financial Records (SARS)',
 'Tax returns, VAT records, and SARS correspondence.',
 'POPIA','legal_obligation',1825,'5 years (SARS requirement)',
 'archive','date_based',0,'annually','seeded'),

('Consent Records (POPIA)',
 'Consent collection and withdrawal logs under POPIA Section 11.',
 'POPIA','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- DPA_KE CATEGORIES (Kenya) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

('Customer Personal Data (Kenya DPA)',
 'Names, national ID, phone numbers, email addresses of Kenyan data subjects.',
 'DPA_KE','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

('Employee Records (Kenya)',
 'Employment contracts, NHIF, NSSF records, and payroll data.',
 'DPA_KE','legal_obligation',2190,'6 years post-employment',
 'delete','date_based',0,'annually','seeded'),

('Consent Records (Kenya DPA)',
 'Consent logs and withdrawal records under the Kenya Data Protection Act.',
 'DPA_KE','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- DPA_GH CATEGORIES (Ghana) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

('Customer Personal Data (Ghana DPA)',
 'Names, Ghana Card numbers, phone numbers, email addresses of Ghanaian data subjects.',
 'DPA_GH','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

('Employee Records (Ghana)',
 'Employment contracts, SSNIT records, and payroll data under Ghanaian labour law.',
 'DPA_GH','legal_obligation',2190,'6 years post-employment',
 'delete','date_based',0,'annually','seeded'),

('Consent Records (Ghana DPA)',
 'Consent logs and withdrawal records under the Ghana Data Protection Act.',
 'DPA_GH','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- PDPA_SG CATEGORIES (Singapore) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

('Customer Personal Data (PDPA Singapore)',
 'Names, NRIC/FIN, phone numbers, email addresses of Singaporean data subjects.',
 'PDPA_SG','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

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
-- SELECT compliance_framework, COUNT(*) cnt FROM data_categories
-- WHERE organization_id = 0 GROUP BY compliance_framework;

-- ------------------------------------------------------------
-- CCPA CATEGORIES (United States) — 5 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

('Consumer Request Records (CCPA)',
 'Records of consumer access, deletion, and opt-out requests under CCPA/CPRA Section 1798.105.',
 'CCPA','legal_obligation',730,'2 years from request date',
 'archive','date_based',0,'annually','seeded'),

('Marketing Opt-Out Records (CCPA)',
 'Do-Not-Sell / Do-Not-Share consumer preference logs under CCPA Section 1798.120.',
 'CCPA','consent',0,'Until consumer withdraws opt-out or 2 years evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded'),

('Employee and Applicant Data (CCPA)',
 'Employee personal data, applicant records, and B2B contact details covered by CCPA/CPRA.',
 'CCPA','legal_obligation',2555,'7 years post-employment',
 'delete','date_based',0,'annually','seeded'),

('Financial Transaction Records (US)',
 'Payment records, invoices, receipts subject to IRS retention rules.',
 'CCPA','legal_obligation',2555,'7 years (IRS requirement)',
 'archive','date_based',0,'annually','seeded'),

('Customer PII (CCPA)',
 'Names, emails, phone numbers, addresses, and identifiers of California consumers.',
 'CCPA','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- LGPD CATEGORIES (Brazil) — 5 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

('Data Subject Request Records (LGPD)',
 'Records of data subject rights requests under LGPD Articles 17-22: access, correction, deletion, portability.',
 'LGPD','legal_obligation',1825,'5 years from request closure',
 'archive','date_based',0,'annually','seeded'),

('Consent Records (LGPD)',
 'Consent collection and withdrawal logs under LGPD Article 8.',
 'LGPD','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded'),

('Employee Records (LGPD/CLT)',
 'Employment contracts, payroll, FGTS, INSS, and termination records under CLT requirements.',
 'LGPD','legal_obligation',1825,'5 years post-employment (CLT)',
 'delete','date_based',0,'annually','seeded'),

('Financial Records (Brazil)',
 'Tax filings, NF-e invoices, and Receita Federal correspondence.',
 'LGPD','legal_obligation',1825,'5 years (Receita Federal)',
 'archive','date_based',0,'annually','seeded'),

('Customer Personal Data (Brazil)',
 'Names, CPF numbers, emails, phone numbers of Brazilian customers.',
 'LGPD','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- POPIA CATEGORIES (South Africa) — 5 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

('PAIA Request Records',
 'Records of access requests under Promotion of Access to Information Act (PAIA).',
 'POPIA','legal_obligation',1095,'3 years post-closure',
 'archive','date_based',0,'annually','seeded'),

('Employee Records (BCEA)',
 'Employment contracts, payroll, UIF records, and termination documents under Basic Conditions of Employment Act.',
 'POPIA','legal_obligation',1825,'5 years post-employment',
 'delete','date_based',0,'annually','seeded'),

('Customer Personal Information (SA)',
 'Names, ID numbers, contact details, and addresses of South African data subjects.',
 'POPIA','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

('Financial Records (SARS)',
 'Tax returns, VAT records, and SARS correspondence.',
 'POPIA','legal_obligation',1825,'5 years (SARS requirement)',
 'archive','date_based',0,'annually','seeded'),

('Consent Records (POPIA)',
 'Consent collection and withdrawal logs under POPIA Section 11.',
 'POPIA','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- DPA_KE CATEGORIES (Kenya) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

('Customer Personal Data (Kenya DPA)',
 'Names, national ID, phone numbers, email addresses of Kenyan data subjects.',
 'DPA_KE','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

('Employee Records (Kenya)',
 'Employment contracts, NHIF, NSSF records, and payroll data.',
 'DPA_KE','legal_obligation',2190,'6 years post-employment',
 'delete','date_based',0,'annually','seeded'),

('Consent Records (Kenya DPA)',
 'Consent logs and withdrawal records under the Kenya Data Protection Act.',
 'DPA_KE','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- DPA_GH CATEGORIES (Ghana) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

('Customer Personal Data (Ghana DPA)',
 'Names, Ghana Card numbers, phone numbers, email addresses of Ghanaian data subjects.',
 'DPA_GH','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

('Employee Records (Ghana)',
 'Employment contracts, SSNIT records, and payroll data under Ghanaian labour law.',
 'DPA_GH','legal_obligation',2190,'6 years post-employment',
 'delete','date_based',0,'annually','seeded'),

('Consent Records (Ghana DPA)',
 'Consent logs and withdrawal records under the Ghana Data Protection Act.',
 'DPA_GH','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- PDPA_SG CATEGORIES (Singapore) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES

('Customer Personal Data (PDPA Singapore)',
 'Names, NRIC/FIN, phone numbers, email addresses of Singaporean data subjects.',
 'PDPA_SG','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),

('Employee Records (MOM/Singapore)',
 'Employment contracts, CPF records, and payroll data under Singapore Employment Act and MOM requirements.',
 'PDPA_SG','legal_obligation',1825,'5 years post-employment',
 'delete','date_based',0,'annually','seeded'),

('Consent Records (PDPA)',
 'Consent collection and withdrawal logs under PDPA obligations.',
 'PDPA_SG','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- DPDP CATEGORIES (India) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES
('Customer Personal Data (India DPDP)',
 'Names, Aadhaar references, phone numbers, email addresses of Indian data principals.',
 'DPDP','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),
('Employee Records (India)',
 'Employment contracts, PF/ESI records, Form 16, and payroll data under Indian labour law.',
 'DPDP','legal_obligation',2555,'7 years post-employment',
 'delete','date_based',0,'annually','seeded'),
('Consent Records (DPDP)',
 'Consent collection and withdrawal logs under DPDP Act Section 6.',
 'DPDP','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- PDPL CATEGORIES (UAE) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES
('Customer Personal Data (UAE PDPL)',
 'Names, Emirates ID references, phone numbers, email addresses of UAE data subjects.',
 'PDPL','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),
('Employee Records (UAE)',
 'Employment contracts, WPS payroll records, visa and labour card data under UAE labour law.',
 'PDPL','legal_obligation',730,'2 years post-employment (UAE Labour Law)',
 'delete','date_based',0,'annually','seeded'),
('Consent Records (PDPL)',
 'Consent collection and withdrawal logs under UAE PDPL.',
 'PDPL','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- PIPEDA CATEGORIES (Canada) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES
('Customer Personal Information (Canada PIPEDA)',
 'Names, SIN references, phone numbers, email addresses of Canadian individuals.',
 'PIPEDA','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),
('Employee Records (Canada)',
 'Employment contracts, T4 records, payroll, and benefits data under CRA requirements.',
 'PIPEDA','legal_obligation',2555,'7 years post-employment (CRA)',
 'delete','date_based',0,'annually','seeded'),
('Consent Records (PIPEDA)',
 'Consent collection and withdrawal logs under PIPEDA Principle 3.',
 'PIPEDA','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- APPs CATEGORIES (Australia) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES
('Customer Personal Information (Australia APPs)',
 'Names, TFN references, phone numbers, email addresses of Australian individuals.',
 'APPs','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),
('Employee Records (Australia)',
 'Employment contracts, superannuation, payroll, and tax records under Fair Work Act and ATO requirements.',
 'APPs','legal_obligation',2555,'7 years post-employment (ATO)',
 'delete','date_based',0,'annually','seeded'),
('Consent Records (APPs)',
 'Consent collection and withdrawal logs under Australian Privacy Principle 3.',
 'APPs','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');

-- ------------------------------------------------------------
-- EGDPL CATEGORIES (Egypt) — 3 entries
-- ------------------------------------------------------------
INSERT INTO `data_categories`
  (`name`,`description`,`compliance_framework`,`legal_basis`,
   `retention_period_days`,`retention_period_label`,
   `disposal_method`,`disposal_trigger`,`requires_dual_approval`,
   `review_frequency`,`source`)
VALUES
('Customer Personal Data (Egypt EGDPL)',
 'Names, national ID numbers, phone numbers, email addresses of Egyptian data subjects.',
 'EGDPL','contract',1095,'3 years post-relationship',
 'anonymise','date_based',0,'quarterly','seeded'),
('Employee Records (Egypt)',
 'Employment contracts, social insurance records, and payroll data under Egyptian labour law.',
 'EGDPL','legal_obligation',1825,'5 years post-employment',
 'delete','date_based',0,'annually','seeded'),
('Consent Records (EGDPL)',
 'Consent collection and withdrawal logs under Egypt Data Protection Law No. 151.',
 'EGDPL','consent',0,'Until consent withdrawn + 1 year evidence',
 'delete','consent_withdrawal',0,'quarterly','seeded');
