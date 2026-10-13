import hashlib
import time
from sqlalchemy.orm import Session
from app.models import DataCategory, AuditLog
from app.config import IS_PRODUCTION, TRUSTED_PROXIES

COUNTRY_REGULATION_MAP = {
    'NG': ['NDPR'],
    'GB': ['UK_GDPR', 'GDPR'],
    'EU': ['GDPR'],
    'US': ['CCPA'],
    'BR': ['LGPD'],
    'ZA': ['POPIA'],
    'KE': ['DPA_KE'],
    'GH': ['DPA_GH'],
    'SG': ['PDPA_SG'],
    'IN': ['DPDP'],
    'AE': ['PDPL'],
    'CA': ['PIPEDA'],
    'AU': ['APPs'],
    'EG': ['EGDPL'],

    # ── African continent — national data protection laws ──
    # East Africa
    'RW': ['DPA_RW'],      # Rwanda Law No. 058/2021 — NCSA
    'UG': ['DPA_UG'],      # Uganda Data Protection and Privacy Act 2019 — PDPO
    'TZ': ['DPA_TZ'],      # Tanzania Personal Data Protection Act 2022 — PDPC
    'ET': ['DPA_ET'],      # Ethiopia Proclamation 1321/2024 — Ethiopian Communications Authority
    # Southern Africa
    'ZM': ['DPA_ZM'],      # Zambia Data Protection Act No. 3 of 2021
    'ZW': ['DPA_ZW'],      # Zimbabwe Cyber & Data Protection Act 2021 — POTRAZ
    'MW': ['DPA_MW'],      # Malawi Data Protection Act 2024 — MACRA-designated
    'BW': ['DPA_BW'],      # Botswana Data Protection Act No. 18 of 2024
    'MU': ['DPA_MU'],      # Mauritius Data Protection Act 2017
    'SC': ['DPA_SC'],      # Seychelles Data Protection Act 2023 — Information Commission
    'SZ': ['DPA_SZ'],      # Eswatini Data Protection Act No. 5 of 2022
    'LS': ['DPA_LS'],      # Lesotho Data Protection Act 2011
    'CV': ['DPA_CV'],      # Cabo Verde Law No. 133/V/2001 (amended 2013) — CNPD
    'MZ': ['GDPR_ALIGN'],  # Mozambique: draft law as of 2026 — GDPR-aligned baseline
    'NA': ['GDPR_ALIGN'],  # Namibia: draft bill as of 2026 — GDPR-aligned baseline
    # West Africa
    'SN': ['DPA_SN'],      # Senegal Act No. 2008-12 — CDP
    'CI': ['DPA_CI'],      # Côte d'Ivoire Law No. 2013-450 — ARTCI
    'MA': ['DPA_MA'],      # Morocco Law No. 09-08 — CNDP
    'BJ': ['DPA_BJ'],      # Benin Law No. 2009-09 — APDP
    'TG': ['DPA_TG'],      # Togo Law No. 2019-014 — IPDCP
    'BF': ['DPA_BF'],      # Burkina Faso Law No. 010-2004/AN — CIL
    'ML': ['DPA_ML'],      # Mali Law No. 2013-015 — APDP
    'GM': ['GDPR_ALIGN'],  # Gambia: law reportedly enacted 2025; unverified — GDPR-aligned baseline
    'CM': ['DPA_CM'],      # Cameroon Law No. 2024/017 — regulator not yet operational
    'GA': ['DPA_GA'],      # Gabon Law No. 001/2011 — CNPDCP
    'AO': ['DPA_AO'],      # Angola Law No. 22/11 — APD
    # North Africa
    'TN': ['DPA_TN'],      # Tunisia Organic Law 2004-63 — INPDP
    'DZ': ['DPA_DZ'],      # Algeria Law No. 18-07 — ANPDP

    # EU / EEA member states → GDPR
    'AT': ['GDPR'], 'BE': ['GDPR'], 'BG': ['GDPR'],
    'HR': ['GDPR'], 'CY': ['GDPR'], 'CZ': ['GDPR'],
    'DK': ['GDPR'], 'EE': ['GDPR'], 'FI': ['GDPR'],
    'FR': ['GDPR'], 'DE': ['GDPR'], 'GR': ['GDPR'],
    'HU': ['GDPR'], 'IE': ['GDPR'], 'IT': ['GDPR'],
    'LV': ['GDPR'], 'LT': ['GDPR'], 'LU': ['GDPR'],
    'MT': ['GDPR'], 'NL': ['GDPR'], 'PL': ['GDPR'],
    'PT': ['GDPR'], 'RO': ['GDPR'], 'SK': ['GDPR'],
    'SI': ['GDPR'], 'ES': ['GDPR'], 'SE': ['GDPR'],
    'IS': ['GDPR'], 'LI': ['GDPR'], 'NO': ['GDPR'],
    'CH': ['GDPR'],
    'OTHER': ['GDPR'],
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

    # ── African continent ──
    'RW': {'authority': 'NCSA', 'law': 'Rwanda DPA 2021',
           'audit_label': 'Rwanda DPA Annual Compliance Report'},
    'UG': {'authority': 'PDPO', 'law': 'Uganda DP&PA 2019',
           'audit_label': 'Uganda DPPA Annual Compliance Report'},
    'TZ': {'authority': 'PDPC (Tanzania)', 'law': 'Tanzania PDPA 2022',
           'audit_label': 'Tanzania PDPA Annual Compliance Report'},
    'ET': {'authority': 'Ethiopian Communications Authority', 'law': 'Ethiopia PDPP 2024',
           'audit_label': 'Ethiopia DPP Annual Compliance Report'},
    'ZM': {'authority': 'Data Protection Commissioner (Zambia)', 'law': 'Zambia DPA 2021',
           'audit_label': 'Zambia DPA Annual Compliance Report'},
    'ZW': {'authority': 'POTRAZ', 'law': 'Zimbabwe CDPA 2021',
           'audit_label': 'Zimbabwe CDPA Annual Compliance Report'},
    'MW': {'authority': 'MACRA', 'law': 'Malawi DPA 2024',
           'audit_label': 'Malawi DPA Annual Compliance Report'},
    'BW': {'authority': 'Information & Data Protection Commission',
           'law': 'Botswana DPA 2024',
           'audit_label': 'Botswana DPA Annual Compliance Report'},
    'MU': {'authority': 'Data Protection Office (Mauritius)', 'law': 'Mauritius DPA 2017',
           'audit_label': 'Mauritius DPA Annual Compliance Report'},
    'SC': {'authority': 'Information Commission (Seychelles)',
           'law': 'Seychelles DPA 2023',
           'audit_label': 'Seychelles DPA Annual Compliance Report'},
    'SZ': {'authority': 'Eswatini DPA', 'law': 'Eswatini DPA 2022',
           'audit_label': 'Eswatini DPA Annual Compliance Report'},
    'LS': {'authority': 'Data Protection Commissioner (Lesotho)',
           'law': 'Lesotho DPA 2011',
           'audit_label': 'Lesotho DPA Annual Compliance Report'},
    'CV': {'authority': 'CNPD (Cabo Verde)', 'law': 'Cabo Verde DPA 2001',
           'audit_label': 'Cabo Verde DPA Annual Compliance Report'},
    'SN': {'authority': 'CDP (Senegal)', 'law': 'Senegal DPA 2008',
           'audit_label': 'Senegal DPA Annual Compliance Report'},
    'CI': {'authority': 'ARTCI', 'law': "Côte d'Ivoire DPA 2013",
           'audit_label': "Côte d'Ivoire DPA Annual Compliance Report"},
    'MA': {'authority': 'CNDP (Morocco)', 'law': 'Morocco Law 09-08',
           'audit_label': 'Morocco DPA Annual Compliance Report'},
    'BJ': {'authority': 'APDP (Benin)', 'law': 'Benin DPA 2009',
           'audit_label': 'Benin DPA Annual Compliance Report'},
    'TG': {'authority': 'IPDCP (Togo)', 'law': 'Togo DPA 2019',
           'audit_label': 'Togo DPA Annual Compliance Report'},
    'BF': {'authority': 'CIL (Burkina Faso)', 'law': 'Burkina Faso DPA 2004',
           'audit_label': 'Burkina Faso DPA Annual Compliance Report'},
    'ML': {'authority': 'APDP (Mali)', 'law': 'Mali DPA 2013',
           'audit_label': 'Mali DPA Annual Compliance Report'},
    'CM': {'authority': 'DPA (Cameroon)*', 'law': 'Cameroon DPA 2024',
           'audit_label': 'Cameroon DPA Annual Compliance Report'},
    'GA': {'authority': 'CNPDCP (Gabon)', 'law': 'Gabon DPA 2011',
           'audit_label': 'Gabon DPA Annual Compliance Report'},
    'AO': {'authority': 'APD (Angola)', 'law': 'Angola DPA 2011',
           'audit_label': 'Angola DPA Annual Compliance Report'},
    'TN': {'authority': 'INPDP', 'law': 'Tunisia DPA 2004',
           'audit_label': 'Tunisia DPA Annual Compliance Report'},
    'DZ': {'authority': 'ANPDP', 'law': 'Algeria Law 18-07',
           'audit_label': 'Algeria DPA Annual Compliance Report'},
    # Draft-law countries: GDPR-aligned baseline pending national law
    'MZ': {'authority': 'National Data Authority (draft law)',
           'law': 'GDPR-aligned baseline',
           'audit_label': 'GDPR-aligned Compliance Report'},
    'NA': {'authority': 'National Data Authority (draft law)',
           'law': 'GDPR-aligned baseline',
           'audit_label': 'GDPR-aligned Compliance Report'},
    'GM': {'authority': 'National Data Authority (draft law)',
           'law': 'GDPR-aligned baseline',
           'audit_label': 'GDPR-aligned Compliance Report'},
    'OTHER': {'authority': 'National Data Authority', 'law': 'General Data Protection (GDPR-aligned)', 'audit_label': 'Annual Compliance Report'},
}

SafeData_SUPPORTED_COUNTRIES = {
    # ── Countries with explicit regulation mappings ──
    'NG': 'Nigeria', 'GB': 'United Kingdom', 'US': 'United States', 'EU': 'European Union',
    'CA': 'Canada', 'AU': 'Australia', 'IN': 'India', 'AE': 'United Arab Emirates',
    'ZA': 'South Africa', 'KE': 'Kenya', 'GH': 'Ghana', 'SG': 'Singapore', 'BR': 'Brazil',
    'EG': 'Egypt',
    # ── African continent (mapped to national laws or GDPR-aligned baseline) ──
    'RW': 'Rwanda', 'UG': 'Uganda', 'TZ': 'Tanzania', 'ET': 'Ethiopia',
    'ZM': 'Zambia', 'ZW': 'Zimbabwe', 'MW': 'Malawi', 'BW': 'Botswana',
    'MU': 'Mauritius', 'SC': 'Seychelles', 'SZ': 'Eswatini', 'LS': 'Lesotho',
    'CV': 'Cabo Verde', 'MZ': 'Mozambique', 'NA': 'Namibia',
    'SN': 'Senegal', 'CI': "Côte d'Ivoire", 'MA': 'Morocco', 'BJ': 'Benin',
    'TG': 'Togo', 'BF': 'Burkina Faso', 'ML': 'Mali', 'GM': 'Gambia',
    'CM': 'Cameroon', 'GA': 'Gabon', 'AO': 'Angola', 'TN': 'Tunisia',
    'DZ': 'Algeria',
    # ── EU / EEA member states (mapped → GDPR) ──
    'AT': 'Austria', 'BE': 'Belgium', 'BG': 'Bulgaria', 'HR': 'Croatia', 'CY': 'Cyprus',
    'CZ': 'Czech Republic', 'DK': 'Denmark', 'EE': 'Estonia', 'FI': 'Finland', 'FR': 'France',
    'DE': 'Germany', 'GR': 'Greece', 'HU': 'Hungary', 'IE': 'Ireland', 'IT': 'Italy',
    'LV': 'Latvia', 'LT': 'Lithuania', 'LU': 'Luxembourg', 'MT': 'Malta', 'NL': 'Netherlands',
    'PL': 'Poland', 'PT': 'Portugal', 'RO': 'Romania', 'SK': 'Slovakia', 'SI': 'Slovenia',
    'ES': 'Spain', 'SE': 'Sweden', 'IS': 'Iceland', 'LI': 'Liechtenstein', 'NO': 'Norway',
    'CH': 'Switzerland',
    # ── All other countries (A-Z) ──
    'AF': 'Afghanistan', 'AL': 'Albania', 'AD': 'Andorra',
    'AG': 'Antigua and Barbuda', 'AR': 'Argentina', 'AM': 'Armenia', 'AZ': 'Azerbaijan',
    'BS': 'Bahamas', 'BH': 'Bahrain', 'BD': 'Bangladesh', 'BB': 'Barbados', 'BY': 'Belarus',
    'BZ': 'Belize', 'BT': 'Bhutan', 'BO': 'Bolivia',
    'BA': 'Bosnia and Herzegovina', 'BN': 'Brunei',
    'BI': 'Burundi', 'KH': 'Cambodia',
    'CF': 'Central African Republic', 'TD': 'Chad', 'CL': 'Chile', 'CN': 'China',
    'CO': 'Colombia', 'KM': 'Comoros', 'CG': 'Congo', 'CD': 'Congo (DRC)', 'CR': 'Costa Rica',
    'CU': 'Cuba', 'DJ': 'Djibouti', 'DM': 'Dominica',
    'DO': 'Dominican Republic', 'EC': 'Ecuador', 'SV': 'El Salvador', 'GQ': 'Equatorial Guinea',
    'ER': 'Eritrea', 'FJ': 'Fiji',
    'GE': 'Georgia', 'GT': 'Guatemala', 'GN': 'Guinea', 'GW': 'Guinea-Bissau',
    'GY': 'Guyana', 'HT': 'Haiti', 'HN': 'Honduras', 'IQ': 'Iraq', 'IL': 'Israel',
    'JM': 'Jamaica', 'JP': 'Japan', 'JO': 'Jordan', 'KZ': 'Kazakhstan', 'KI': 'Kiribati',
    'KP': 'North Korea', 'KR': 'South Korea', 'KW': 'Kuwait', 'KG': 'Kyrgyzstan',
    'LA': 'Laos', 'LB': 'Lebanon', 'LR': 'Liberia', 'LY': 'Libya',
    'MG': 'Madagascar', 'MY': 'Malaysia', 'MV': 'Maldives',
    'MH': 'Marshall Islands', 'MR': 'Mauritania', 'MX': 'Mexico',
    'FM': 'Micronesia', 'MD': 'Moldova', 'MC': 'Monaco', 'MN': 'Mongolia', 'ME': 'Montenegro',
    'MM': 'Myanmar', 'NR': 'Nauru',
    'NP': 'Nepal', 'NZ': 'New Zealand', 'NI': 'Nicaragua', 'NE': 'Niger', 'MK': 'North Macedonia',
    'OM': 'Oman', 'PK': 'Pakistan', 'PW': 'Palau', 'PS': 'Palestine', 'PA': 'Panama',
    'PG': 'Papua New Guinea', 'PY': 'Paraguay', 'PE': 'Peru', 'PH': 'Philippines',
    'QA': 'Qatar', 'RU': 'Russia', 'KN': 'Saint Kitts and Nevis',
    'LC': 'Saint Lucia', 'VC': 'Saint Vincent and the Grenadines', 'WS': 'Samoa',
    'SM': 'San Marino', 'ST': 'São Tomé and Príncipe', 'SA': 'Saudi Arabia',
    'RS': 'Serbia', 'SL': 'Sierra Leone', 'SB': 'Solomon Islands',
    'SO': 'Somalia', 'SS': 'South Sudan', 'LK': 'Sri Lanka', 'SD': 'Sudan', 'SR': 'Suriname',
    'SY': 'Syria', 'TW': 'Taiwan', 'TJ': 'Tajikistan', 'TH': 'Thailand',
    'TL': 'Timor-Leste', 'TO': 'Tonga', 'TT': 'Trinidad and Tobago',
    'TR': 'Turkey', 'TM': 'Turkmenistan', 'TV': 'Tuvalu',
    'UA': 'Ukraine', 'UY': 'Uruguay', 'UZ': 'Uzbekistan', 'VU': 'Vanuatu', 'VA': 'Vatican City',
    'VE': 'Venezuela', 'VN': 'Vietnam', 'YE': 'Yemen',
}

# Pricing Catalog (Base USD)
PRICING_PLANS = {
    'monthly': {'amount_cents': 4000, 'label': '$40', 'interval': 'month'},
    'yearly': {'amount_cents': 39900, 'label': '$399', 'interval': 'year', 'savings': 'Save $81'},
}

# Supported Global Jurisdictions & Currency Rates (Relative to 1 USD)
CURRENCY_DATA = {
    'USD': {'code': 'USD', 'symbol': '$', 'rate': 1.0, 'name': 'US Dollar'},
    'NGN': {'code': 'NGN', 'symbol': '₦', 'rate': 1500.0, 'name': 'Nigerian Naira'},
    'ZAR': {'code': 'ZAR', 'symbol': 'R', 'rate': 18.5, 'name': 'South African Rand'},
    'GBP': {'code': 'GBP', 'symbol': '£', 'rate': 0.78, 'name': 'British Pound'},
    'EUR': {'code': 'EUR', 'symbol': '€', 'rate': 0.92, 'name': 'Euro'},
    'KES': {'code': 'KES', 'symbol': 'KSh ', 'rate': 130.0, 'name': 'Kenyan Shilling'},
    'GHS': {'code': 'GHS', 'symbol': 'GH₵ ', 'rate': 14.5, 'name': 'Ghanaian Cedi'},
    'CAD': {'code': 'CAD', 'symbol': 'CA$ ', 'rate': 1.36, 'name': 'Canadian Dollar'},
    'AUD': {'code': 'AUD', 'symbol': 'A$ ', 'rate': 1.52, 'name': 'Australian Dollar'},
    'INR': {'code': 'INR', 'symbol': '₹', 'rate': 83.5, 'name': 'Indian Rupee'},
    'AED': {'code': 'AED', 'symbol': 'AED ', 'rate': 3.67, 'name': 'UAE Dirham'},
    'SGD': {'code': 'SGD', 'symbol': 'S$ ', 'rate': 1.35, 'name': 'Singapore Dollar'},
    'BRL': {'code': 'BRL', 'symbol': 'R$ ', 'rate': 5.4, 'name': 'Brazilian Real'},
    'EGP': {'code': 'EGP', 'symbol': 'E£ ', 'rate': 48.0, 'name': 'Egyptian Pound'},
    # African currencies
    'RWF': {'code': 'RWF', 'symbol': 'FRw ', 'rate': 1400.0, 'name': 'Rwandan Franc'},
    'UGX': {'code': 'UGX', 'symbol': 'USh ', 'rate': 3700.0, 'name': 'Ugandan Shilling'},
    'TZS': {'code': 'TZS', 'symbol': 'TSh ', 'rate': 2600.0, 'name': 'Tanzanian Shilling'},
    'ZMW': {'code': 'ZMW', 'symbol': 'K ', 'rate': 25.0, 'name': 'Zambian Kwacha'},
    'MWK': {'code': 'MWK', 'symbol': 'MK ', 'rate': 1735.0, 'name': 'Malawian Kwacha'},
    'BWP': {'code': 'BWP', 'symbol': 'P ', 'rate': 13.5, 'name': 'Botswana Pula'},
    'MUR': {'code': 'MUR', 'symbol': '₨ ', 'rate': 46.0, 'name': 'Mauritian Rupee'},
    'SCR': {'code': 'SCR', 'symbol': 'SR ', 'rate': 14.5, 'name': 'Seychellois Rupee'},
    'XOF': {'code': 'XOF', 'symbol': 'CFA ', 'rate': 600.0, 'name': 'West African CFA Franc'},
    'XAF': {'code': 'XAF', 'symbol': 'FCFA ', 'rate': 600.0, 'name': 'Central African CFA Franc'},
    'CVE': {'code': 'CVE', 'symbol': '$ Esc ', 'rate': 100.0, 'name': 'Cape Verdean Escudo'},
    'DZD': {'code': 'DZD', 'symbol': 'DA ', 'rate': 134.0, 'name': 'Algerian Dinar'},
    'TND': {'code': 'TND', 'symbol': 'DT ', 'rate': 3.1, 'name': 'Tunisian Dinar'},
    'MAD': {'code': 'MAD', 'symbol': 'DH ', 'rate': 10.0, 'name': 'Moroccan Dirham'},
    'AOA': {'code': 'AOA', 'symbol': 'Kz ', 'rate': 915.0, 'name': 'Angolan Kwanza'},
}

# Map Country Codes to Primary Currency
COUNTRY_TO_CURRENCY = {
    'US': 'USD',
    'NG': 'NGN',
    'ZA': 'ZAR',
    'GB': 'GBP',
    'KE': 'KES',
    'GH': 'GHS',
    'CA': 'CAD',
    'AU': 'AUD',
    'IN': 'INR',
    'AE': 'AED',
    'SG': 'SGD',
    'BR': 'BRL',
    'EG': 'EGP',
    # African currencies
    'RW': 'RWF', 'UG': 'UGX', 'TZ': 'TZS', 'ZM': 'ZMW', 'MW': 'MWK',
    'BW': 'BWP', 'MU': 'MUR', 'SC': 'SCR',
    'DZ': 'DZD', 'TN': 'TND', 'MA': 'MAD', 'AO': 'AOA',
    # West African CFA franc zone
    'SN': 'XOF', 'CI': 'XOF', 'BJ': 'XOF', 'TG': 'XOF', 'BF': 'XOF',
    'ML': 'XOF', 'GA': 'XOF',    'CM': 'XAF', 'CV': 'CVE',
    # European Union Eurozone
    'EU': 'EUR', 'DE': 'EUR', 'FR': 'EUR', 'IT': 'EUR', 'ES': 'EUR',
    'NL': 'EUR', 'BE': 'EUR', 'IE': 'EUR', 'PT': 'EUR', 'AT': 'EUR',
    'FI': 'EUR', 'GR': 'EUR', 'SE': 'EUR', 'PL': 'EUR',
}

def get_country_regulations(country_code: str) -> list:
    return COUNTRY_REGULATION_MAP.get(country_code.upper(), COUNTRY_REGULATION_MAP['OTHER'])

def get_country_regulation_labels(country_code: str) -> dict:
    return COUNTRY_REGULATION_LABELS.get(country_code.upper(), COUNTRY_REGULATION_LABELS['OTHER'])

def detect_visitor_currency(country_code: str) -> dict:
    """Returns currency metadata dict for a country code."""
    code = (country_code or 'US').upper().strip()
    curr_code = COUNTRY_TO_CURRENCY.get(code, 'USD')
    return CURRENCY_DATA.get(curr_code, CURRENCY_DATA['USD'])

def get_visitor_country(request) -> str:
    """Extract country code from request headers (Cloudflare, proxies, GeoIP) or query/session."""
    try:
        # 1. Query parameter override (e.g. ?country=ZA or ?currency=NGN)
        param_country = request.query_params.get("country") if hasattr(request, "query_params") else None
        if param_country and len(param_country) == 2:
            return param_country.upper()

        param_curr = request.query_params.get("currency") if hasattr(request, "query_params") else None
        if param_curr:
            for c_code, curr in COUNTRY_TO_CURRENCY.items():
                if curr == param_curr.upper():
                    return c_code

        # Proxy trust verification: In production, verify headers come from trusted proxy
        import app.helpers as _h
        _is_prod = getattr(_h, "IS_PRODUCTION", IS_PRODUCTION)
        _trusted = getattr(_h, "TRUSTED_PROXIES", TRUSTED_PROXIES)
        if _is_prod and _trusted:
            trusted_set = {p.strip() for p in _trusted.split(",") if p.strip()}
            client_ip = request.client.host if hasattr(request, "client") and request.client else ""
            if client_ip and client_ip not in trusted_set:
                # Direct untrusted connection: do not trust edge headers
                return "US"

        # 2. Cloudflare Country Header
        cf_country = request.headers.get("CF-IPCountry") if hasattr(request, "headers") else None
        if cf_country and len(cf_country) == 2 and cf_country.upper() != "XX":
            return cf_country.upper()

        # 3. Standard Geo-IP proxy headers
        if hasattr(request, "headers"):
            for h in ["X-Country-Code", "X-Geo-Country", "X-Appengine-Country"]:
                val = request.headers.get(h)
                if val and len(val) == 2:
                    return val.upper()
    except Exception:
        pass
    return "US"

def get_localized_pricing(country_code: str) -> dict:
    """
    Returns dual pricing dictionary (base USD + localized visitor currency).
    Core Plan: $40/mo, $399/yr.
    """
    curr = detect_visitor_currency(country_code)
    rate = curr.get("rate", 1.0)
    symbol = curr.get("symbol", "$")
    code = curr.get("code", "USD")
    country_upper = (country_code or 'US').upper()

    monthly_usd = 40
    yearly_usd = 399

    monthly_local = int(round(monthly_usd * rate))
    yearly_local = int(round(yearly_usd * rate))
    savings_usd = 81
    savings_local = int(round(savings_usd * rate))

    return {
        "country_code": country_upper,
        "country_name": SafeData_SUPPORTED_COUNTRIES.get(country_upper, country_upper),
        "currency_code": code,
        "currency_symbol": symbol,
        "currency_name": curr.get("name", "US Dollar"),
        "exchange_rate": rate,
        "is_usd": code == "USD",
        "monthly": {
            "amount_usd": monthly_usd,
            "amount_local": monthly_local,
            "display_usd": f"${monthly_usd}",
            "display_local": f"{symbol}{monthly_local:,}",
            "full_display": f"${monthly_usd}/mo" if code == "USD" else f"${monthly_usd}/mo ({symbol}{monthly_local:,}/mo)"
        },
        "yearly": {
            "amount_usd": yearly_usd,
            "amount_local": yearly_local,
            "display_usd": f"${yearly_usd}",
            "display_local": f"{symbol}{yearly_local:,}",
            "full_display": f"${yearly_usd}/yr" if code == "USD" else f"${yearly_usd}/yr ({symbol}{yearly_local:,}/yr)",
            "savings_usd": f"Save ${savings_usd}",
            "savings_local": f"Save {symbol}{savings_local:,}"
        }
    }

def get_framework_badge(framework: str) -> str:
    f = framework.strip().upper()
    if f in ('GDPR', 'UK_GDPR', 'EU_GDPR'):
        return 'bg-info text-dark fw-bold'
    elif f in ('NDPR', 'NDPA'):
        return 'bg-success text-white fw-bold'
    elif f == 'CCPA':
        return 'bg-warning text-dark fw-bold'
    elif f == 'LGPD':
        return 'bg-danger text-white fw-bold'
    elif f == 'POPIA':
        return 'bg-primary text-white fw-bold'
    elif f in ('DPDP', 'DPDP_ACT'):
        return 'bg-dark text-white fw-bold'
    elif f == 'PDPL':
        return 'bg-secondary text-white fw-bold'
    elif f == 'PIPEDA':
        return 'bg-info text-dark fw-bold'
    elif f == 'APPS':
        return 'bg-primary text-white fw-bold'
    elif f == 'EGDPL':
        return 'bg-success text-white fw-bold'
    # ── African frameworks: shared teal family ──
    elif f.startswith('DPA_'):
        return 'bg-success text-white fw-bold'   # African national DPAs share the success green
    elif f == 'GDPR_ALIGN':
        return 'bg-info text-dark fw-bold'       # GDPR-aligned baseline (draft-law countries)
    elif f in ('BOTH', 'GLOBAL', 'MULTI', 'UNIVERSAL'):
        return 'bg-secondary text-white fw-bold'
    else:
        return 'bg-secondary text-white fw-bold'

# Cryptographic chain logger
def log_audit(db: Session, org_id: int, action: str, entity_type: str, entity_id: int = None, performed_by: int = None, details: dict = None, ip_address: str = None):
    import json as _json
    from datetime import datetime as _dt, timezone as _tz

    # Fetch previous log hash
    prev_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = prev_log.row_hash if prev_log else "0" * 64

    # Normalise details to canonical, key-sorted JSON 
    if details is None:
        details_str = ""
    elif isinstance(details, str):
        details_str = details
    else:
        details_str = _json.dumps(details, sort_keys=True, ensure_ascii=False)

    # Canonical hash payload  format
    created_at_str = _dt.now(_tz.utc).strftime("%Y-%m-%d %H:%M:%S")
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
#   Dynamic category templates — FULL replica of legacy seed_categories_only.sql
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

    # ──────────────────────────────────────────────────────────────────────
    #  AFRICA — national data protection laws (east/southern/west/north)
    #  Each set: customer data, employee records (national labour/social
    #  security), regulator consent records, and financial/KYC where a
    #  national AML or tax authority standard exists.
    # ──────────────────────────────────────────────────────────────────────

    # DPA_RW (Rwanda): Law No. 058/2021 rel. to Protection of Personal Data & Privacy — NCSA
    'DPA_RW': [
        ('Customer Personal Data (Rwanda DPA)',
         'Names, national ID (NID), phone numbers, email addresses of Rwandan data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Rwanda / RSSB)',
         'Employment contracts, RSSB social security records, and payroll data under Rwandan labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Rwanda DPA)',
         'Consent collection and withdrawal logs under Rwanda Law No. 058/2021.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_UG (Uganda): Data Protection and Privacy Act 2019 — PDPO (NITA-U)
    'DPA_UG': [
        ('Customer Personal Data (Uganda DPPA)',
         'Names, national ID (NIN), phone numbers, email addresses of Ugandan data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Uganda / NSSF)',
         'Employment contracts, NSSF contributions, PAYE records, and payroll data under Ugandan employment law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Uganda DPPA)',
         'Consent logs and withdrawal records under Section 3 of the Uganda Data Protection and Privacy Act.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_TZ (Tanzania): Personal Data Protection Act 2022 (Act No. 11) — PDPC
    'DPA_TZ': [
        ('Customer Personal Data (Tanzania PDPA)',
         'Names, national ID (NIDA), phone numbers, email addresses of Tanzanian data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Tanzania / NSSF)',
         'Employment contracts, NSSF contributions, PAYE records, and payroll under Tanzanian employment law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Tanzania PDPA)',
         'Consent collection and withdrawal logs under the Tanzania Personal Data Protection Act 2022.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_ET (Ethiopia): Personal Data Protection Proclamation No. 1321/2024 — ECA
    'DPA_ET': [
        ('Customer Personal Data (Ethiopia PDPP)',
         'Names, national ID (Fayda), phone numbers, email addresses of Ethiopian data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Ethiopia / ESS)',
         'Employment contracts, ESS social insurance records, and payroll data under Ethiopian labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Ethiopia PDPP)',
         'Consent collection and withdrawal logs under Proclamation No. 1321/2024.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_ZM (Zambia): Data Protection Act No. 3 of 2021 — Data Protection Commissioner
    'DPA_ZM': [
        ('Customer Personal Data (Zambia DPA)',
         'Names, NRC numbers, phone numbers, email addresses of Zambian data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Zambia / NAPSA)',
         'Employment contracts, NAPSA contributions, PAYE records, and payroll under Zambian employment law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Financial Records (ZRA)',
         'Tax filings, VAT returns, and Zambia Revenue Authority correspondence.',
         'legal_obligation', 2555, '6 years (ZRA requirement)', 'archive', 'date_based', False, 'annually'),
        ('Consent Records (Zambia DPA)',
         'Consent logs and withdrawal records under the Zambia Data Protection Act No. 3 of 2021.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_ZW (Zimbabwe): Cyber and Data Protection Act [Chapter 12:07] — POTRAZ
    'DPA_ZW': [
        ('Customer Personal Data (Zimbabwe CDPA)',
         'Names, national ID numbers, phone numbers, email addresses of Zimbabwean data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Zimbabwe / NSSA)',
         'Employment contracts, NSSA contributions, PAYE records, and payroll under Zimbabwean labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Financial Records (ZIMRA)',
         'Tax returns, VAT records, and ZIMRA correspondence.',
         'legal_obligation', 2190, '6 years (ZIMRA requirement)', 'archive', 'date_based', False, 'annually'),
        ('Consent Records (Zimbabwe CDPA)',
         'Consent collection and withdrawal logs under the Cyber and Data Protection Act Section 12.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_MW (Malawi): Data Protection Act 2024 — MACRA-designated authority
    'DPA_MW': [
        ('Customer Personal Data (Malawi DPA)',
         'Names, national ID numbers, phone numbers, email addresses of Malawian data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Malawi / MWCISU)',
         'Employment contracts, pension records, PAYE records, and payroll under Malawian employment law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Malawi DPA)',
         'Consent collection and withdrawal logs under the Malawi Data Protection Act 2024.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_BW (Botswana): Data Protection Act No. 18 of 2024 — Information & Data Protection Commission
    'DPA_BW': [
        ('Customer Personal Data (Botswana DPA)',
         'Names, Omang (national ID) numbers, phone numbers, email addresses of Botswana data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Botswana / BPSA)',
         'Employment contracts, GIPF/BPSA pension records, and payroll under Botswana employment law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Botswana DPA)',
         'Consent collection and withdrawal logs under the Botswana Data Protection Act 2024.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_MU (Mauritius): Data Protection Act 2017 — Data Protection Office
    'DPA_MU': [
        ('Customer Personal Data (Mauritius DPA)',
         'Names, national ID (CNID) numbers, phone numbers, email addresses of Mauritian data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Mauritius)',
         'Employment contracts, NPF/NSF contributions, and payroll under Mauritian labour law.',
         'legal_obligation', 2555, '7 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Financial Records (MRA)',
         'Tax returns, VAT records, and Mauritius Revenue Authority correspondence.',
         'legal_obligation', 2555, '7 years (MRA requirement)', 'archive', 'date_based', False, 'annually'),
        ('Consent Records (Mauritius DPA)',
         'Consent collection and withdrawal logs under the Mauritius Data Protection Act 2017.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_SC (Seychelles): Data Protection Act 2023 (Act 24) — Information Commission
    'DPA_SC': [
        ('Customer Personal Data (Seychelles DPA)',
         'Names, NIN references, phone numbers, email addresses of Seychellois data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Seychelles / SNPF)',
         'Employment contracts, SNPF contributions, and payroll under Seychellois employment law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Seychelles DPA)',
         'Consent collection and withdrawal logs under the Seychelles Data Protection Act 2023.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_SZ (Eswatini): Data Protection Act No. 5 of 2022 — Eswatini DPA
    'DPA_SZ': [
        ('Customer Personal Data (Eswatini DPA)',
         'Names, national ID numbers, phone numbers, email addresses of Eswatini data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Eswatini / FSP)',
         'Employment contracts, FSP pension contributions, and payroll under Swazi employment law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Eswatini DPA)',
         'Consent collection and withdrawal logs under the Eswatini Data Protection Act 2022.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_LS (Lesotho): Data Protection Act 2011 — Data Protection Commissioner
    'DPA_LS': [
        ('Customer Personal Data (Lesotho DPA)',
         'Names, national ID numbers, phone numbers, email addresses of Basotho data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Lesotho / LNPS)',
         'Employment contracts, LNPS pension contributions, and payroll under Lesotho employment law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Lesotho DPA)',
         'Consent collection and withdrawal logs under the Lesotho Data Protection Act 2011.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_CV (Cabo Verde): Law 133/V/2001 on Protection of Personal Data (amended 2013) — CNPD
    'DPA_CV': [
        ('Customer Personal Data (Cabo Verde DPA)',
         'Names, NIF numbers, phone numbers, email addresses of Cabo Verdean data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Cabo Verde / INPS)',
         'Employment contracts, INPS contributions, and payroll under Cabo Verdean labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Cabo Verde DPA)',
         'Consent collection and withdrawal logs under Law No. 133/V/2001.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_SN (Senegal): Act No. 2008-12 on Personal Data Protection — CDP
    'DPA_SN': [
        ('Customer Personal Data (Senegal DPA)',
         'Names, CNP numbers, phone numbers, email addresses of Senegalese data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Senegal / IPRES)',
         'Employment contracts, IPRES/CSS contributions, and payroll under Senegalese labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Senegal DPA)',
         'Consent collection and withdrawal logs under Senegal Act No. 2008-12.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_CI (Côte d'Ivoire): Law No. 2013-450 on Protection of Personal Data — ARTCI
    'DPA_CI': [
        ('Customer Personal Data (Côte d\'Ivoire DPA)',
         'Names, CNI numbers, phone numbers, email addresses of Ivorian data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Côte d\'Ivoire / CNPS)',
         'Employment contracts, CNPS contributions, and payroll under Ivorian labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Côte d\'Ivoire DPA)',
         'Consent collection and withdrawal logs under Law No. 2013-450.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_MA (Morocco): Law No. 09-08 — CNDP
    'DPA_MA': [
        ('Customer Personal Data (Morocco Law 09-08)',
         'Names, CNIE references, phone numbers, email addresses of Moroccan data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Morocco / CNSS)',
         'Employment contracts, CNSS contributions, and payroll under Moroccan labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Morocco CNDP)',
         'Consent collection and withdrawal logs under Article 5 of Law No. 09-08.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_BJ (Benin): Law No. 2009-09 — APDP
    'DPA_BJ': [
        ('Customer Personal Data (Benin DPA)',
         'Names, CIP numbers, phone numbers, email addresses of Beninese data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Benin / CNSS)',
         'Employment contracts, CNSS contributions, and payroll under Beninese labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Benin DPA)',
         'Consent collection and withdrawal logs under Law No. 2009-09.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_TG (Togo): Law No. 2019-014 — IPDCP
    'DPA_TG': [
        ('Customer Personal Data (Togo DPA)',
         'Names, national ID numbers, phone numbers, email addresses of Togolese data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Togo / CNSS)',
         'Employment contracts, CNSS contributions, and payroll under Togolese labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Togo DPA)',
         'Consent collection and withdrawal logs under Law No. 2019-014.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_BF (Burkina Faso): Law No. 010-2004/AN (amended 2021) — CIL
    'DPA_BF': [
        ('Customer Personal Data (Burkina Faso DPA)',
         'Names, national ID numbers, phone numbers, email addresses of Burkina Faso data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Burkina Faso / CNSS)',
         'Employment contracts, CNSS contributions, and payroll under Burkinabè labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Burkina Faso DPA)',
         'Consent collection and withdrawal logs under Law No. 010-2004/AN.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_ML (Mali): Law No. 2013-015 — APDP
    'DPA_ML': [
        ('Customer Personal Data (Mali DPA)',
         'Names, national ID (NINA) numbers, phone numbers, email addresses of Malian data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Mali / INPS)',
         'Employment contracts, INPS contributions, and payroll under Malian labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Mali DPA)',
         'Consent collection and withdrawal logs under Law No. 2013-015.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_CM (Cameroon): Law No. 2024/017 — DPA (regulator being established)
    'DPA_CM': [
        ('Customer Personal Data (Cameroon DPA)',
         'Names, national ID (CNI) numbers, phone numbers, email addresses of Cameroonian data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Cameroon / CNPS)',
         'Employment contracts, CNPS contributions, and payroll under Cameroonian labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Cameroon DPA)',
         'Consent collection and withdrawal logs under Law No. 2024/017.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_GA (Gabon): Law No. 001/2011 — CNPDCP
    'DPA_GA': [
        ('Customer Personal Data (Gabon DPA)',
         'Names, national ID numbers, phone numbers, email addresses of Gabonese data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Gabon / CNSS)',
         'Employment contracts, CNSS contributions, and payroll under Gabonese labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Gabon DPA)',
         'Consent collection and withdrawal logs under Law No. 001/2011.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_AO (Angola): Law No. 22/11 — APD
    'DPA_AO': [
        ('Customer Personal Data (Angola DPA)',
         'Names, BI (identity card) numbers, phone numbers, email addresses of Angolan data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Angola / INSS)',
         'Employment contracts, INSS contributions, and payroll under Angolan labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Angola DPA)',
         'Consent collection and withdrawal logs under Law No. 22/11.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_TN (Tunisia): Organic Law 2004-63 — INPDP
    'DPA_TN': [
        ('Customer Personal Data (Tunisia DPA)',
         'Names, national ID numbers, phone numbers, email addresses of Tunisian data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Tunisia / CNSS)',
         'Employment contracts, CNSS contributions, and payroll under Tunisian labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Tunisia DPA)',
         'Consent collection and withdrawal logs under Organic Law 2004-63.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # DPA_DZ (Algeria): Law No. 18-07 — ANPDP
    'DPA_DZ': [
        ('Customer Personal Data (Algeria Law 18-07)',
         'Names, national ID (NIN) numbers, phone numbers, email addresses of Algerian data subjects.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (Algeria / CNAS)',
         'Employment contracts, CNAS/CNR contributions, and payroll under Algerian labour law.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (Algeria DPA)',
         'Consent collection and withdrawal logs under Law No. 18-07.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],

    # ──────────────────────────────────────────────────────────────────────
    #  GDPR_ALIGN — baseline for African countries whose national law is
    #  still in draft (Namibia, Mozambique, Gambia). Uses GDPR-aligned
    #  obligations until a national law enters into force.
    # ──────────────────────────────────────────────────────────────────────
    'GDPR_ALIGN': [
        ('Customer Personal Data (GDPR-aligned baseline)',
         'Names, national ID references, phone numbers, and email addresses '
         'processed under a GDPR-aligned national baseline while the country\'s '
         'own data protection law is finalised.',
         'contract', 1095, '3 years post-relationship', 'anonymise', 'date_based', False, 'quarterly'),
        ('Employee Records (GDPR-aligned baseline)',
         'Employment contracts, social security records, and payroll data '
         'retained under general labour-law recordkeeping obligations.',
         'legal_obligation', 1825, '5 years post-employment', 'delete', 'date_based', False, 'annually'),
        ('Consent Records (GDPR-aligned baseline)',
         'Consent collection and withdrawal logs maintained under GDPR-aligned '
         'consent principles pending national law.',
         'consent', 0, 'Until consent withdrawn + 1 year evidence', 'delete', 'consent_withdrawal', False, 'quarterly'),
    ],
}


def provision_org_categories(db: Session, org_id: int, country_code: str):
    """
    Seed data categories for a new organisation based on country → regulation mapping.
    Also creates a default retention rule for each seeded category .
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

                # Create default retention rule for this category 
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
    """
    Send a transactional email from the SafeData platform.

    Credentials come from environment variables (SMTP_HOST, SMTP_PORT, SMTP_USER,
    SMTP_PASS, SMTP_FROM_EMAIL, SMTP_FROM_NAME, SMTP_SECURE) set by 3Consulting on
    the hosting platform (e.g. Render).  They are NOT stored in or read from the
    application database — clients never configure or see these settings.

    In local/dev mode (SMTP_HOST not set), emails are printed to the console log.
    """
    import smtplib
    import os
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from app.config import (
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
        SMTP_FROM_EMAIL, SMTP_FROM_NAME, SMTP_SECURE, SMTP_REPLY_TO, LOG_PATH
    )

    # ── Dev / local fallback: log to console when SMTP is not configured ──
    if not SMTP_HOST:
        print("--- EMAIL CONSOLE LOG (SMTP_HOST not set — local dev mode) ---")
        print(f"To:       {to_email}")
        print(f"Subject:  {subject}")
        print(f"Reply-To: {SMTP_REPLY_TO or '(none)'}")
        print(f"Body:     {html_body[:300]}...")
        print("--------------------------------------------------------------")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg["To"]      = to_email
        # Reply-To lets clients reply to support@ without exposing noreply@
        if SMTP_REPLY_TO:
            msg["Reply-To"] = SMTP_REPLY_TO
        msg.attach(MIMEText(html_body, "html"))

        if SMTP_SECURE == "ssl":
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            if SMTP_SECURE == "tls":
                server.starttls()

        if SMTP_USER and SMTP_PASS:
            server.login(SMTP_USER, SMTP_PASS)

        server.sendmail(SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        return True

    except Exception as e:
        print(f"[send_system_email] delivery failed → {e}")
        log_file = os.path.join(LOG_PATH, "mail_errors.log")
        try:
            from datetime import datetime
            with open(log_file, "a") as f:
                f.write(f"[{datetime.now().isoformat()}] to={to_email} err={e}\n")
        except Exception:
            pass
        return False



# ═══════════════════════════════════════════════════════════════════════════
#   Email Templates 
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
        '<div style="background:#ff914d;color:#fff;padding:18px 24px;font-size:20px;font-weight:bold;">SafeData</div>'
        '<div style="padding:24px;color:#222;">'
        f'<h2 style="color:#1A6187;margin-top:0;">{_escape_html(title)}</h2>'
        f'{body_html}'
        '</div>'
        f'<div style="padding:16px 24px;background:#1A1A2E;color:#cfd2dc;font-size:12px;">&copy; {year}'
        ' 3Consulting Limited &middot; SafeData</div>'
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
        '<p>A password reset was requested for your SafeData account. This link is valid for 1 hour:</p>'
        f'<p><a href="{_escape_html(reset_link)}" style="background:#ff914d;color:#fff;padding:10px 18px;'
        'text-decoration:none;border-radius:4px;display:inline-block;">Reset your password</a></p>'
        '<p>If you did not request this, you can safely ignore this email.</p>'
    )
    return ('Reset your SafeData password', email_layout('Password reset', body))


def email_verification(name: str, verify_link: str) -> tuple:
    """Email verification for new registrations. Returns (subject, html)."""
    body = (
        f'<p>Hello {_escape_html(name)},</p>'
        '<p>Welcome to SafeData. Please verify your email address to activate your account:</p>'
        f'<p><a href="{_escape_html(verify_link)}" style="background:#ff914d;color:#fff;padding:10px 18px;'
        'text-decoration:none;border-radius:4px;display:inline-block;">Verify my email</a></p>'
        '<p>If you did not create an account, ignore this message.</p>'
    )
    return ('Verify your SafeData account', email_layout('Email verification', body))


def email_team_invite(name: str, org_name: str, role: str, invite_link: str) -> tuple:
    """Team invitation email. Returns (subject, html)."""
    role_labels = {'admin': 'Administrator', 'dpo': 'Data Protection Officer', 'data_owner': 'Data Owner'}
    role_label = role_labels.get(role, role)
    body = (
        f'<p>Hello {_escape_html(name)},</p>'
        f'<p>You have been invited to join <strong>{_escape_html(org_name)}</strong> on SafeData'
        f' as <strong>{_escape_html(role_label)}</strong>.</p>'
        '<p>SafeData is your organisation\'s automated data retention and compliance portal.</p>'
        f'<p><a href="{_escape_html(invite_link)}" style="background:#ff914d;color:#fff;padding:10px 18px;'
        'text-decoration:none;border-radius:4px;display:inline-block;">Accept invitation</a></p>'
        '<p>This link expires in 7 days. If you were not expecting this, you can ignore this email.</p>'
    )
    return (f"You're invited to SafeData — {org_name}", email_layout('Team invitation', body))


# ═══════════════════════════════════════════════════════════════════════════
#   Zero-Knowledge Architecture: PII Detection & Guard
# ═══════════════════════════════════════════════════════════════════════════

def detect_pii_in_text(text: str) -> list:
    """
    Detects obvious personal identification patterns in text (emails, credit cards, national IDs/SSNs).
    Used to enforce SafeData's Zero-Knowledge guarantee on free-text metadata fields.
    """
    import re
    if not text or not str(text).strip():
        return []

    findings = []
    # 1. Email address pattern
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', text):
        findings.append("email_address")

    # 2. Credit Card number pattern (13 to 19 digits)
    card_match = re.search(r'\b(?:\d[ -]*?){13,19}\b', text)
    if card_match:
        digits_only = re.sub(r'\D', '', card_match.group(0))
        if len(digits_only) in (13, 14, 15, 16, 17, 18, 19) and digits_only.startswith(('4', '5', '3', '6')):
            findings.append("payment_card")

    # 3. National ID / US SSN (XXX-XX-XXXX)
    if re.search(r'\b\d{3}-\d{2}-\d{4}\b', text):
        findings.append("national_id_ssn")

    return findings

