import hashlib
import time
from sqlalchemy.orm import Session
from app.models import DataCategory, AuditLog

COUNTRY_REGULATION_MAP = {
    'NG': ['NDPR', 'BOTH'],
    'GB': ['UK_GDPR', 'GDPR', 'BOTH'],
    'EU': ['GDPR', 'BOTH'],
    'US': ['CCPA', 'BOTH'],
    'BR': ['LGPD', 'BOTH'],
    'ZA': ['POPIA', 'BOTH'],
    'KE': ['DPA_KE', 'BOTH'],
    'GH': ['DPA_GH', 'BOTH'],
    'SG': ['PDPA_SG', 'BOTH'],
    'IN': ['DPDP', 'BOTH'],
    'AE': ['PDPL', 'BOTH'],
    'CA': ['PIPEDA', 'BOTH'],
    'AU': ['APPs', 'BOTH'],
    'EG': ['EGDPL', 'BOTH'],
    # EU / EEA member states → GDPR
    'AT': ['GDPR', 'BOTH'], 'BE': ['GDPR', 'BOTH'], 'BG': ['GDPR', 'BOTH'],
    'HR': ['GDPR', 'BOTH'], 'CY': ['GDPR', 'BOTH'], 'CZ': ['GDPR', 'BOTH'],
    'DK': ['GDPR', 'BOTH'], 'EE': ['GDPR', 'BOTH'], 'FI': ['GDPR', 'BOTH'],
    'FR': ['GDPR', 'BOTH'], 'DE': ['GDPR', 'BOTH'], 'GR': ['GDPR', 'BOTH'],
    'HU': ['GDPR', 'BOTH'], 'IE': ['GDPR', 'BOTH'], 'IT': ['GDPR', 'BOTH'],
    'LV': ['GDPR', 'BOTH'], 'LT': ['GDPR', 'BOTH'], 'LU': ['GDPR', 'BOTH'],
    'MT': ['GDPR', 'BOTH'], 'NL': ['GDPR', 'BOTH'], 'PL': ['GDPR', 'BOTH'],
    'PT': ['GDPR', 'BOTH'], 'RO': ['GDPR', 'BOTH'], 'SK': ['GDPR', 'BOTH'],
    'SI': ['GDPR', 'BOTH'], 'ES': ['GDPR', 'BOTH'], 'SE': ['GDPR', 'BOTH'],
    'IS': ['GDPR', 'BOTH'], 'LI': ['GDPR', 'BOTH'], 'NO': ['GDPR', 'BOTH'],
    'CH': ['GDPR', 'BOTH'],
    'OTHER': ['GDPR', 'BOTH'],
}


COUNTRY_REGULATION_LABELS = {
    'NG': {'authority': 'NITDA', 'law': 'NDPR/NDPA', 'audit_label': 'NDPR Annual Compliance Report'},
    'GB': {'authority': 'ICO', 'law': 'UK GDPR', 'audit_label': 'UK GDPR Annual Compliance Report'},
    'EU': {'authority': 'DPA (EU)', 'law': 'EU GDPR', 'audit_label': 'GDPR Annual Compliance Report'},
    'US': {'authority': 'State AG / FTC', 'law': 'CCPA/CPRA', 'audit_label': 'CCPA Annual Compliance Report'},
    'BR': {'authority': 'ANPD', 'law': 'LGPD', 'audit_label': 'LGPD Annual Compliance Report'},
    'ZA': {'authority': 'Information Regulator', 'law': 'POPIA', 'audit_label': 'POPIA Annual Compliance Report'},
    'KE': {'authority': 'ODPC', 'law': 'DPA Kenya', 'audit_label': 'DPA Kenya Annual Compliance Report'},
    'GH': {'authority': 'Data Protection Commission', 'law': 'DPA Ghana', 'audit_label': 'DPA Ghana Annual Compliance Report'},
    'SG': {'authority': 'PDPC', 'law': 'PDPA', 'audit_label': 'PDPA Annual Compliance Report'},
    'IN': {'authority': 'Data Protection Board', 'law': 'DPDP Act', 'audit_label': 'DPDP Annual Compliance Report'},
    'AE': {'authority': 'UAE Data Office', 'law': 'PDPL', 'audit_label': 'PDPL Annual Compliance Report'},
    'CA': {'authority': 'OPC', 'law': 'PIPEDA', 'audit_label': 'PIPEDA Annual Compliance Report'},
    'AU': {'authority': 'OAIC', 'law': 'Privacy Act / APPs', 'audit_label': 'APPs Annual Compliance Report'},
    'EG': {'authority': 'Data Protection Center', 'law': 'EGDPL', 'audit_label': 'EGDPL Annual Compliance Report'},
    'OTHER': {'authority': 'National Data Authority', 'law': 'General Data Protection (GDPR-aligned)', 'audit_label': 'Annual Compliance Report'},
}

ADRS_SUPPORTED_COUNTRIES = {
    # ── Countries with explicit regulation mappings ──
    'NG': 'Nigeria', 'GB': 'United Kingdom', 'US': 'United States', 'EU': 'European Union',
    'CA': 'Canada', 'AU': 'Australia', 'IN': 'India', 'AE': 'United Arab Emirates',
    'ZA': 'South Africa', 'KE': 'Kenya', 'GH': 'Ghana', 'SG': 'Singapore', 'BR': 'Brazil',
    'EG': 'Egypt',
    # ── EU / EEA member states (mapped → GDPR) ──
    'AT': 'Austria', 'BE': 'Belgium', 'BG': 'Bulgaria', 'HR': 'Croatia', 'CY': 'Cyprus',
    'CZ': 'Czech Republic', 'DK': 'Denmark', 'EE': 'Estonia', 'FI': 'Finland', 'FR': 'France',
    'DE': 'Germany', 'GR': 'Greece', 'HU': 'Hungary', 'IE': 'Ireland', 'IT': 'Italy',
    'LV': 'Latvia', 'LT': 'Lithuania', 'LU': 'Luxembourg', 'MT': 'Malta', 'NL': 'Netherlands',
    'PL': 'Poland', 'PT': 'Portugal', 'RO': 'Romania', 'SK': 'Slovakia', 'SI': 'Slovenia',
    'ES': 'Spain', 'SE': 'Sweden', 'IS': 'Iceland', 'LI': 'Liechtenstein', 'NO': 'Norway',
    'CH': 'Switzerland',
    # ── All other countries (A-Z) ──
    'AF': 'Afghanistan', 'AL': 'Albania', 'DZ': 'Algeria', 'AD': 'Andorra', 'AO': 'Angola',
    'AG': 'Antigua and Barbuda', 'AR': 'Argentina', 'AM': 'Armenia', 'AZ': 'Azerbaijan',
    'BS': 'Bahamas', 'BH': 'Bahrain', 'BD': 'Bangladesh', 'BB': 'Barbados', 'BY': 'Belarus',
    'BZ': 'Belize', 'BJ': 'Benin', 'BT': 'Bhutan', 'BO': 'Bolivia',
    'BA': 'Bosnia and Herzegovina', 'BW': 'Botswana', 'BN': 'Brunei', 'BF': 'Burkina Faso',
    'BI': 'Burundi', 'CV': 'Cabo Verde', 'KH': 'Cambodia', 'CM': 'Cameroon',
    'CF': 'Central African Republic', 'TD': 'Chad', 'CL': 'Chile', 'CN': 'China',
    'CO': 'Colombia', 'KM': 'Comoros', 'CG': 'Congo', 'CD': 'Congo (DRC)', 'CR': 'Costa Rica',
    'CI': "Côte d'Ivoire", 'CU': 'Cuba', 'DJ': 'Djibouti', 'DM': 'Dominica',
    'DO': 'Dominican Republic', 'EC': 'Ecuador', 'SV': 'El Salvador', 'GQ': 'Equatorial Guinea',
    'ER': 'Eritrea', 'SZ': 'Eswatini', 'ET': 'Ethiopia', 'FJ': 'Fiji', 'GA': 'Gabon',
    'GM': 'Gambia', 'GE': 'Georgia', 'GT': 'Guatemala', 'GN': 'Guinea', 'GW': 'Guinea-Bissau',
    'GY': 'Guyana', 'HT': 'Haiti', 'HN': 'Honduras', 'IQ': 'Iraq', 'IL': 'Israel',
    'JM': 'Jamaica', 'JP': 'Japan', 'JO': 'Jordan', 'KZ': 'Kazakhstan', 'KI': 'Kiribati',
    'KP': 'North Korea', 'KR': 'South Korea', 'KW': 'Kuwait', 'KG': 'Kyrgyzstan',
    'LA': 'Laos', 'LB': 'Lebanon', 'LS': 'Lesotho', 'LR': 'Liberia', 'LY': 'Libya',
    'MG': 'Madagascar', 'MW': 'Malawi', 'MY': 'Malaysia', 'MV': 'Maldives', 'ML': 'Mali',
    'MH': 'Marshall Islands', 'MR': 'Mauritania', 'MU': 'Mauritius', 'MX': 'Mexico',
    'FM': 'Micronesia', 'MD': 'Moldova', 'MC': 'Monaco', 'MN': 'Mongolia', 'ME': 'Montenegro',
    'MA': 'Morocco', 'MZ': 'Mozambique', 'MM': 'Myanmar', 'NA': 'Namibia', 'NR': 'Nauru',
    'NP': 'Nepal', 'NZ': 'New Zealand', 'NI': 'Nicaragua', 'NE': 'Niger', 'MK': 'North Macedonia',
    'OM': 'Oman', 'PK': 'Pakistan', 'PW': 'Palau', 'PS': 'Palestine', 'PA': 'Panama',
    'PG': 'Papua New Guinea', 'PY': 'Paraguay', 'PE': 'Peru', 'PH': 'Philippines',
    'QA': 'Qatar', 'RU': 'Russia', 'RW': 'Rwanda', 'KN': 'Saint Kitts and Nevis',
    'LC': 'Saint Lucia', 'VC': 'Saint Vincent and the Grenadines', 'WS': 'Samoa',
    'SM': 'San Marino', 'ST': 'São Tomé and Príncipe', 'SA': 'Saudi Arabia', 'SN': 'Senegal',
    'RS': 'Serbia', 'SC': 'Seychelles', 'SL': 'Sierra Leone', 'SB': 'Solomon Islands',
    'SO': 'Somalia', 'SS': 'South Sudan', 'LK': 'Sri Lanka', 'SD': 'Sudan', 'SR': 'Suriname',
    'SY': 'Syria', 'TW': 'Taiwan', 'TJ': 'Tajikistan', 'TZ': 'Tanzania', 'TH': 'Thailand',
    'TL': 'Timor-Leste', 'TG': 'Togo', 'TO': 'Tonga', 'TT': 'Trinidad and Tobago',
    'TN': 'Tunisia', 'TR': 'Turkey', 'TM': 'Turkmenistan', 'TV': 'Tuvalu', 'UG': 'Uganda',
    'UA': 'Ukraine', 'UY': 'Uruguay', 'UZ': 'Uzbekistan', 'VU': 'Vanuatu', 'VA': 'Vatican City',
    'VE': 'Venezuela', 'VN': 'Vietnam', 'YE': 'Yemen', 'ZM': 'Zambia', 'ZW': 'Zimbabwe',
}

# Pricing Catalog
PRICING_PLANS = {
    'monthly': {'amount_cents': 4000, 'label': '$40', 'interval': 'month'},
    'yearly': {'amount_cents': 39900, 'label': '$399', 'interval': 'year', 'savings': 'Save $81'},
}

def get_country_regulations(country_code: str) -> list:
    return COUNTRY_REGULATION_MAP.get(country_code.upper(), COUNTRY_REGULATION_MAP['OTHER'])

def get_country_regulation_labels(country_code: str) -> dict:
    return COUNTRY_REGULATION_LABELS.get(country_code.upper(), COUNTRY_REGULATION_LABELS['OTHER'])

def detect_visitor_currency(country_code: str) -> dict:
    code = country_code.upper()
    if code == 'NG':
        return {'code': 'NGN', 'symbol': '₦', 'rate': 1500.0}
    elif code == 'GB':
        return {'code': 'GBP', 'symbol': '£', 'rate': 0.78}
    elif code in ['EU', 'FR', 'DE', 'IT', 'ES', 'NL', 'BE', 'IE']:
        return {'code': 'EUR', 'symbol': '€', 'rate': 0.92}
    else:
        return {'code': 'USD', 'symbol': '$', 'rate': 1.0}

def get_framework_badge(framework: str) -> str:
    f = framework.upper()
    if f == 'GDPR' or f == 'UK_GDPR':
        return 'badge-gdpr'
    elif f == 'NDPR':
        return 'badge-ndpr'
    elif f == 'CCPA':
        return 'badge-ccpa'
    elif f == 'LGPD':
        return 'badge-lgpd'
    elif f == 'POPIA':
        return 'badge-popia'
    elif f == 'DPDP':
        return 'badge-dpdp'
    elif f == 'PDPL':
        return 'badge-pdpl'
    elif f == 'PIPEDA':
        return 'badge-pipeda'
    elif f == 'APPs':
        return 'badge-apps'
    elif f == 'EGDPL':
        return 'badge-egdpl'
    else:
        return 'bg-secondary'

# Cryptographic chain logger
def log_audit(db: Session, org_id: int, action: str, entity_type: str, entity_id: int, performed_by: int, details: dict, ip_address: str):
    import json as _json
    from datetime import datetime as _dt

    # Fetch previous log hash
    prev_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = prev_log.row_hash if prev_log else "0" * 64

    # Normalise details to canonical, key-sorted JSON (PHP-compatible)
    if details is None:
        details_str = ""
    elif isinstance(details, str):
        details_str = details
    else:
        details_str = _json.dumps(details, sort_keys=True, ensure_ascii=False)

    # Canonical hash payload matches PHP audit_canonical() format
    created_at_str = _dt.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    payload = "|".join([
        str(org_id), action, entity_type,
        str(entity_id) if entity_id is not None else "",
        str(performed_by) if performed_by is not None else "",
        details_str, str(ip_address or ""), prev_hash, created_at_str,
    ])
    row_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()

    log_entry = AuditLog(
        organization_id=org_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        performed_by=performed_by,
        details=details,
        ip_address=ip_address,
        prev_hash=prev_hash,
        row_hash=row_hash
    )
    db.add(log_entry)
    db.commit()

# ═══════════════════════════════════════════════════════════════════════════
#   Dynamic category templates — FULL replica of PHP seed_categories_only.sql
#   Tuple: (name, description, legal_basis, days, label, method, trigger,
#           dual_approval, review_frequency)
# ═══════════════════════════════════════════════════════════════════════════
CATEGORY_SEEDS = {
    # ──────────────────────────────────────────────────────────────────────
    #  GDPR (EU / UK) — 15 entries
    # ──────────────────────────────────────────────────────────────────────
    'GDPR': [
        ('Employee Personnel Records',
         'Full employment records: contracts, appraisals, disciplinary actions, payroll history, termination documents.',
         'legal_obligation', 2190, '6 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Employee Payroll & Tax Records',
         'Payroll runs, P60s, P45s, HMRC submissions, tax codes, National Insurance records.',
         'legal_obligation', 2555, '7 years (HMRC requirement)', 'archive', 'date_based', False, 'annually'),
        ('Recruitment & Application Data',
         'CVs, cover letters, interview notes, and assessment results for unsuccessful candidates.',
         'legitimate_interest', 180, '6 months post-rejection', 'delete', 'date_based', False, 'quarterly'),
        ('Customer Contracts & Agreements',
         'Signed contracts, SOWs, MSAs, NDAs, and service agreements with clients.',
         'contract', 2555, '7 years post-expiry', 'archive', 'date_based', False, 'annually'),
        ('Marketing Consent Records',
         'Email opt-in records, consent timestamps, preference centre logs, and withdrawal records.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
        ('Website & Server Access Logs',
         'Web server logs, access logs, error logs, IP addresses of visitors.',
         'legitimate_interest', 180, '6 months', 'delete', 'date_based', False, 'quarterly'),
        ('Customer Support Tickets',
         'Support communications, complaint records, resolution logs, and related correspondence.',
         'contract', 1095, '3 years post-resolution', 'anonymise', 'date_based', False, 'quarterly'),
        ('Financial Transactions & Invoices',
         'Invoices, receipts, purchase orders, bank statements, and VAT records.',
         'legal_obligation', 2555, '7 years (HMRC/Companies Act)', 'archive', 'date_based', False, 'annually'),
        ('Health & Medical Records (Employees)',
         'Occupational health reports, sick notes, disability assessments, return-to-work plans.',
         'legal_obligation', 3650, '10 years post-employment', 'delete', 'date_based', True, 'annually'),
        ('CCTV Footage',
         'Video surveillance footage from office and facility cameras.',
         'legitimate_interest', 30, '30 days', 'delete', 'date_based', False, 'monthly'),
        ('Data Breach Incident Records',
         'Records of personal data breaches, impact assessments, notifications to ICO and data subjects.',
         'legal_obligation', 1825, '5 years (ICO requirement)', 'archive', 'date_based', False, 'annually'),
        ('DSAR Records',
         'All requests received under Articles 15-22 GDPR: access, rectification, erasure, portability.',
         'legal_obligation', 1095, '3 years post-closure', 'archive', 'date_based', False, 'annually'),
        ('Supplier & Vendor Contracts',
         'Third-party processing agreements, DPAs, supplier due diligence records.',
         'contract', 2555, '7 years post-expiry', 'archive', 'date_based', False, 'annually'),
        ('DPIA Reports',
         'Data Protection Impact Assessments under Article 35 GDPR.',
         'legal_obligation', 1825, '5 years or life of processing', 'archive', 'date_based', False, 'annually'),
        ('Training & Certification Records',
         'Data protection training completion records, certificates, awareness logs.',
         'legal_obligation', 1095, '3 years', 'delete', 'date_based', False, 'annually'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  NDPR (Nigeria) — 10 entries
    # ──────────────────────────────────────────────────────────────────────
    'NDPR': [
        ('Customer KYC & Onboarding Data',
         'KYC records, identity verification, CAC documents, utility bills, onboarding forms (CBN / NITDA).',
         'legal_obligation', 1825, '5 years post-relationship (CBN AML)', 'archive', 'date_based', False, 'annually'),
        ('Employee Personal Data (NDPR)',
         'Nigerian employee records: BVN, NIN, state of origin, guarantor forms, employment contracts.',
         'legal_obligation', 2555, '7 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Financial Records (FIRS Compliance)',
         'Tax filings, WHT, VAT returns, CIT records, FIRS correspondence.',
         'legal_obligation', 2190, '6 years (FIRS requirement)', 'archive', 'date_based', False, 'annually'),
        ('Customer Personal Data (Nigeria)',
         'Names, phone numbers, email addresses, addresses, DOB of Nigerian customers.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Health Data (Employees - Nigeria)',
         'HMO records, hospital referral letters, sick leave records, health fund documentation.',
         'legal_obligation', 3650, '10 years', 'delete', 'date_based', True, 'annually'),
        ('Consent Records (NDPR)',
         'Written or electronic consent under NDPR Section 2.2 for marketing, data sharing, or processing.',
         'consent', 0, 'Duration of purpose + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
        ('Third-Party Data Sharing Agreements',
         'Contracts and DPAs with third parties processing personal data of Nigerian data subjects.',
         'legal_obligation', 2555, '7 years', 'archive', 'date_based', False, 'annually'),
        ('Data Breach Records (NDPR)',
         'Breach notifications to NITDA, data subject notifications, incident reports per NDPR Article 4.1.',
         'legal_obligation', 1825, '5 years', 'archive', 'date_based', False, 'annually'),
        ('Annual Data Audit Reports',
         'Annual data protection audit reports for NITDA or internal use per NDPR Framework.',
         'legal_obligation', 2555, '7 years', 'archive', 'date_based', False, 'annually'),
        ('Procurement & Tender Records (Nigeria)',
         'Procurement records, supplier evaluations, tender documents under NDPR and Public Procurement Act.',
         'legal_obligation', 2190, '6 years', 'archive', 'date_based', False, 'annually'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  BOTH (Dual-Framework: GDPR + NDPR) — 5 entries
    # ──────────────────────────────────────────────────────────────────────
    'BOTH': [
        ('Cross-Border Data Transfer Records',
         'Records of personal data transfers outside Nigeria or UK/EU: SCCs, adequacy decisions, transfer mechanisms.',
         'legal_obligation', 1825, '5 years', 'archive', 'date_based', False, 'annually'),
        ('Privacy Notices & Policy Versions',
         'All versions of privacy notices, cookie policies, and terms of service with effective dates.',
         'legal_obligation', 1825, '5 years from version retirement', 'archive', 'date_based', False, 'annually'),
        ("Children's Data (Under 13/18)",
         'Any personal data of minors, parental consent records, age verification logs.',
         'consent', 0, '5 years or until data subject turns 21', 'delete', 'consent_withdrawal', True, 'quarterly'),
        ('Whistleblowing & Grievance Records',
         'Internal reports, investigation records, outcomes related to data protection complaints.',
         'legal_obligation', 1825, '5 years post-closure', 'archive', 'date_based', False, 'annually'),
        ('Biometric Data',
         'Fingerprints, facial recognition data, voice prints, retina scans used for access or verification.',
         'consent', 0, 'Until consent withdrawn or employment/relationship ends', 'delete', 'consent_withdrawal', True, 'quarterly'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  CCPA (United States) — 5 entries
    # ──────────────────────────────────────────────────────────────────────
    'CCPA': [
        ('Consumer Request Records (CCPA)',
         'Records of consumer access, deletion, and opt-out requests under CCPA/CPRA Section 1798.105.',
         'legal_obligation', 730, '2 years from request date', 'archive', 'date_based', False, 'annually'),
        ('Marketing Opt-Out Records (CCPA)',
         'Do-Not-Sell / Do-Not-Share consumer preference logs under CCPA Section 1798.120.',
         'consent', 0, 'Until consumer withdraws opt-out or 2 years evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
        ('Employee and Applicant Data (CCPA)',
         'Employee personal data, applicant records, and B2B contact details covered by CCPA/CPRA.',
         'legal_obligation', 2555, '7 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Financial Transaction Records (US)',
         'Payment records, invoices, receipts subject to IRS retention rules.',
         'legal_obligation', 2555, '7 years (IRS requirement)', 'archive', 'date_based', False, 'annually'),
        ('Customer PII (CCPA)',
         'Names, emails, phone numbers, addresses, and identifiers of California consumers.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  LGPD (Brazil) — 5 entries
    # ──────────────────────────────────────────────────────────────────────
    'LGPD': [
        ('Data Subject Request Records (LGPD)',
         'Records of data subject rights requests under LGPD Articles 17-22: access, correction, deletion, portability.',
         'legal_obligation', 1825, '5 years from request closure', 'archive', 'date_based', False, 'annually'),
        ('Consent Records (LGPD)',
         'Consent collection and withdrawal logs under LGPD Article 8.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
        ('Employee Records (LGPD/CLT)',
         'Employment contracts, payroll, FGTS, INSS, and termination records under CLT requirements.',
         'legal_obligation', 1825, '5 years post-employment (CLT)', 'delete', 'date_based', False, 'annually'),
        ('Financial Records (Brazil)',
         'Tax filings, NF-e invoices, and Receita Federal correspondence.',
         'legal_obligation', 1825, '5 years (Receita Federal)', 'archive', 'date_based', False, 'annually'),
        ('Customer Personal Data (Brazil)',
         'Names, CPF numbers, emails, phone numbers of Brazilian customers.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  POPIA (South Africa) — 5 entries
    # ──────────────────────────────────────────────────────────────────────
    'POPIA': [
        ('PAIA Request Records',
         'Records of access requests under Promotion of Access to Information Act (PAIA).',
         'legal_obligation', 1095, '3 years post-closure', 'archive', 'date_based', False, 'annually'),
        ('Employee Records (BCEA)',
         'Employment contracts, payroll, UIF records, and termination documents under Basic Conditions of Employment Act.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Customer Personal Information (SA)',
         'Names, ID numbers, contact details, and addresses of South African data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Financial Records (SARS)',
         'Tax returns, VAT records, and SARS correspondence.',
         'legal_obligation', 1825, '5 years (SARS requirement)', 'archive', 'date_based', False, 'annually'),
        ('Consent Records (POPIA)',
         'Consent collection and withdrawal logs under POPIA Section 11.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  DPA_KE (Kenya) — 3 entries
    # ──────────────────────────────────────────────────────────────────────
    'DPA_KE': [
        ('Customer Personal Data (Kenya DPA)',
         'Names, national ID, phone numbers, email addresses of Kenyan data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Kenya)',
         'Employment contracts, NHIF, NSSF records, and payroll data.',
         'legal_obligation', 2190, '6 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Kenya DPA)',
         'Consent logs and withdrawal records under the Kenya Data Protection Act.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  DPA_GH (Ghana) — 3 entries
    # ──────────────────────────────────────────────────────────────────────
    'DPA_GH': [
        ('Customer Personal Data (Ghana DPA)',
         'Names, Ghana Card numbers, phone numbers, email addresses of Ghanaian data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Ghana)',
         'Employment contracts, SSNIT records, and payroll data under Ghanaian labour law.',
         'legal_obligation', 2190, '6 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Ghana DPA)',
         'Consent logs and withdrawal records under the Ghana Data Protection Act.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  PDPA_SG (Singapore) — 3 entries
    # ──────────────────────────────────────────────────────────────────────
    'PDPA_SG': [
        ('Customer Personal Data (PDPA Singapore)',
         'Names, NRIC/FIN, phone numbers, email addresses of Singaporean data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (MOM/Singapore)',
         'Employment contracts, CPF records, and payroll data under Singapore Employment Act and MOM requirements.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (PDPA)',
         'Consent collection and withdrawal logs under PDPA obligations.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  DPDP (India) — 3 entries
    # ──────────────────────────────────────────────────────────────────────
    'DPDP': [
        ('Customer Personal Data (India DPDP)',
         'Names, Aadhaar references, phone numbers, email addresses of Indian data principals.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (India)',
         'Employment contracts, PF/ESI records, Form 16, and payroll data under Indian labour law.',
         'legal_obligation', 2555, '7 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (DPDP)',
         'Consent collection and withdrawal logs under DPDP Act Section 6.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  PDPL (UAE) — 3 entries
    # ──────────────────────────────────────────────────────────────────────
    'PDPL': [
        ('Customer Personal Data (UAE PDPL)',
         'Names, Emirates ID references, phone numbers, email addresses of UAE data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (UAE)',
         'Employment contracts, WPS payroll records, visa and labour card data under UAE labour law.',
         'legal_obligation', 730, '2 years post-employment (UAE Labour Law)', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (PDPL)',
         'Consent collection and withdrawal logs under UAE PDPL.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  PIPEDA (Canada) — 3 entries
    # ──────────────────────────────────────────────────────────────────────
    'PIPEDA': [
        ('Customer Personal Information (Canada PIPEDA)',
         'Names, SIN references, phone numbers, email addresses of Canadian individuals.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Canada)',
         'Employment contracts, T4 records, payroll, and benefits data under CRA requirements.',
         'legal_obligation', 2555, '7 years post-employment (CRA)', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (PIPEDA)',
         'Consent collection and withdrawal logs under PIPEDA Principle 3.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  APPs (Australia) — 3 entries
    # ──────────────────────────────────────────────────────────────────────
    'APPs': [
        ('Customer Personal Information (Australia APPs)',
         'Names, TFN references, phone numbers, email addresses of Australian individuals.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Australia)',
         'Employment contracts, superannuation, payroll, and tax records under Fair Work Act and ATO requirements.',
         'legal_obligation', 2555, '7 years post-employment (ATO)', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (APPs)',
         'Consent collection and withdrawal logs under Australian Privacy Principle 3.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  EGDPL (Egypt) — 3 entries
    # ──────────────────────────────────────────────────────────────────────
    'EGDPL': [
        ('Customer Personal Data (Egypt EGDPL)',
         'Names, national ID numbers, phone numbers, email addresses of Egyptian data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Egypt)',
         'Employment contracts, social insurance records, and payroll data under Egyptian labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (EGDPL)',
         'Consent collection and withdrawal logs under Egypt Data Protection Law No. 151.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],
}


def provision_org_categories(db: Session, org_id: int, country_code: str):
    """
    Seed data categories for a new organisation based on country → regulation mapping.
    Also creates a default retention rule for each seeded category (PHP parity).
    """
    from app.models import CategoryRetentionRule

    frameworks = get_country_regulations(country_code)
    for fw in frameworks:
        seeds = CATEGORY_SEEDS.get(fw, [])
        for name, desc, basis, days, label, method, trigger, dual, review_freq in seeds:
            # Check if category already exists for this org
            exists = db.query(DataCategory).filter(
                DataCategory.organization_id == org_id,
                DataCategory.name == name
            ).first()
            if not exists:
                cat = DataCategory(
                    organization_id=org_id,
                    name=name,
                    description=desc,
                    compliance_framework=fw,
                    legal_basis=basis,
                    retention_period_days=days,
                    retention_period_label=label,
                    disposal_method=method,
                    disposal_trigger=trigger,
                    requires_dual_approval=dual,
                    review_frequency=review_freq,
                    source='seeded'
                )
                db.add(cat)
                db.flush()  # get cat.id for rule creation

                # Create default retention rule for this category (PHP parity)
                rule = CategoryRetentionRule(
                    organization_id=org_id,
                    category_id=cat.id,
                    rule_name=f"Default — {label}",
                    legal_basis=basis,
                    processing_purpose=desc,
                    institution_type='all',
                    retention_period_days=days,
                    retention_period_label=label,
                    disposal_method=method,
                    disposal_trigger=trigger,
                    requires_dual_approval=dual,
                    is_default=True,
                    sort_order=0,
                )
                db.add(rule)
    db.commit()


def clone_category_retention_rules(db: Session, source_org_id: int, target_org_id: int):
    """Clone retention rules from one org to another (used in tenant provisioning)."""
    from app.models import CategoryRetentionRule
    rules = db.query(CategoryRetentionRule).filter(
        CategoryRetentionRule.organization_id == source_org_id
    ).all()
    for r in rules:
        # Find matching category by name in target org
        target_cat = db.query(DataCategory).filter(
            DataCategory.organization_id == target_org_id,
            DataCategory.name == db.query(DataCategory.name).filter(
                DataCategory.id == r.category_id
            ).scalar_subquery()
        ).first()
        if target_cat:
            existing = db.query(CategoryRetentionRule).filter(
                CategoryRetentionRule.organization_id == target_org_id,
                CategoryRetentionRule.category_id == target_cat.id,
                CategoryRetentionRule.rule_name == r.rule_name,
            ).first()
            if not existing:
                new_rule = CategoryRetentionRule(
                    organization_id=target_org_id,
                    category_id=target_cat.id,
                    rule_name=r.rule_name,
                    legal_basis=r.legal_basis,
                    processing_purpose=r.processing_purpose,
                    institution_type=r.institution_type,
                    retention_period_days=r.retention_period_days,
                    retention_period_label=r.retention_period_label,
                    disposal_method=r.disposal_method,
                    disposal_trigger=r.disposal_trigger,
                    requires_dual_approval=r.requires_dual_approval,
                    is_default=r.is_default,
                    sort_order=r.sort_order,
                )
                db.add(new_rule)
    db.commit()

import base64
import hashlib
import hmac
import struct
import time
import secrets
import urllib.parse

def totp_generate_secret() -> str:
    rand_bytes = secrets.token_bytes(20)
    return base64.b32encode(rand_bytes).decode('utf-8').replace('=', '')

def totp_code(secret_b32: str, timestamp: int = None, period: int = 30, digits: int = 6) -> str:
    secret_b32 = secret_b32.upper().strip()
    missing_padding = len(secret_b32) % 8
    if missing_padding:
        secret_b32 += '=' * (8 - missing_padding)
    key = base64.b32decode(secret_b32)
    t = timestamp or int(time.time())
    counter = t // period
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    part = struct.unpack(">I", h[offset:offset+4])[0] & 0x7FFFFFFF
    code = part % (10 ** digits)
    return str(code).zfill(digits)

def totp_verify(secret_b32: str, code: str, window: int = 1, period: int = 30) -> bool:
    try:
        code = "".join(code.split())
        if not code.isdigit() or len(code) != 6:
            return False
        now = int(time.time())
        for i in range(-window, window + 1):
            if totp_code(secret_b32, now + i * period, period) == code:
                return True
        return False
    except Exception:
        return False

def totp_uri(secret_b32: str, account: str, issuer: str) -> str:
    label = f"{issuer}:{account}"
    return f"otpauth://totp/{urllib.parse.quote(label)}?secret={secret_b32}&issuer={urllib.parse.quote(issuer)}&period=30&digits=6"

def generate_recovery_codes(n: int = 8) -> dict:
    plain = []
    hashed = []
    for _ in range(n):
        code = secrets.token_hex(5).upper()
        code = code[:5] + '-' + code[5:]
        plain.append(code)
        hashed.append(hashlib.sha256(code.encode('utf-8')).hexdigest())
    return {'plain': plain, 'hashed': hashed}

def consume_recovery_code(hashed_codes: list, candidate: str) -> list:
    c = candidate.strip().upper()
    h = hashlib.sha256(c.encode('utf-8')).hexdigest()
    if h in hashed_codes:
        new_list = list(hashed_codes)
        new_list.remove(h)
        return new_list
    return None

def send_system_email(db: Session, to_email: str, subject: str, html_body: str) -> bool:
    import smtplib
    import os
    from datetime import datetime
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from app.models import SystemSetting
    from app.config import LOG_PATH

    # Fetch settings
    settings = {}
    for row in db.query(SystemSetting).filter(SystemSetting.setting_key.like("smtp%")).all():
        settings[row.setting_key] = row.setting_value
    
    host = settings.get("smtp_host", "")
    if not host or "yourdomain" in host.lower():
        # Log to console
        print(f"--- EMAIL CONSOLE LOG (SMTP not configured) ---")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body: {html_body[:200]}...")
        print(f"------------------------------------------------")
        return True

    from_email = settings.get("smtp_from_email", "no-reply@localhost")
    from_name = settings.get("smtp_from_name", "ADRS")
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))
        
        port = int(settings.get("smtp_port", "587"))
        user = settings.get("smtp_user", "") or settings.get("smtp_username", "")
        password = settings.get("smtp_pass", "") or settings.get("smtp_password", "")
        secure = settings.get("smtp_secure", "tls") or settings.get("smtp_encryption", "tls")

        # Connect
        if secure == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            if secure == "tls":
                server.starttls()

        if user and password:
            server.login(user, password)
            
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Mail delivery failed: {e}")
        log_file = os.path.join(LOG_PATH, "mail_errors.log")
        try:
            with open(log_file, "a") as f:
                f.write(f"[{datetime.now().isoformat()}] {e}\n")
        except Exception:
            pass
        return False


# ═══════════════════════════════════════════════════════════════════════════
#   Email Templates (ported from PHP email_templates.php)
# ═══════════════════════════════════════════════════════════════════════════

def _escape_html(text: str) -> str:
    """HTML entity escape for use in email templates."""
    import html
    return html.escape(str(text), quote=True)


def email_layout(title: str, body_html: str) -> str:
    """Wrap body HTML in the 3Consulting-branded email shell."""
    from datetime import datetime
    year = datetime.utcnow().year
    return (
        '<!doctype html><html><body style="margin:0;background:#f4f4f4;font-family:Arial,Helvetica,sans-serif;">'
        '<div style="max-width:600px;margin:0 auto;background:#fff;">'
        '<div style="background:#ff914d;color:#fff;padding:18px 24px;font-size:20px;font-weight:bold;">ADRS</div>'
        '<div style="padding:24px;color:#222;">'
        f'<h2 style="color:#1A6187;margin-top:0;">{_escape_html(title)}</h2>'
        f'{body_html}'
        '</div>'
        f'<div style="padding:16px 24px;background:#1A1A2E;color:#cfd2dc;font-size:12px;">&copy; {year}'
        ' 3Consulting Limited &middot; ADRS</div>'
        '</div></body></html>'
    )


def render_notification_email(notification: dict) -> str:
    """Render an email for a stored notification row (subject + message)."""
    msg = _escape_html(notification.get('message', '')).replace('\n', '<br>')
    return email_layout(notification.get('subject', 'Notification'), f'<p>{msg}</p>')


def email_password_reset(name: str, reset_link: str) -> tuple:
    """Password-reset email. Returns (subject, html)."""
    body = (
        f'<p>Hello {_escape_html(name)},</p>'
        '<p>A password reset was requested for your ADRS account. This link is valid for 1 hour:</p>'
        f'<p><a href="{_escape_html(reset_link)}" style="background:#ff914d;color:#fff;padding:10px 18px;'
        'text-decoration:none;border-radius:4px;display:inline-block;">Reset your password</a></p>'
        '<p>If you did not request this, you can safely ignore this email.</p>'
    )
    return ('Reset your ADRS password', email_layout('Password reset', body))


def email_verification(name: str, verify_link: str) -> tuple:
    """Email verification for new registrations. Returns (subject, html)."""
    body = (
        f'<p>Hello {_escape_html(name)},</p>'
        '<p>Welcome to ADRS. Please verify your email address to activate your account:</p>'
        f'<p><a href="{_escape_html(verify_link)}" style="background:#ff914d;color:#fff;padding:10px 18px;'
        'text-decoration:none;border-radius:4px;display:inline-block;">Verify my email</a></p>'
        '<p>If you did not create an account, ignore this message.</p>'
    )
    return ('Verify your ADRS account', email_layout('Email verification', body))


def email_team_invite(name: str, org_name: str, role: str, invite_link: str) -> tuple:
    """Team invitation email. Returns (subject, html)."""
    role_labels = {'admin': 'Administrator', 'dpo': 'Data Protection Officer', 'data_owner': 'Data Owner'}
    role_label = role_labels.get(role, role)
    body = (
        f'<p>Hello {_escape_html(name)},</p>'
        f'<p>You have been invited to join <strong>{_escape_html(org_name)}</strong> on ADRS'
        f' as <strong>{_escape_html(role_label)}</strong>.</p>'
        '<p>ADRS is your organisation\'s automated data retention and compliance portal.</p>'
        f'<p><a href="{_escape_html(invite_link)}" style="background:#ff914d;color:#fff;padding:10px 18px;'
        'text-decoration:none;border-radius:4px;display:inline-block;">Accept invitation</a></p>'
        '<p>This link expires in 7 days. If you were not expecting this, you can ignore this email.</p>'
    )
    return (f"You're invited to ADRS — {org_name}", email_layout('Team invitation', body))
