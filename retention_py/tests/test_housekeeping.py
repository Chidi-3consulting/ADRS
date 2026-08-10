"""
Test housekeeping.
Tests pruning of stale login_attempts, password_resets, and old notifications.
"""
import pytest
from datetime import datetime, timedelta
from app.engine import run_housekeeping
from app.models import LoginAttempt, PasswordReset, Notification, User


def _create_user(db):
    from app.auth import hash_password
    user = User(
        organization_id=1, name="Test User", email="hk@test.com",
        password_hash=hash_password("Password123!"), role="admin", is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_housekeeping_prunes_old_login_attempts(db):
    """Login attempts older than 30 days should be pruned."""
    old_date = datetime.utcnow() - timedelta(days=31)
    for i in range(5):
        attempt = LoginAttempt(email=f"test{i}@x.com", ip_address="1.2.3.4", success=False)
        db.add(attempt)
    db.commit()

    # Manually backdate
    for a in db.query(LoginAttempt).all():
        a.created_at = old_date
    db.commit()

    result = run_housekeeping(db)
    assert result["login_attempts"] >= 5


def test_housekeeping_prunes_expired_resets(db):
    """Expired password resets should be pruned."""
    old_date = datetime.utcnow() - timedelta(days=8)
    for i in range(3):
        reset = PasswordReset(
            email=f"test{i}@x.com", token_hash=f"hash_{i}",
            expires_at=old_date, used=False,
        )
        db.add(reset)
    db.commit()

    result = run_housekeeping(db)
    assert result["password_resets"] >= 3


def test_housekeeping_keeps_recent_data(db):
    """Recent login attempts and resets should NOT be pruned."""
    attempt = LoginAttempt(email="recent@x.com", ip_address="1.2.3.4", success=True)
    db.add(attempt)

    reset = PasswordReset(
        email="recent@x.com", token_hash="recent_hash",
        expires_at=datetime.utcnow() + timedelta(hours=1), used=False,
    )
    db.add(reset)
    db.commit()

    run_housekeeping(db)

    assert db.query(LoginAttempt).filter(LoginAttempt.email == "recent@x.com").count() == 1
    assert db.query(PasswordReset).filter(PasswordReset.email == "recent@x.com").count() == 1
