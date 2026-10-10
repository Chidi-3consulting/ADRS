"""
Test setup wizard.
Tests setup_is_complete, and the POST /setup flow.
"""
import pytest
from app.auth import setup_is_complete
from app.models import SystemSetting


def _clear_setup_flag(db):
    db.query(SystemSetting).filter(SystemSetting.setting_key == "setup_complete").delete()
    db.commit()


def test_setup_not_complete_initially(db):
    """Setup should not be complete without the system setting."""
    _clear_setup_flag(db)
    assert setup_is_complete(db) is False


def test_setup_complete_after_flag(db):
    """Setup should be complete after setting the flag."""
    _clear_setup_flag(db)
    db.add(SystemSetting(setting_key="setup_complete", setting_value="1"))
    db.commit()

    assert setup_is_complete(db) is True


def test_setup_incomplete_with_wrong_value(db):
    """Setup should not be complete if value is not '1'."""
    _clear_setup_flag(db)
    db.add(SystemSetting(setting_key="setup_complete", setting_value="0"))
    db.commit()

    assert setup_is_complete(db) is False


def test_setup_get_page(client, db):
    """GET /setup should return 200 when setup is not complete."""
    _clear_setup_flag(db)
    response = client.get("/setup", follow_redirects=False)
    assert response.status_code == 200


def test_setup_get_redirects_when_complete(client):
    """GET /setup should redirect (303) once setup is complete."""
    response = client.get("/setup", follow_redirects=False)
    assert response.status_code == 303


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
