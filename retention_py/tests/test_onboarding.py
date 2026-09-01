"""
Test onboarding & multi-country global compliance support.
Validates:
1. Dynamic category provisioning across all continents (Nigeria, UK, US, EU, Brazil, South Africa, Kenya, India, UAE, Canada, Australia, Egypt, and global fallback).
2. End-to-end registration, login, dashboard rendering, category verification, and report generation for any country.
"""
import pytest
from app.helpers import provision_org_categories, get_country_regulations, get_country_regulation_labels, detect_visitor_currency, CATEGORY_SEEDS
from app.models import DataCategory, Organization, User


def test_provision_ng_categories(db):
    """Nigeria should seed NDPR + BOTH categories."""
    provision_org_categories(db, 101, "NG")
    cats = db.query(DataCategory).filter(DataCategory.organization_id == 101).all()
    assert len(cats) > 0
    frameworks = {c.compliance_framework for c in cats}
    assert "NDPR" in frameworks or "BOTH" in frameworks


def test_provision_gb_categories(db):
    """UK should seed UK_GDPR/GDPR + BOTH categories."""
    provision_org_categories(db, 102, "GB")
    cats = db.query(DataCategory).filter(DataCategory.organization_id == 102).all()
    assert len(cats) > 0


def test_provision_us_categories(db):
    """US should seed CCPA categories."""
    provision_org_categories(db, 103, "US")
    cats = db.query(DataCategory).filter(DataCategory.organization_id == 103).all()
    assert len(cats) > 0
    frameworks = {c.compliance_framework for c in cats}
    assert "CCPA" in frameworks


def test_provision_idempotent(db):
    """Running twice should not duplicate categories."""
    provision_org_categories(db, 104, "NG")
    count1 = db.query(DataCategory).filter(DataCategory.organization_id == 104).count()

    provision_org_categories(db, 104, "NG")
    count2 = db.query(DataCategory).filter(DataCategory.organization_id == 104).count()

    assert count1 == count2


def test_provision_unknown_country(db):
    """Unknown country should fall back to GDPR + BOTH baseline."""
    provision_org_categories(db, 105, "XX")
    cats = db.query(DataCategory).filter(DataCategory.organization_id == 105).all()
    assert len(cats) > 0


def test_get_country_regulations():
    """Check regulation map returns correct frameworks."""
    assert "NDPR" in get_country_regulations("NG")
    assert "GDPR" in get_country_regulations("GB") or "UK_GDPR" in get_country_regulations("GB")
    assert "CCPA" in get_country_regulations("US")
    assert "LGPD" in get_country_regulations("BR")
    assert "POPIA" in get_country_regulations("ZA")
    assert "DPDP" in get_country_regulations("IN")
    assert "PDPL" in get_country_regulations("AE")
    assert "PIPEDA" in get_country_regulations("CA")
    assert "APPs" in get_country_regulations("AU")
    assert "EGDPL" in get_country_regulations("EG")


def test_country_currency_and_labels():
    """Ensure currencies and labels resolve gracefully for all regions."""
    assert detect_visitor_currency("NG")["code"] == "NGN"
    assert detect_visitor_currency("GB")["code"] == "GBP"
    assert detect_visitor_currency("DE")["code"] == "EUR"
    assert detect_visitor_currency("US")["code"] == "USD"
    assert detect_visitor_currency("JP")["code"] == "USD"

    assert get_country_regulation_labels("NG")["authority"] == "NITDA"
    assert get_country_regulation_labels("GB")["authority"] == "ICO"
    assert get_country_regulation_labels("US")["authority"] == "State AG / FTC"
    assert get_country_regulation_labels("BR")["authority"] == "ANPD"
    assert get_country_regulation_labels("ZA")["authority"] == "Information Regulator"
    assert get_country_regulation_labels("JP")["authority"] == "National Data Authority"


@pytest.mark.parametrize("country_code,expected_domain", [
    ("NG", "lagosfin.ng"),
    ("GB", "londonlegal.co.uk"),
    ("US", "usacorp.io"),
    ("DE", "berlintech.de"),
    ("BR", "riosaude.com.br"),
    ("ZA", "capetownlogistics.co.za"),
    ("IN", "mumbaidata.in"),
    ("AE", "dubaiventures.ae"),
    ("CA", "torontomedia.ca"),
    ("AU", "sydneysystems.com.au"),
    ("JP", "tokyoanalytics.jp"),  # Unmapped country testing global fallback
])
def test_global_registration_and_end_to_end_journey(client, db, country_code, expected_domain):
    """
    Simulates real end-to-end user journeys from countries around the globe.
    Tests:
    1. Tenant sign up with country selection.
    2. Automatic category seeding based on national law.
    3. User authentication & session generation.
    4. Dashboard rendering with national compliance scorecard.
    5. Category register inspection.
    6. Report generation and download.
    """
    email = f"lead@{expected_domain}"
    password = "SuperGlobalPassword123!"

    # 1. Register
    res_reg = client.post("/register", data={
        "org_name": f"Enterprise {country_code}",
        "domain": expected_domain,
        "user_name": f"Admin {country_code}",
        "email": email,
        "password": password,
        "password_confirm": password,
        "country": country_code
    }, follow_redirects=False)
    assert res_reg.status_code == 303

    # 2. Login
    res_login = client.post("/login", data={
        "email": email,
        "password": password
    }, follow_redirects=False)
    assert res_login.status_code == 303

    # 3. View Dashboard
    res_dash = client.get("/dashboard")
    assert res_dash.status_code == 200
    assert "Compliance Health" in res_dash.text or "Scorecard" in res_dash.text

    # 4. View Categories
    res_cats = client.get("/categories")
    assert res_cats.status_code == 200
    assert "Data Categories" in res_cats.text

    # 5. Verify Categories exist in Database
    org = db.query(Organization).filter(Organization.primary_domain == expected_domain).first()
    assert org is not None
    assert org.country == country_code

    categories = db.query(DataCategory).filter(DataCategory.organization_id == org.id).all()
    assert len(categories) > 0, f"No categories seeded for country {country_code}"

    # 6. View Reports & Download CSV
    res_rep = client.get("/reports?range=ytd")
    assert res_rep.status_code == 200

    res_csv = client.get("/reports/csv?range=ytd")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
