import io
from datetime import date
from app.models import ConnectedSystem, ApiKey, DataCategory, DataRecord, PendingRecalculation, Organization

def test_healthz_endpoint(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_connected_systems_and_api_keys(client, db):
    # Register org
    client.post("/register", data={
        "org_name": "API Corp",
        "domain": "apicorp.com",
        "user_name": "Admin",
        "email": "admin@apicorp.com",
        "password": "apicorppassword",
        "country": "US"
    })

    org = db.query(Organization).filter(Organization.primary_domain == "apicorp.com").first()

    # Create connected system
    res = client.post("/integrations/systems/create", data={
        "name": "Salesforce CRM",
        "system_type": "crm",
        "base_url": "https://crm.apicorp.com",
        "description": "Main CRM System"
    }, follow_redirects=False)
    assert res.status_code == 303

    sys_obj = db.query(ConnectedSystem).filter(ConnectedSystem.organization_id == org.id, ConnectedSystem.name == "Salesforce CRM").first()
    assert sys_obj is not None

    # Create API Key
    res = client.post("/integrations/keys/create", data={
        "system_id": sys_obj.id,
        "key_name": "Production Key",
        "rate_limit_per_min": 100,
        "permissions": ["ingest", "batch"]
    })
    assert res.status_code == 200
    assert "adrs_k1_" in res.text

def test_recalculations_approval_flow(client, db):
    # Setup org & category & record
    client.post("/register", data={
        "org_name": "Recalc Ltd",
        "domain": "recalc.io",
        "user_name": "DPO",
        "email": "dpo@recalc.io",
        "password": "recalcpass123",
        "country": "GB"
    })

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

    # Approve recalculation
    res = client.post(f"/recalculations/{recalc.id}/action", data={
        "decision": "recalculate"
    }, follow_redirects=False)
    assert res.status_code == 303

    db.refresh(rec)
    assert str(rec.retention_end_date) == "2027-01-01"
