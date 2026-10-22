"""SafeData operations CLI: python -m app.cli <command>."""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import UTC

from alembic.config import Config

from alembic import command

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log = logging.getLogger("safedata.cli")


def alembic_config(url: str | None = None) -> Config:
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(ROOT, "alembic"))
    if url:
        cfg.set_main_option("sqlalchemy.url_override", url)
    return cfg


def cmd_migrate(_args) -> int:
    command.upgrade(alembic_config(), "head")
    return 0


def cmd_adopt_legacy_db(_args) -> int:
    """For databases created by the old import-time create_all: patch legacy columns,
    create any missing tables, verify no drift, then stamp head."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    import app.models  # noqa: F401
    from app.core.legacy_schema import ensure_legacy_columns
    from app.database import Base, engine

    ensure_legacy_columns(engine)
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    if diff:
        log.error("Legacy DB still differs from models; not stamping: %s", diff)
        return 1
    # compare_metadata ignores CHECK constraints, so adopted legacy tables do not get the enum CHECKs.
    log.warning("Adopted legacy tables will not have the enum CHECK constraints (not detected by drift check).")
    # No drift against the FULL current models means the DB is already at head (create_all added
    # any missing tables, incl. job_locks/job_runs). Stamp head; do not upgrade.
    command.stamp(alembic_config(), "head")
    return 0


def cmd_create_admin(args) -> int:
    """Create (or repair) an admin login without going through /register.

    The registration form is the normal path, but it is useless when you are
    locked out: it refuses a domain or email that already exists, and a
    half-finished signup leaves exactly that state. This command is
    idempotent — it reuses an existing organisation, and resets the password
    of an existing user rather than failing.
    """
    import secrets
    from datetime import datetime, timedelta

    from app.auth import hash_password, password_policy_error, record_password_history
    from app.database import SessionLocal
    from app.helpers import is_free_tier_domain, provision_org_categories
    from app.models import Organization, User

    email = args.email.strip().lower()
    if "@" not in email:
        log.error("Not an email address: %s", email)
        return 1
    domain = email.split("@")[-1]

    # Same rule as passenger_wsgi.py: bring the schema to head first (idempotent),
    # so this works on a fresh database and right after a deploy, before any restart.
    if os.environ.get("SAFEDATA_AUTO_MIGRATE", "1") == "1":
        cmd_migrate(None)

    password = args.password or os.getenv("SAFEDATA_ADMIN_PASSWORD") or secrets.token_urlsafe(18)
    generated = not (args.password or os.getenv("SAFEDATA_ADMIN_PASSWORD"))

    policy_err = password_policy_error(password, user_email=email, user_name=args.name)
    if policy_err:
        log.error("Password rejected by policy: %s", policy_err)
        return 1

    db = SessionLocal()
    try:
        free_tier = is_free_tier_domain(domain)
        org = db.query(Organization).filter(Organization.primary_domain == domain).first()
        if org is None:
            now_utc = datetime.utcnow()
            slug_base = re.sub(r"[^a-z0-9]+", "-", (args.org or domain).lower()).strip("-")[:50] or "org"
            slug = slug_base
            for n in range(2, 100):  # slug is unique; a retried run must not collide
                if db.query(Organization).filter(Organization.slug == slug).first() is None:
                    break
                slug = f"{slug_base}-{n}"[:50]
            org = Organization(
                name=args.org or domain,
                slug=slug,
                primary_domain=domain,
                country=args.country,
                tier="enterprise" if free_tier else "core",
                status="active" if free_tier else "trial",
                subscription_status="active" if free_tier else "trial",
                trial_ends_at=None if free_tier else (now_utc + timedelta(days=14)),
            )
            db.add(org)
            db.commit()
            db.refresh(org)
            provision_org_categories(db, org.id, args.country)
            log.info("Created organisation %r (id=%s, tier=%s)", org.name, org.id, org.tier)
        else:
            # An existing 3Consulting org predating the free-tier rule stays on
            # whatever it was sold; only lift it when the domain qualifies.
            if free_tier and (org.tier != "enterprise" or org.status != "active"):
                org.tier, org.status, org.subscription_status = "enterprise", "active", "active"
                org.trial_ends_at = None
                db.commit()
                log.info("Upgraded existing organisation %r to free Enterprise", org.name)
            else:
                log.info("Reusing organisation %r (id=%s, tier=%s)", org.name, org.id, org.tier)

        pwd_hash = hash_password(password)
        user = db.query(User).filter(User.email == email).first()
        verified_now = datetime.now(UTC).replace(tzinfo=None)
        if user is None:
            user = User(
                organization_id=org.id,
                name=args.name,
                email=email,
                password_hash=pwd_hash,
                role="admin",
                is_active=True,
                must_change_password=False,
                email_verified_at=verified_now,
            )
            db.add(user)
            action = "Created"
        else:
            user.password_hash = pwd_hash
            user.role = "admin"
            user.is_active = True
            user.must_change_password = False
            user.deleted_at = None
            if user.email_verified_at is None:
                user.email_verified_at = verified_now
            action = "Reset"
        db.commit()
        db.refresh(user)
        record_password_history(db, user.id, pwd_hash)

        print()
        print(f"{action} SafeData admin")
        print(f"  URL       {os.getenv('APP_URL', 'https://safedata.3consult-ng.com')}/login")
        print(f"  Email     {email}")
        if generated:
            print(f"  Password  {password}")
            print("            (generated — store it now, it is not recoverable)")
        else:
            print("  Password  (as supplied)")
        print(f"  Org       {org.name} — tier={org.tier}, status={org.status}")
        if user.twofa_enabled:
            print("  NOTE      two-factor is enabled on this account; you still need your authenticator.")
        print()
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    # Read the same .env as the web app before anything imports app.config,
    # or commands run on the server would silently use a local SQLite file.
    from app.core.envfile import prepare_server_environment

    if prepare_server_environment(ROOT):
        log.debug("Loaded settings from %s", os.path.join(ROOT, ".env"))
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate").set_defaults(fn=cmd_migrate)
    sub.add_parser("adopt-legacy-db").set_defaults(fn=cmd_adopt_legacy_db)

    ca = sub.add_parser("create-admin", help="create or repair an admin login")
    ca.add_argument("--email", required=True, help="admin email; its domain becomes the organisation domain")
    ca.add_argument("--name", default="Administrator", help="person's display name")
    ca.add_argument("--org", default=None, help="organisation name (default: the email domain)")
    ca.add_argument("--country", default="NG", help="ISO-3166 alpha-2, drives the seeded category library")
    ca.add_argument(
        "--password", default=None, help="omit to generate one, or set SAFEDATA_ADMIN_PASSWORD to avoid shell history"
    )
    ca.set_defaults(fn=cmd_create_admin)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
