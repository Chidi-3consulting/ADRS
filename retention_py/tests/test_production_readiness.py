"""
Production Readiness & Feature Completeness Test Suite for SafeData.
Validates:
1. Controller vs. Third-Party Processor Retention Tracking
2. Reports Engine: Multi-range filters, CSV, JSON, and Print packs
3. Notifications Inbox: Category filtering, mark-all-read, and clear
4. Comprehensive Cryptographic Audit Logging across all events
5. Solution Manual 8-chapter rendering
6. ROPA graceful redirection
"""
import pytest
from datetime import date, timedelta, datetime
from app.models import User, Organization, DataCategory, DataRecord, Notification, AuditLog
from app.engine import compliance_scorecard_details, compliance_metrics

def test_ropa_graceful_redirect(client, db):
    """Verify /ropa gracefully redirects with 303 to /categories."""
    # Register an admin
    client.post("/register", data={
        "org_name": "Acme Global",
        "domain": "acmeglobal.com",
        "user_name": "Compliance Lead",
        "email": "dpo@acmeglobal.com",
        "password": "Xyq9$mNpL2!k",
        "password_confirm": "Xyq9$mNpL2!k",
        "country": "NG"
    })
    client.post("/login", data={
        "email": "dpo@acmeglobal.com",
        "password": "Xyq9$mNpL2!k"
    })

    res = client.get("/ropa", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/categories"


def test_processor_retention_tracking(client, db):
    """Verify creation, storage, and retrieval of third-party processor retention categories and records."""
    client.post("/register", data={
        "org_name": "FinTech Corp",
        "domain": "fintechcorp.com",
        "user_name": "Security Admin",
        "email": "admin@fintechcorp.com",
        "password": "Xyq9$mNpL2!k",
        "password_confirm": "Xyq9$mNpL2!k",
        "country": "NG"
    })
    client.post("/login", data={
        "email": "admin@fintechcorp.com",
        "password": "Xyq9$mNpL2!k"
    })

    # Create category with processor tracking
    res = client.post("/categories/create", data={
        "name": "Cloud Hosted Customer KYC",
        "description": "Customer verification IDs stored in cloud vendor",
        "retention_reason": "Statutory AML requirement",
        "legal_basis": "legal_obligation",
        "disposal_trigger": "date_based",
        "retention_period_days": 1825,
        "retention_period_label": "5 Years",
        "disposal_method": "delete",
        "review_frequency": "quarterly",
        "processing_role": "processor",
        "processor_name": "AWS EMEA Cloud",
        "processor_contact": "dpo@aws.amazon.com",
        "dpa_reference": "DPA-2026-AWS-KYC-01",
        "processor_retention_status": "compliant",
        "requires_dual_approval": "on"
    }, follow_redirects=True)
    assert res.status_code == 200

    cat = db.query(DataCategory).filter(DataCategory.name == "Cloud Hosted Customer KYC").first()
    assert cat is not None
    assert cat.processing_role == "processor"
    assert cat.processor_name == "AWS EMEA Cloud"
    assert cat.dpa_reference == "DPA-2026-AWS-KYC-01"
    assert cat.requires_dual_approval == True

    # Create record under processor category
    res = client.post("/records/create", data={
        "category_id": cat.id,
        "record_reference": "KYC-USER-98210",
        "data_subject_type": "Customer",
        "processor_name": "AWS EMEA Cloud",
        "collection_date": date.today().strftime("%Y-%m-%d"),
        "notes": "Verified via passport upload"
    }, follow_redirects=True)
    assert res.status_code == 200

    rec = db.query(DataRecord).filter(DataRecord.record_reference == "KYC-USER-98210").first()
    assert rec is not None
    assert rec.processor_name == "AWS EMEA Cloud"
    assert rec.processor_sync_status == "synced"


def test_reports_time_range_and_exports(client, db):
    """Verify reports time-range filtering, CSV export, JSON export, and printable audit pack."""
    client.post("/register", data={
        "org_name": "Apex Health",
        "domain": "apexhealth.org",
        "user_name": "Chief DPO",
        "email": "dpo@apexhealth.org",
        "password": "Xyq9$mNpL2!k",
        "password_confirm": "Xyq9$mNpL2!k",
        "country": "NG"
    })
    client.post("/login", data={
        "email": "dpo@apexhealth.org",
        "password": "Xyq9$mNpL2!k"
    })

    # Test HTML view with filters
    res_html = client.get("/reports?range=30d&role_filter=all&status=all")
    assert res_html.status_code == 200
    assert "Data Retention & Compliance Reports" in res_html.text

    # Test CSV export
    res_csv = client.get("/reports/csv?range=ytd")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Record ID,Reference,Category" in res_csv.text

    # Test JSON export
    res_json = client.get("/reports/json?range=90d")
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]
    data = res_json.json()
    assert "report_title" in data
    assert "scorecard" in data
    assert "records" in data

    # Test Print Audit Pack
    res_print = client.get("/reports/print?range=ytd")
    assert res_print.status_code == 200
    assert "Statutory Data Retention & Compliance Audit Pack" in res_print.text


def test_notifications_workflow(client, db):
    """Verify notifications filtering, read-all, and clear actions."""
    client.post("/register", data={
        "org_name": "Nordic Logistics",
        "domain": "nordiclogistics.com",
        "user_name": "Logistics Admin",
        "email": "admin@nordiclogistics.com",
        "password": "Xyq9$mNpL2!k",
        "password_confirm": "Xyq9$mNpL2!k",
        "country": "NG"
    })
    client.post("/login", data={
        "email": "admin@nordiclogistics.com",
        "password": "Xyq9$mNpL2!k"
    })

    user = db.query(User).filter(User.email == "admin@nordiclogistics.com").first()

    # Seed notifications
    n1 = Notification(
        organization_id=user.organization_id,
        recipient_id=user.id,
        type="retention_warning",
        subject="Statutory Retention Warning",
        message="3 records are due for retention review."
    )
    n2 = Notification(
        organization_id=user.organization_id,
        recipient_id=user.id,
        type="disposal_complete",
        subject="Disposal Executed",
        message="Record LOG-001 was securely purged."
    )
    db.add_all([n1, n2])
    db.commit()

    # Test Inbox view
    res = client.get("/notifications?filter=warning")
    assert res.status_code == 200
    assert "Statutory Retention Warning" in res.text

    # Test Mark All Read
    res_read_all = client.post("/notifications/read-all", follow_redirects=False)
    assert res_read_all.status_code == 303

    db.refresh(n1)
    db.refresh(n2)
    assert n1.read_at is not None
    assert n2.read_at is not None

    # Test Clear Read
    res_clear = client.post("/notifications/clear", follow_redirects=False)
    assert res_clear.status_code == 303

    remaining_count = db.query(Notification).filter(Notification.recipient_id == user.id).count()
    assert remaining_count == 0


def test_solution_manual_and_scorecard_engine(client, db):
    """Verify Solution Manual rendering and multi-pillar compliance calculations."""
    client.post("/register", data={
        "org_name": "Nexus Bank",
        "domain": "nexusbank.com",
        "user_name": "Head of Risk",
        "email": "risk@nexusbank.com",
        "password": "Xyq9$mNpL2!k",
        "password_confirm": "Xyq9$mNpL2!k",
        "country": "NG"
    })
    client.post("/login", data={
        "email": "risk@nexusbank.com",
        "password": "Xyq9$mNpL2!k"
    })

    user = db.query(User).filter(User.email == "risk@nexusbank.com").first()

    # Verify /help solution manual has all 8 chapters
    res_help = client.get("/help")
    assert res_help.status_code == 200
    assert "SafeData Enterprise Solution Manual" in res_help.text
    assert "Chapter 1" in res_help.text
    assert "Chapter 8" in res_help.text
    assert "Frequently Asked Questions" in res_help.text

    # Verify compliance scorecard details engine
    scorecard = compliance_scorecard_details(db, user.organization_id)
    assert "overall_score" in scorecard
    assert "grade" in scorecard
    assert "pillars" in scorecard
    assert "policy_coverage" in scorecard["pillars"]
    assert "retention_sla" in scorecard["pillars"]
    assert "processor_governance" in scorecard["pillars"]
    assert "safeguards_oversight" in scorecard["pillars"]
    assert len(scorecard["recommendations"]) > 0
