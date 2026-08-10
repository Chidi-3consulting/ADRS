import pytest
import app.middleware
import app.config
from app.auth import (
    hash_password, verify_password, password_policy_error,
    login_throttle_seconds, record_login_attempt,
)
from app.models import User, Organization, LoginAttempt


def test_password_policy():
    # Min length check (10 chars)
    assert password_policy_error("short1") is not None
    # Missing numbers
    assert password_policy_error("onlyletters") is not None
    # Missing letters
    assert password_policy_error("1234567890") is not None
    # Valid password
    assert password_policy_error("ValidPass123!") is None


def test_login_throttling(db):
    email = "attacker@example.com"
    ip = "192.168.1.100"

    # Should not be throttled initially
    assert login_throttle_seconds(db, email, ip) == 0

    # Record 4 failed attempts
    for _ in range(4):
        record_login_attempt(db, email, ip, success=False)
    assert login_throttle_seconds(db, email, ip) == 0

    # 5th failed attempt triggers throttle
    record_login_attempt(db, email, ip, success=False)
    assert login_throttle_seconds(db, email, ip) > 0


def test_security_headers(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert "strict-origin-when-cross-origin" in response.headers.get("Referrer-Policy", "")
    assert "Content-Security-Policy" in response.headers


def test_csrf_protection(client):
    # Set APP_ENV to local to enable CSRF check during this test
    original_env = app.middleware.APP_ENV
    try:
        app.middleware.APP_ENV = "local"
        r = client.get("/login")
        assert r.status_code == 200

        # POST without CSRF token should return 403 Forbidden
        post_res = client.post("/login", data={"email": "bad@test.com", "password": "wrong"})
        assert post_res.status_code == 403
    finally:
        app.middleware.APP_ENV = original_env
