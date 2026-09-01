"""
Tests for Step-Up Re-Authentication (Safe Delete, Disposal, Legal Hold).
"""
import pytest
from app.models import User, Organization, DataCategory, DataRecord, AuditLog
from app.auth import hash_password, verify_stepup_authentication
from app.helpers import totp_generate_secret, totp_code, generate_recovery_codes


@pytest.fixture
def org_and_user(db):
    org = db.query(Organization).filter(Organization.id == 1).first()

    pwd = "CorrectSecretPassword123!"
    user = User(
        organization_id=org.id,
        email="dpo.security@example.com",
        name="Security DPO",
        role="dpo",
        password_hash=hash_password(pwd),
        is_active=True,
        twofa_enabled=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return org, user, pwd


def test_stepup_password_success(db, org_and_user):
    org, user, plain_pwd = org_and_user
    ok, msg = verify_stepup_authentication(db, user.id, plain_pwd)
    assert ok is True
    assert msg == "OK"


def test_stepup_password_failure(db, org_and_user):
    org, user, _ = org_and_user
    ok, msg = verify_stepup_authentication(db, user.id, "WrongPassword999!")
    assert ok is False
    assert "Invalid account password" in msg


def test_stepup_empty_credential(db, org_and_user):
    org, user, _ = org_and_user
    ok, msg = verify_stepup_authentication(db, user.id, "")
    assert ok is False
    assert "required" in msg.lower()


def test_stepup_with_2fa_enabled(db, org_and_user):
    org, user, plain_pwd = org_and_user
    secret = totp_generate_secret()
    rc = generate_recovery_codes(4)
    user.twofa_enabled = True
    user.twofa_secret = secret
    import json
    user.twofa_recovery = json.dumps(rc["hashed"])
    db.commit()

    # Valid TOTP code
    current_code = totp_code(secret)
    ok, msg = verify_stepup_authentication(db, user.id, current_code)
    assert ok is True

    # Account password still works as valid step-up
    ok, msg = verify_stepup_authentication(db, user.id, plain_pwd)
    assert ok is True

    # Invalid code
    ok, msg = verify_stepup_authentication(db, user.id, "000000")
    assert ok is False
