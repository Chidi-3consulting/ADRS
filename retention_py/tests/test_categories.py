from app.models import DataCategory, Organization

def test_auto_seeding_on_registration(client, db):
    # Register under India (IN)
    client.post("/register", data={
        "org_name": "Delhi Tech",
        "domain": "delhi.in",
        "user_name": "Aarav",
        "email": "aarav@delhi.in",
        "password": "delhitechpass",
        "country": "IN"
    })
    
    org = db.query(Organization).filter(Organization.primary_domain == "delhi.in").first()
    
    # Assert DPDP categories are seeded automatically (e.g. at least 3 seeded categories)
    cats = db.query(DataCategory).filter(
        DataCategory.organization_id == org.id,
        DataCategory.source == "seeded"
    ).all()
    
    assert len(cats) >= 3
    frameworks = [c.compliance_framework for c in cats]
    assert "DPDP" in frameworks
    assert "BOTH" in frameworks

def test_manual_category_framework_assignment(client, db):
    # Login session setup
    client.post("/register", data={
        "org_name": "Lagos Tech",
        "domain": "lagos.ng",
        "user_name": "Ola",
        "email": "ola@lagos.ng",
        "password": "lagostechpass",
        "country": "NG"
    })
    
    # Create category manually without compliance_framework (checkboxes removed)
    response = client.post("/categories/create", data={
        "name": "Audit Invoices",
        "description": "Tax and financial audit records",
        "retention_reason": "Statutory audit laws compliance",
        "legal_basis": "legal_obligation",
        "disposal_trigger": "date_based",
        "retention_period_days": 2555,
        "retention_period_label": "7 years",
        "disposal_method": "archive",
        "review_frequency": "annually",
        "requires_dual_approval": "on"
    }, follow_redirects=False)
    
    # Assert it redirected to /categories
    assert response.status_code == 303
    
    # Check category was created with NDPR,BOTH assigned automatically
    org = db.query(Organization).filter(Organization.primary_domain == "lagos.ng").first()
    cat = db.query(DataCategory).filter(
        DataCategory.organization_id == org.id,
        DataCategory.name == "Audit Invoices"
    ).first()
    
    assert cat is not None
    assert cat.compliance_framework == "NDPR,BOTH"
    assert cat.requires_dual_approval is True
