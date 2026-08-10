"""
Test login throttle — ported from PHP login_throttle_test.php.
Tests brute-force login prevention.
"""
import pytest
from app.auth import record_login_attempt, login_throttle_seconds


def test_no_throttle_below_limit(db):
    """Should not throttle when under 5 attempts."""
    for i in range(3):
        record_login_attempt(db, "test@example.com", "1.2.3.4", success=False)
    assert login_throttle_seconds(db, "test@example.com", "1.2.3.4") == 0


def test_throttle_after_limit(db):
    """Should throttle after 5 failed attempts."""
    for i in range(6):
        record_login_attempt(db, "brute@test.com", "5.6.7.8", success=False)
    seconds = login_throttle_seconds(db, "brute@test.com", "5.6.7.8")
    assert seconds > 0


def test_success_does_not_count(db):
    """Successful logins should not count toward throttle."""
    for i in range(3):
        record_login_attempt(db, "ok@test.com", "1.1.1.1", success=True)
    for i in range(2):
        record_login_attempt(db, "ok@test.com", "1.1.1.1", success=False)
    assert login_throttle_seconds(db, "ok@test.com", "1.1.1.1") == 0
