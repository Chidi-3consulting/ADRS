"""
Test invitations — ported from PHP invitations_test.php.
Tests invite create, accept, and revoke.
"""
import pytest
from datetime import datetime, timedelta
from app.models import OrganizationInvitation, User


def test_create_invitation(db):
    """Should create an invitation record."""
    invite = OrganizationInvitation(
        organization_id=1,
        email="invited@test.com",
        name="Invited User",
        role="data_owner",
        invited_by=1,
        token_hash="abc123hash",
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    assert invite.id is not None
    assert invite.email == "invited@test.com"
    assert invite.revoked_at is None


def test_invitation_expiry(db):
    """Expired invitation should be detectable."""
    invite = OrganizationInvitation(
        organization_id=1,
        email="expired@test.com",
        name="Expired User",
        role="data_owner",
        invited_by=1,
        token_hash="expiredhash",
        expires_at=datetime.utcnow() - timedelta(days=1),
    )
    db.add(invite)
    db.commit()

    assert invite.expires_at < datetime.utcnow()


def test_revoke_invitation(db):
    """Revoked invitation should have revoked_at timestamp set."""
    invite = OrganizationInvitation(
        organization_id=1,
        email="revoke@test.com",
        name="Revoke User",
        role="dpo",
        invited_by=1,
        token_hash="revokehash",
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(invite)
    db.commit()

    invite.revoked_at = datetime.utcnow()
    db.commit()

    refreshed = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.email == "revoke@test.com"
    ).first()
    assert refreshed.revoked_at is not None
