# GDPR + NDPR Starter Compliance Library

## Overview
This system ships with 30 pre-built data categories drawn from the requirements of:
- **GDPR** (EU General Data Protection Regulation) — 15 categories
- **NDPR** (Nigeria Data Protection Regulation, NITDA) — 10 categories
- **Both frameworks** — 5 categories applying to organisations operating in both jurisdictions

All seeded categories are marked `source = 'seeded'` and can be edited to match your organisation's specific data landscape.

---

## GDPR Categories (15)

| # | Category | Retention | Legal Basis | Disposal |
|---|---|---|---|---|
| 1 | Employee Personnel Records | 6 years post-employment | Legal Obligation | Delete |
| 2 | Employee Payroll & Tax Records | 7 years | Legal Obligation | Archive |
| 3 | Recruitment & Application Data | 6 months post-rejection | Legitimate Interest | Delete |
| 4 | Customer Contracts & Agreements | 7 years post-expiry | Contract | Archive |
| 5 | Marketing Consent Records | Until withdrawn + 1 year | Consent | Delete |
| 6 | Website & Server Access Logs | 6 months | Legitimate Interest | Delete |
| 7 | Customer Support Tickets | 3 years post-resolution | Contract | Anonymise |
| 8 | Financial Transactions & Invoices | 7 years | Legal Obligation | Archive |
| 9 | Health & Medical Records (Employees) | 10 years post-employment | Legal Obligation | Delete |
| 10 | CCTV Footage | 30 days | Legitimate Interest | Delete |
| 11 | Data Breach Incident Records | 5 years | Legal Obligation | Archive |
| 12 | DSAR Records | 3 years post-closure | Legal Obligation | Archive |
| 13 | Supplier & Vendor Contracts | 7 years post-expiry | Contract | Archive |
| 14 | DPIA Reports | 5 years or life of processing | Legal Obligation | Archive |
| 15 | Training & Certification Records | 3 years | Legal Obligation | Delete |

**Key regulatory sources:**
- HMRC: 7-year rule for financial records (Finance Act 2008)
- ICO: 5-year data breach record keeping
- Limitation Act 1980: 6-year limitation period for contract claims
- UK GDPR Article 30: Records of processing activities

---

## NDPR Categories (10)

| # | Category | Retention | Legal Basis | Disposal |
|---|---|---|---|---|
| 16 | Customer KYC & Onboarding Data | 5 years post-relationship | Legal Obligation | Archive |
| 17 | Employee Personal Data (Nigeria) | 7 years | Legal Obligation | Delete |
| 18 | Financial Records (FIRS) | 6 years | Legal Obligation | Archive |
| 19 | Customer Personal Data — General | 3 years | Contract | Anonymise |
| 20 | Health Data — Employees (Nigeria) | 10 years | Legal Obligation | Delete |
| 21 | Consent Records (NDPR) | Duration + 1 year | Consent | Delete |
| 22 | Third-Party Data Sharing Agreements | 7 years | Legal Obligation | Archive |
| 23 | Data Breach Records (NDPR) | 5 years | Legal Obligation | Archive |
| 24 | Annual Data Audit Reports | 7 years | Legal Obligation | Archive |
| 25 | Procurement & Tender Records | 6 years | Legal Obligation | Archive |

**Key regulatory sources:**
- NDPR 2019 (NITDA): General data protection requirements
- CBN AML/CFT Regulations 2013: 5-year KYC retention
- FIRS: 6-year financial record keeping
- PENCOM Guidelines: Employee pension records
- CBN Data Protection Circular 2021

---

## Dual-Framework Categories (5)

| # | Category | Retention | Legal Basis | Disposal |
|---|---|---|---|---|
| 26 | Cross-Border Data Transfer Records | 5 years | Legal Obligation | Archive |
| 27 | Privacy Notices & Policy Versions | 5 years from retirement | Legal Obligation | Archive |
| 28 | Children's Data | 5 years or until age 21 | Consent | Delete |
| 29 | Whistleblowing & Grievance Records | 5 years post-closure | Legal Obligation | Archive |
| 30 | Biometric Data | Until consent withdrawn | Consent | Delete |

---

## Customisation Guide

### Adding your organisation's specific categories:
1. Navigate to **Data Categories → Add Category**
2. Set `source` to `custom` (default for new entries)
3. Map to your existing data inventory

### Categories you may need to add for Nigerian businesses:
- PENCOM pension records (10 years)
- NIN verification records (duration of relationship)
- BVN-linked records (5 years post-relationship per CBN)
- SEC-regulated investment records (10 years)
- NAFDAC regulated product records (varies by product)
- NCC telecommunications records (per NCC Data Protection Regulations)

### Categories you may need to add for UK/EU businesses:
- Cookie consent logs (1 year)
- Direct marketing suppression lists (indefinite)
- Pension records (75 years from date of birth)
- Companies House filing records (permanent)
- VAT records (6 years)
