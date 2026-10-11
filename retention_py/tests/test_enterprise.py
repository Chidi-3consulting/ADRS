"""
Test enterprise engine.
Tests API keys, intake queue, auto-categorisation, consent signals, and disposal dispatch.
"""
import pytest
import json
from datetime import datetime, timedelta
from app.enterprise import (
    generate_api_key, create_api_key, verify_api_key, revoke_api_key,
    api_key_can, auto_categorize, enqueue_intake, process_intake_queue,
    intake_is_duplicate, record_consent_signal, queue_disposal_dispatch,
    process_disposal_dispatches, run_enterprise_engine_steps,
)
from app.models import (
    ConnectedSystem, AutoCategorizationRule, DataCategory, DataRecord,
    ApiKey, IntakeQueue, ConsentSignal,
)


def _seed_system(db, org_id=1):
    system = ConnectedSystem(
        organization_id=org_id, name="Test CRM", base_url="https://crm.example.com",
        system_type="crm", is_active=True,
    )
    db.add(system)
    db.commit()
    db.refresh(system)
    return system


def _seed_category(db, org_id=1, trigger="date_based"):
    cat = DataCategory(
        organization_id=org_id, name="Test Category", description="Test",
        compliance_framework="GDPR", legal_basis="consent",
        retention_period_days=365, retention_period_label="1 year",
        disposal_method="delete", disposal_trigger=trigger,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


class TestApiKeys:
    def test_generate_api_key_format(self):
        k = generate_api_key()
        assert k["raw"].startswith("SafeData_")
        assert len(k["raw"]) == len("SafeData_") + 48
        assert len(k["hash"]) == 64

    def test_create_and_verify(self, db, auth_user):
        system = _seed_system(db)
        result = create_api_key(db, system.id, "Test Key", ["ingest"], 60, auth_user.id)
        assert "raw" in result
        assert "id" in result

        verified = verify_api_key(db, result["raw"])
        assert verified is not None
        assert verified.id == result["id"]

    def test_verify_invalid_key(self, db):
        assert verify_api_key(db, "invalid_key_12345") is None

    def test_revoke_key(self, db, auth_user):
        system = _seed_system(db)
        result = create_api_key(db, system.id, "Revocable", [], 60, auth_user.id)
        revoke_api_key(db, result["id"], auth_user.id)
        assert verify_api_key(db, result["raw"]) is None

    def test_api_key_can(self, db, auth_user):
        system = _seed_system(db)
        result = create_api_key(db, system.id, "Perms", ["ingest", "read"], 60, auth_user.id)
        key = verify_api_key(db, result["raw"])
        assert api_key_can(key, "ingest") is True
        assert api_key_can(key, "delete") is False


class TestAutoCategorize:
    def test_match_by_object_type(self, db):
        system = _seed_system(db)
        cat = _seed_category(db)
        rule = AutoCategorizationRule(
            system_id=system.id, object_type="employee_record",
            category_id=cat.id, priority=1, is_active=True,
        )
        db.add(rule)
        db.commit()

        result = auto_categorize(db, system.id, "employee_record")
        assert result == cat.id

    def test_no_match(self, db):
        system = _seed_system(db)
        result = auto_categorize(db, system.id, "unknown_type")
        assert result is None

    def test_condition_match(self, db):
        system = _seed_system(db)
        cat = _seed_category(db)
        rule = AutoCategorizationRule(
            system_id=system.id, object_type="doc",
            condition_field="department", condition_value="HR",
            category_id=cat.id, priority=1, is_active=True,
        )
        db.add(rule)
        db.commit()

        assert auto_categorize(db, system.id, "doc", {"department": "HR"}) == cat.id
        assert auto_categorize(db, system.id, "doc", {"department": "IT"}) is None


class TestIntakeQueue:
    def test_enqueue_and_process(self, db):
        system = _seed_system(db)
        cat = _seed_category(db)
        rule = AutoCategorizationRule(
            system_id=system.id, object_type="record",
            category_id=cat.id, priority=1, is_active=True,
        )
        db.add(rule)
        db.commit()

        enqueue_intake(db, system.id, None, "batch1", {
            "object_type": "record", "external_ref": "EXT-001",
            "data_subject_type": "employee",
        })

        result = process_intake_queue(db, 10)
        assert result["processed"] == 1
        assert result["created"] == 1
        assert result["failed"] == 0

    def test_duplicate_detection(self, db):
        cat = _seed_category(db)
        record = DataRecord(
            organization_id=1, category_id=cat.id,
            record_reference="DUP-001", status="active",
        )
        db.add(record)
        db.commit()

        assert intake_is_duplicate(db, "DUP-001", cat.id) is True
        assert intake_is_duplicate(db, "NEW-001", cat.id) is False


class TestConsentSignals:
    def test_consent_signal_match(self, db):
        system = _seed_system(db)
        cat = _seed_category(db, trigger="consent_withdrawal")
        record = DataRecord(
            organization_id=1, category_id=cat.id,
            record_reference="CONSENT-001", status="active",
        )
        db.add(record)
        db.commit()

        result = record_consent_signal(db, system.id, "CONSENT-001", "withdrawal")
        assert result["matched"] is True
        assert result["record_id"] is not None

    def test_consent_signal_no_match(self, db):
        system = _seed_system(db)
        result = record_consent_signal(db, system.id, "NOMATCH-001", "withdrawal")
        assert result["matched"] is False

    def test_api_consent_signal_endpoint(self, db, client, auth_user):
        system = _seed_system(db)
        key_res = create_api_key(db, system.id, "Consent Key", ["consent"], 60, auth_user.id)
        cat = _seed_category(db, trigger="consent_withdrawal")
        record = DataRecord(
            organization_id=1, category_id=cat.id,
            record_reference="API-CONSENT-001", status="active",
        )
        db.add(record)
        db.commit()

        # Call POST /api/v1/consent/signal
        resp = client.post(
            "/api/v1/consent/signal",
            headers={"X-API-Key": key_res["raw"]},
            json={
                "record_reference": "API-CONSENT-001",
                "signal_type": "withdrawal",
                "withdrawn_at": "2026-09-14T08:00:00Z",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["updated_records"] == 1

        db.refresh(record)
        assert record.consent_withdrawn_at is not None
        assert record.consent_withdrawn_by is None
        assert record.retention_end_date is not None

    def test_api_consent_withdraw_deprecation(self, db, client, auth_user):
        system = _seed_system(db)
        key_res = create_api_key(db, system.id, "Consent Key", ["consent"], 60, auth_user.id)
        cat = _seed_category(db, trigger="consent_withdrawal")
        record = DataRecord(
            organization_id=1, category_id=cat.id,
            record_reference="API-CONSENT-002", status="active",
        )
        db.add(record)
        db.commit()

        # Call deprecated POST /api/v1/consent/withdraw
        resp = client.post(
            "/api/v1/consent/withdraw",
            headers={"X-API-Key": key_res["raw"]},
            json={"record_reference": "API-CONSENT-002"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("Deprecation") == "true"

    def test_manual_consent_routes_removed(self, client):
        # Confirm manual UI routes no longer exist
        r1 = client.post("/records/consent/1")
        assert r1.status_code == 404
        r2 = client.post("/records/consent_withdraw/1")
        assert r2.status_code == 404

