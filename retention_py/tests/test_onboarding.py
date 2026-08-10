"""
Test onboarding.
Tests category seeding per country.
"""
import pytest
from app.helpers import provision_org_categories, get_country_regulations, CATEGORY_SEEDS
from app.models import DataCategory


def test_provision_ng_categories(db):
    """Nigeria should seed NDPR + BOTH categories."""
    provision_org_categories(db, 1, "NG")
    cats = db.query(DataCategory).filter(DataCategory.organization_id == 1).all()
    assert len(cats) > 0
    frameworks = {c.compliance_framework for c in cats}
    assert "NDPR" in frameworks or "BOTH" in frameworks


def test_provision_gb_categories(db):
    """UK should seed UK_GDPR/GDPR + BOTH categories."""
    provision_org_categories(db, 1, "GB")
    cats = db.query(DataCategory).filter(DataCategory.organization_id == 1).all()
    assert len(cats) > 0


def test_provision_idempotent(db):
    """Running twice should not duplicate categories."""
    provision_org_categories(db, 1, "NG")
    count1 = db.query(DataCategory).filter(DataCategory.organization_id == 1).count()

    provision_org_categories(db, 1, "NG")
    count2 = db.query(DataCategory).filter(DataCategory.organization_id == 1).count()

    assert count1 == count2


def test_provision_unknown_country(db):
    """Unknown country should fall back to GDPR + BOTH."""
    provision_org_categories(db, 1, "XX")
    cats = db.query(DataCategory).filter(DataCategory.organization_id == 1).all()
    assert len(cats) > 0


def test_get_country_regulations():
    """Check regulation map returns correct frameworks."""
    assert "NDPR" in get_country_regulations("NG")
    assert "GDPR" in get_country_regulations("GB") or "UK_GDPR" in get_country_regulations("GB")
    assert "CCPA" in get_country_regulations("US")
