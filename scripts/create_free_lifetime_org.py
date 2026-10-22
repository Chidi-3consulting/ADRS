"""
Script to create or update a free lifetime enterprise account for 3consult-ng.com and its subdomains.

Actions performed:
1. Ensures organization for '3consult-ng.com' exists with:
   - tier: 'enterprise'
   - status: 'active'
   - subscription_status: 'active' (lifetime paid access)
   - trial_ends_at: None
2. Seeds compliance data categories and default retention rules for the organization (Nigeria / NDPR & GDPR baseline).
3. Ensures enterprise license key exists and is recorded.
4. Ensures admin user (admin@3consult-ng.com) is linked to this organization with full administrative permissions.
5. Enables 2FA for the admin account with a secure TOTP secret and backup recovery codes.
"""

import sys
import os
import json
import secrets
from pathlib import Path

# Add project root and retention_py root to sys.path so internal imports resolve cleanly
BASE_DIR = Path(__file__).resolve().parents[1]
RETENTION_DIR = BASE_DIR / "retention_py"

for p in [str(RETENTION_DIR), str(BASE_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("APP_ENV", "local")

from app.database import SessionLocal
from app.models import Organization, User, EnterpriseLicenceKey
from app.helpers import provision_org_categories, totp_generate_secret, generate_recovery_codes
from app.auth import encrypt_totp_secret, hash_password
from sqlalchemy.orm import Session


def setup_3consult_lifetime(db: Session):
    domain = "3consult-ng.com"
    slug = "3consult-ng"
    org_name = "3Consulting Limited"

    print(f"[1/5] Configuring free lifetime enterprise organization for '{domain}'...")
    org = db.query(Organization).filter(
        (Organization.slug == slug) | (Organization.primary_domain == domain)
    ).first()

    if org:
        org.name = org_name
        org.slug = slug
        org.primary_domain = domain
        org.tier = "enterprise"
        org.status = "active"
        org.subscription_status = "active"
        org.trial_ends_at = None
        db.add(org)
        print(f"      -> Updated existing organization (ID: {org.id}) to Enterprise / Active lifetime subscription.")
    else:
        org = Organization(
            name=org_name,
            slug=slug,
            primary_domain=domain,
            country="NG",
            tier="enterprise",
            status="active",
            subscription_status="active",
            trial_ends_at=None,
        )
        db.add(org)
        db.flush()
        print(f"      -> Created new organization (ID: {org.id}) with Enterprise / Active lifetime subscription.")

    db.commit()
    db.refresh(org)

    print("[2/5] Provisioning compliance data categories & retention rules...")
    provision_org_categories(db, org.id, org.country or "NG")
    db.commit()
    print("      -> Standard categories and retention rules ensured.")

    print("[3/5] Generating enterprise licence key...")
    license_key_prefix = "SafeData-ENT-3CONSULT"
    existing_key = db.query(EnterpriseLicenceKey).filter(
        EnterpriseLicenceKey.redeemed_by_organization_id == org.id
    ).first()

    if not existing_key:
        import hashlib
        raw_key = f"{license_key_prefix}-{secrets.token_hex(8).upper()}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        new_licence = EnterpriseLicenceKey(
            key_hash=key_hash,
            key_prefix=raw_key[:24],
            redeemed_by_organization_id=org.id,
            redeemed_at=org.created_at,
        )
        db.add(new_licence)
        org.enterprise_licence_key = raw_key[:24]
        db.commit()
        print(f"      -> Created enterprise licence record (Prefix: {raw_key[:24]}).")
    else:
        print(f"      -> Enterprise licence already linked (Prefix: {existing_key.key_prefix}).")

    print("[4/5] Associating admin@3consult-ng.com user...")
    admin_user = db.query(User).filter(User.email == "admin@3consult-ng.com").first()
    if admin_user:
        admin_user.organization_id = org.id
        admin_user.role = "admin"
        admin_user.is_platform_admin = True
        admin_user.is_active = True
        print(f"      -> Linked user '{admin_user.email}' (ID: {admin_user.id}) to organization '{org.name}'.")
    else:
        temp_pass = "SafeData2026!"
        admin_user = User(
            organization_id=org.id,
            name="SafeData Admin",
            email="admin@3consult-ng.com",
            password_hash=hash_password(temp_pass),
            role="admin",
            is_active=True,
            is_platform_admin=True,
        )
        db.add(admin_user)
        db.flush()
        print(f"      -> Created new admin user '{admin_user.email}' (ID: {admin_user.id}).")

    print("[5/5] Ensuring 2FA is active with secure TOTP secret & recovery codes...")
    if not admin_user.twofa_enabled or not admin_user.twofa_secret:
        totp_secret = totp_generate_secret()
        recovery = generate_recovery_codes(8)
        admin_user.twofa_enabled = True
        admin_user.twofa_secret = encrypt_totp_secret(totp_secret)
        admin_user.twofa_recovery = json.dumps(recovery["hashed"])
        print(f"      -> Enabled 2FA for {admin_user.email}.")
        print(f"         Plain TOTP Secret: {totp_secret}")
        print(f"         Backup Recovery Codes: {recovery['plain']}")
    else:
        print(f"      -> 2FA is already enabled for {admin_user.email}.")

    db.commit()
    print("\n[SUCCESS] Lifetime free enterprise access configured successfully for 3consult-ng.com!")


def main():
    db = SessionLocal()
    try:
        setup_3consult_lifetime(db)
    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] An error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
