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
    'NG': 'Nigeria', 'GB': 'United Kingdom', 'US': 'United States', 'EU': 'European Union',
    'CA': 'Canada', 'AU': 'Australia', 'IN': 'India', 'AE': 'United Arab Emirates',
    'ZA': 'South Africa', 'KE': 'Kenya', 'GH': 'Ghana', 'SG': 'Singapore', 'BR': 'Brazil',
    'EG': 'Egypt', 'AF': 'Afghanistan', 'AL': 'Albania', 'DZ': 'Algeria', 'AD': 'Andorra',
    'AO': 'Angola', 'AG': 'Antigua and Barbuda', 'AR': 'Argentina', 'AM': 'Armenia',
    'AT': 'Austria', 'AZ': 'Azerbaijan', 'BS': 'Bahamas', 'BH': 'Bahrain', 'BD': 'Bangladesh',
    'BB': 'Barbados', 'BY': 'Belarus', 'BE': 'Belgium', 'BZ': 'Belize', 'BJ': 'Benin',
    'BT': 'Bhutan', 'BO': 'Bolivia', 'BA': 'Bosnia and Herzegovina', 'BW': 'Botswana',
    'BN': 'Brunei', 'BG': 'Bulgaria', 'BF': 'Burkina Faso', 'BI': 'Burundi',
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
    # Fetch previous log hash
    prev_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = prev_log.row_hash if prev_log else "0" * 64

    # Calculate current log canonical content hash
    details_str = str(details or {})
    payload = f"{org_id}|{action}|{entity_type}|{entity_id}|{performed_by}|{details_str}|{ip_address}|{prev_hash}"
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

# Dynamic category templates provider
CATEGORY_SEEDS = {
    'GDPR': [
        ('Employee Personnel Records', 'Personnel files and agreements.', 'legal_obligation', 2190, '6 years', 'delete', 'date_based', False),
        ('Employee Payroll & Tax Records', 'Payroll runs and HMRC files.', 'legal_obligation', 2555, '7 years', 'archive', 'date_based', False),
        ('Recruitment Application Data', 'CVs for unsuccessful candidates.', 'legitimate_interest', 180, '6 months', 'delete', 'date_based', False),
        ('Marketing Consent Records', 'Opt-in timestamps and logs.', 'consent', 0, 'Until consent withdrawn', 'delete', 'consent_withdrawal', False),
        ('Health & Medical Records', 'Occupational health notes.', 'legal_obligation', 3650, '10 years', 'delete', 'date_based', True)
    ],
    'NDPR': [
        ('NDPR Employee Onboarding Files', 'Employee agreements under NDPR.', 'consent', 2190, '6 years', 'delete', 'date_based', False),
        ('NDPR Tax Audit Invoices', 'Financial documentation.', 'legal_obligation', 2555, '7 years', 'archive', 'date_based', False),
        ('NDPR Customer Consent Log', 'Opt-in/out user consent proofs.', 'consent', 0, 'Until withdrawn', 'delete', 'consent_withdrawal', False)
    ],
    'DPDP': [
        ('DPDP Employee Data Records', 'Employee agreements and onboarding.', 'legal_obligation', 2190, '6 years', 'delete', 'date_based', False),
        ('DPDP Customer PII', 'Customer identity records.', 'consent', 0, 'Until withdrawn', 'delete', 'consent_withdrawal', False),
        ('DPDP Consent Verification Log', 'Consent audit logs.', 'consent', 365, '1 year', 'delete', 'date_based', False)
    ],
    'PDPL': [
        ('PDPL HR & Payroll Data', 'Employee payroll files.', 'legal_obligation', 2190, '6 years', 'delete', 'date_based', False),
        ('PDPL Customer Identity Records', 'Customer profiles.', 'consent', 0, 'Until withdrawn', 'delete', 'consent_withdrawal', False),
        ('PDPL Operations Audit Trail', 'System operation logs.', 'legal_obligation', 1825, '5 years', 'archive', 'date_based', False)
    ],
    'PIPEDA': [
        ('PIPEDA Employee Files', 'HR file details.', 'contract', 2190, '6 years', 'delete', 'date_based', False),
        ('PIPEDA Transaction Records', 'Canada financial logs.', 'legal_obligation', 2555, '7 years', 'archive', 'date_based', False),
        ('PIPEDA Customer Consent Register', 'Consent signals.', 'consent', 0, 'Until withdrawn', 'delete', 'consent_withdrawal', False)
    ],
    'APPs': [
        ('APPs Employment Records', 'Australian employee files.', 'legal_obligation', 2190, '6 years', 'delete', 'date_based', False),
        ('APPs Billing & Invoicing Logs', 'Operations financial files.', 'legal_obligation', 2555, '7 years', 'archive', 'date_based', False),
        ('APPs Customer Privacy Data', 'Customer profiles.', 'consent', 0, 'Until withdrawn', 'delete', 'consent_withdrawal', False)
    ],
    'EGDPL': [
        ('EGDPL Personnel Records', 'Egypt employee files.', 'legal_obligation', 2190, '6 years', 'delete', 'date_based', False),
        ('EGDPL Customer Consent Log', 'Egyptian consent registers.', 'consent', 0, 'Until withdrawn', 'delete', 'consent_withdrawal', False),
        ('EGDPL Financial Transactions', 'Sales receipts & logs.', 'legal_obligation', 2555, '7 years', 'archive', 'date_based', False)
    ],
    'BOTH': [
        ('Cross-Framework Employee Files', 'Shared employee data.', 'legal_obligation', 2190, '6 years', 'delete', 'date_based', False),
        ('Cross-Framework Invoices', 'Billing and tax records.', 'legal_obligation', 2555, '7 years', 'archive', 'date_based', False),
        ('Cross-Framework Customer Consents', 'Opt-in proofs.', 'consent', 0, 'Until withdrawn', 'delete', 'consent_withdrawal', False)
    ]
}

def provision_org_categories(db: Session, org_id: int, country_code: str):
    frameworks = get_country_regulations(country_code)
    for fw in frameworks:
        seeds = CATEGORY_SEEDS.get(fw, [])
        for name, desc, basis, days, label, method, trigger, dual in seeds:
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
                    source='seeded'
                )
                db.add(cat)
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


