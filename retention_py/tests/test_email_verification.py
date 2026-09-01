"""
Test email verification.
Tests token generation, verification, and expiry.
"""
import pytest
from datetime import datetime, timedelta
from app.auth import issue_email_verification_token, verify_email_token, hash_password
from app.models import User, PasswordReset


def _create_user(db, email="verify@test.com"):
    user = User(
        organization_id=1, name="Verify User", email=email,
        password_hash=hash_password("Password123!"),
        role="admin", is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_issue_token(db):
    """Should generate a verification token and store its hash."""
    user = _create_user(db)
    token = issue_email_verification_token(db, user.id)

    assert token  # Non-empty
    assert len(token) > 20  # urlsafe token

    # Check stored hash
    resets = db.query(PasswordReset).filter(PasswordReset.email == user.email).all()
    assert len(resets) == 1
    assert resets[0].token_hash.startswith("ev_")


def test_verify_valid_token(db):
    """Valid token should verify and mark user as email verified."""
    user = _create_user(db)
    token = issue_email_verification_token(db, user.id)

    result = verify_email_token(db, token)
    assert result is True

    # User should now have email_verified_at set
    refreshed = db.query(User).filter(User.id == user.id).first()
    assert refreshed.email_verified_at is not None


def test_verify_invalid_token(db):
    """Invalid token should fail."""
    _create_user(db)
    result = verify_email_token(db, "totally_invalid_token")
    assert result is False


def test_verify_expired_token(db):
    """Expired token should fail."""
    user = _create_user(db, "expired@test.com")
    token = issue_email_verification_token(db, user.id)

    # Manually expire the token
    reset = db.query(PasswordReset).filter(PasswordReset.email == user.email).first()
    reset.expires_at = datetime.utcnow() - timedelta(hours=1)
    db.commit()

    result = verify_email_token(db, token)
    assert result is False


def test_verify_used_token(db):
    """Used token should not work again."""
    user = _create_user(db, "used@test.com")
    token = issue_email_verification_token(db, user.id)

    assert verify_email_token(db, token) is True
    assert verify_email_token(db, token) is False  # Second use fails
