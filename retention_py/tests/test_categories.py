from app.models import DataCategory, Organization

def test_auto_seeding_on_registration(client, db):
    # Register under India (IN)
    client.post("/register", data={
        "org_name": "Delhi Tech",
        "domain": "delhi.in",
        "user_name": "Aarav",
        "email": "aarav@delhi.in",
        "password": "DelhiTechPassword123!",
        "password_confirm": "DelhiTechPassword123!",
        "country": "IN"
    })

    org = db.query(Organization).filter(Organization.primary_domain == "delhi.in").first()
    assert org is not None

    # Assert DPDP categories are seeded automatically
    cats = db.query(DataCategory).filter(
        DataCategory.organization_id == org.id,
        DataCategory.source == "seeded"
    ).all()

    assert len(cats) >= 3
    frameworks = [c.compliance_framework for c in cats]
    assert any("DPDP" in f for f in frameworks)

def test_manual_category_framework_assignment(db):
    org = Organization(
        name="Lagos Tech",
        slug="lagos-tech",
        primary_domain="lagos.ng",
        country="NG",
        tier="core",
        status="active"
    )
    db.add(org)
    db.commit()

    cat = DataCategory(
        organization_id=org.id,
        name="Audit Invoices",
        description="Tax and financial audit records",
        retention_reason="Statutory audit laws compliance",
        legal_basis="legal_obligation",
        disposal_trigger="date_based",
        retention_period_days=2555,
        retention_period_label="7 years",
        disposal_method="archive",
        review_frequency="annually",
        requires_dual_approval=True
    )
    db.add(cat)
    db.commit()

    fetched = db.query(DataCategory).filter(
        DataCategory.organization_id == org.id,
        DataCategory.name == "Audit Invoices"
    ).first()

    assert fetched is not None
    assert fetched.requires_dual_approval is True
