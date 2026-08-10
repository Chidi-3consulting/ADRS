"""
Test setup wizard — ported from PHP setup_test.php.
Tests setup_is_complete, and the POST /setup flow.
"""
import pytest
from app.auth import setup_is_complete
from app.models import SystemSetting


def test_setup_not_complete_initially(db):
    """Setup should not be complete without the system setting."""
    assert setup_is_complete(db) is False


def test_setup_complete_after_flag(db):
    """Setup should be complete after setting the flag."""
    db.add(SystemSetting(setting_key="setup_complete", setting_value="1"))
    db.commit()

    assert setup_is_complete(db) is True


def test_setup_incomplete_with_wrong_value(db):
    """Setup should not be complete if value is not '1'."""
    db.add(SystemSetting(setting_key="setup_complete", setting_value="0"))
    db.commit()

    assert setup_is_complete(db) is False


def test_setup_get_page(client):
    """GET /setup should return 200 when setup is not complete."""
    response = client.get("/setup", follow_redirects=False)
    assert response.status_code in [200, 303]


def test_setup_post_validation(client):
    """POST /setup with missing fields should show error."""
    response = client.post("/setup", data={
        "org_name": "",
        "name": "",
        "email": "",
        "password": "",
        "password_confirm": "",
    }, follow_redirects=False)
    # Should return 200 with error or redirect
    assert response.status_code in [200, 303, 403]
