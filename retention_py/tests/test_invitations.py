"""
Test invitations.
Tests invite create, accept, and revoke.
"""
import pytest
from datetime import datetime, timedelta, timezone
from app.models import OrganizationInvitation, User


def test_create_invitation(db, auth_user):
    """Should create an invitation record."""
    invite = OrganizationInvitation(
        organization_id=1,
        email="invited@test.com",
        name="Invited User",
        role="data_owner",
        invited_by=auth_user.id,
        token_hash="abc123hash",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    assert invite.id is not None
    assert invite.email == "invited@test.com"
    assert invite.revoked_at is None


def test_invitation_expiry(db, auth_user):
    """Expired invitation should be detectable."""
    invite = OrganizationInvitation(
        organization_id=1,
        email="expired@test.com",
        name="Expired User",
        role="data_owner",
        invited_by=auth_user.id,
        token_hash="expiredhash",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1),
    )
    db.add(invite)
    db.commit()

    assert invite.expires_at < datetime.now(timezone.utc).replace(tzinfo=None)


def test_revoke_invitation(db, auth_user):
    """Revoked invitation should have revoked_at timestamp set."""
    invite = OrganizationInvitation(
        organization_id=1,
        email="revoke@test.com",
        name="Revoke User",
        role="dpo",
        invited_by=auth_user.id,
        token_hash="revokehash",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7),
    )
    db.add(invite)
    db.commit()

    invite.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    refreshed = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.email == "revoke@test.com"
    ).first()
    assert refreshed.revoked_at is not None
