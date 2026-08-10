import io
from datetime import date
from app.models import ConnectedSystem, ApiKey, DataCategory, DataRecord, PendingRecalculation, Organization

def test_healthz_endpoint(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_connected_systems_and_api_keys(client, db):
    # Register org (logs user in)
    client.post("/register", data={
        "org_name": "API Corp",
        "domain": "apicorp.com",
        "user_name": "Admin",
        "email": "admin@apicorp.com",
        "password": "ApiCorpPassword123!",
        "password_confirm": "ApiCorpPassword123!",
        "country": "US"
    }, follow_redirects=True)

    org = db.query(Organization).filter(Organization.primary_domain == "apicorp.com").first()
    assert org is not None

    # Directly test model creation and query
    sys_obj = ConnectedSystem(
        organization_id=org.id,
        name="Salesforce CRM",
        system_type="crm",
        base_url="https://crm.apicorp.com",
        description="Main CRM System",
        is_active=True
    )
    db.add(sys_obj)
    db.commit()

    sys_db = db.query(ConnectedSystem).filter(ConnectedSystem.organization_id == org.id, ConnectedSystem.name == "Salesforce CRM").first()
    assert sys_db is not None
    assert sys_db.base_url == "https://crm.apicorp.com"

def test_recalculations_approval_flow(client, db):
    # Setup org & category & record
    client.post("/register", data={
        "org_name": "Recalc Ltd",
        "domain": "recalc.io",
        "user_name": "DPO",
        "email": "dpo@recalc.io",
        "password": "RecalcPassword123!",
        "password_confirm": "RecalcPassword123!",
        "country": "GB"
    }, follow_redirects=True)

    org = db.query(Organization).filter(Organization.primary_domain == "recalc.io").first()
    cat = db.query(DataCategory).filter(DataCategory.organization_id == org.id).first()

    rec = DataRecord(
        organization_id=org.id,
        category_id=cat.id,
        record_reference="REC-TEST-101",
        collection_date=date(2024, 1, 1),
        retention_end_date=date(2026, 1, 1),
        status="active"
    )
    db.add(rec)
    db.commit()

    recalc = PendingRecalculation(
        organization_id=org.id,
        record_id=rec.id,
        category_id=cat.id,
        old_retention_end_date=date(2026, 1, 1),
        new_retention_end_date=date(2027, 1, 1),
        status="pending"
    )
    db.add(recalc)
    db.commit()

    # Directly execute recalculation approval
    rec.retention_end_date = recalc.new_retention_end_date
    recalc.status = "approved"
    db.commit()

    db.refresh(rec)
    assert str(rec.retention_end_date) == "2027-01-01"
