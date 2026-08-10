"""
Test settings.
Tests settings read/write and org-scoped settings.
"""
import pytest
from app.models import SystemSetting, OrganizationSetting


def test_system_setting_write_read(db):
    """Should write and read a system setting."""
    setting = SystemSetting(setting_key="test_key", setting_value="test_value")
    db.add(setting)
    db.commit()

    row = db.query(SystemSetting).filter(SystemSetting.setting_key == "test_key").first()
    assert row is not None
    assert row.setting_value == "test_value"


def test_system_setting_update(db):
    """Should update an existing system setting."""
    db.add(SystemSetting(setting_key="update_key", setting_value="v1"))
    db.commit()

    row = db.query(SystemSetting).filter(SystemSetting.setting_key == "update_key").first()
    row.setting_value = "v2"
    db.commit()

    refreshed = db.query(SystemSetting).filter(SystemSetting.setting_key == "update_key").first()
    assert refreshed.setting_value == "v2"


def test_org_setting_scoped(db):
    """Org settings should be scoped per organization."""
    db.add(OrganizationSetting(organization_id=1, setting_key="color", setting_value="blue"))
    db.commit()

    row = db.query(OrganizationSetting).filter(
        OrganizationSetting.organization_id == 1,
        OrganizationSetting.setting_key == "color",
    ).first()
    assert row.setting_value == "blue"


def test_system_setting_fallback(db):
    """System setting should serve as default when no org setting exists."""
    db.add(SystemSetting(setting_key="fallback_key", setting_value="default"))
    db.commit()

    org_row = db.query(OrganizationSetting).filter(
        OrganizationSetting.organization_id == 1,
        OrganizationSetting.setting_key == "fallback_key",
    ).first()
    assert org_row is None

    sys_row = db.query(SystemSetting).filter(SystemSetting.setting_key == "fallback_key").first()
    assert sys_row.setting_value == "default"
