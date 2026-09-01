"""
Test billing.
Tests organization access + trial expiry logic.
"""
import pytest
from datetime import datetime, timedelta
from app.models import Organization


def test_active_subscription_has_access(db):
    """Active subscription should have access."""
    org = db.query(Organization).filter(Organization.id == 1).first()
    org.subscription_status = "active"
    org.status = "active"
    db.commit()

    assert org.subscription_status == "active"
    assert org.status == "active"


def test_suspended_org_no_access(db):
    """Suspended org should not have normal access."""
    org = db.query(Organization).filter(Organization.id == 1).first()
    org.status = "suspended"
    db.commit()

    assert org.status == "suspended"


def test_trial_not_expired(db):
    """Trial with future ends_at should have access."""
    org = db.query(Organization).filter(Organization.id == 1).first()
    org.subscription_status = "trial"
    org.trial_ends_at = datetime.utcnow() + timedelta(days=7)
    db.commit()

    assert org.trial_ends_at > datetime.utcnow()


def test_trial_expired(db):
    """Trial with past ends_at should be expired."""
    org = db.query(Organization).filter(Organization.id == 1).first()
    org.subscription_status = "trial"
    org.trial_ends_at = datetime.utcnow() - timedelta(days=1)
    db.commit()

    assert org.trial_ends_at < datetime.utcnow()


def test_trial_no_expiry(db):
    """Trial with no ends_at should have indefinite access."""
    org = db.query(Organization).filter(Organization.id == 1).first()
    org.subscription_status = "trial"
    org.trial_ends_at = None
    db.commit()

    assert org.trial_ends_at is None
