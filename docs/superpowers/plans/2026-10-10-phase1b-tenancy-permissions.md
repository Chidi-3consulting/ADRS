# Phase 1B — Tenancy, Identity & Permissions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce Group → Entity → Unit, scoped memberships with the 7-role permission map, server-side sessions, an automatic tenant/scope filter on every query, verified domains, enforced email verification, a secure Platform Owner bootstrap, and close every access-control gap found in the audit.

**Architecture:** `app/core/permissions.py` (pure role→permission map), `app/core/sessions.py` (hybrid: signed pre-auth cookie + opaque server-side authenticated session), `app/core/context.py` (`Ctx`, `tenant_context`, `require(...)`), `app/core/tenancy.py` (SQLAlchemy `do_orm_execute` loader criteria), `app/domain/org/` (entities, units, domains, memberships services). Existing `get_session`/`set_session` keep their signatures so the ~90 existing call sites keep working while routes migrate to `require(...)`. Legacy `session["role"]` is derived from memberships during the transition.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 ORM events (`do_orm_execute`, `with_loader_criteria`), Alembic (hand-written data migration), itsdangerous, dnspython, pytest.

**Spec:** `docs/superpowers/specs/2026-10-10-safedata-launch-programme-design.md` (§2 D3–D6, §5.2, §6.4a, §9; findings F2–F4, F10, F11; SD-04-006, SD-04-007)

## Global Constraints

- Depends on Phase 1A merged (test fixtures, Alembic, `app/core/clock.py`, logging).
- Roles (exact identifiers): `owner`, `admin`, `privacy_officer`, `data_owner`, `contributor`, `auditor`, `viewer`. Platform roles: `platform_owner`, `super_admin`, `support`.
- Scope types (exact identifiers): `group`, `entity`, `unit`.
- Platform roles may only be held by users whose email ends with `@3consult-ng.com`; platform roles require 2FA enabled before platform pages render.
- No shared passwords; the Platform Owner password is entered interactively at bootstrap, never read from code, files or env.
- A verified domain belongs to exactly one Group. Pending claims never block anyone.
- Every page or action a role cannot use is blocked server-side (403 for authenticated users, redirect to `/login` for anonymous).
- Session idle timeout 1800 s, absolute 28800 s (unchanged values from `app/config.py`).
- All "now" via `app.core.clock.utcnow()`.
- Full test suite green at the end of every task.

## Review Focus

1. **User belongs to two Groups and switches** — expect queries return only the active Group's rows; switching to a Group they do not belong to returns 403 (Task 4 test `test_switch_to_foreign_group_forbidden`).
2. **Entity-scoped Privacy Officer opens a record id from a sibling entity in the same Group** — expect 404 (Task 4 test `test_entity_scope_hides_sibling_entity_records`).
3. **Deactivated user with a live session cookie** — expect the next request is treated as signed out (Task 3 test `test_deactivated_user_session_rejected`).
4. **Session store unavailable** — expect the request is treated as anonymous (fail closed), never as the previously cached role (Task 3 test `test_session_lookup_failure_fails_closed`).
5. **Two organisations claim the same domain; one verifies** — expect the verifier owns it, the other claim is released, and the other org's admin is notified (Task 7 test `test_verification_releases_competing_claims`).

---

## File Structure

```
retention_py/app/core/permissions.py      # ROLES, PERMISSIONS, role_has()
retention_py/app/core/sessions.py         # hybrid session store; get/set/clear/revoke
retention_py/app/core/context.py          # Ctx, build_ctx, tenant_context, require
retention_py/app/core/tenancy.py          # tenant filter event + TENANT_MODELS
retention_py/app/domain/__init__.py
retention_py/app/domain/org/__init__.py
retention_py/app/domain/org/structure.py  # create_default_entity, units
retention_py/app/domain/org/domains.py    # claim, verify_dns, verify_email_token
retention_py/app/domain/org/memberships.py# grant, revoke, legacy_role
retention_py/app/models.py                # Entity, Unit, EntityDomain, Membership, UserSession; org billing_mode; entity_id/unit_id cols; platform_role
retention_py/alembic/versions/0003_hierarchy.py
retention_py/app/auth.py                  # get_session/set_session/clear_session delegate to core.sessions
retention_py/app/middleware.py            # SessionEnforcement simplified; setup guard removed
retention_py/app/cli.py                   # + create-platform-owner, grant-platform-role
retention_py/app/routes/*.py              # require(...) per route; entity_id on create
retention_py/tests/conftest.py            # login_as helper
retention_py/tests/test_tenancy_*.py
```

---

### Task 1: Permission map

**Files:**
- Create: `retention_py/app/core/permissions.py`
- Test: `retention_py/tests/test_tenancy_permissions.py`

**Interfaces:**
- Produces: `ROLES: tuple[str, ...]`, `PERMISSIONS: dict[str, frozenset[str]]`, `role_has(role: str, permission: str) -> bool`, `LEGACY_ROLE: dict[str, str]` (new role → `admin`/`dpo`/`data_owner`).

- [ ] **Step 1: Write the failing test**

```python
# retention_py/tests/test_tenancy_permissions.py
import pytest

from app.core.permissions import LEGACY_ROLE, PERMISSIONS, ROLES, role_has


def test_roles_exact():
    assert ROLES == ("owner", "admin", "privacy_officer", "data_owner", "contributor", "auditor", "viewer")


def test_every_permission_references_known_roles():
    for perm, roles in PERMISSIONS.items():
        assert roles <= set(ROLES), perm


@pytest.mark.parametrize("role,perm,expected", [
    ("data_owner", "categories.manage", False),   # F2: data owners cannot change retention rules
    ("data_owner", "ropa.manage", False),
    ("contributor", "records.import", True),
    ("contributor", "records.dispose.request", False),
    ("privacy_officer", "records.dispose.approve", True),
    ("admin", "billing.manage", False),
    ("owner", "billing.manage", True),
    ("auditor", "evidence.export", True),
    ("auditor", "records.create", False),
    ("viewer", "reports.view", True),
    ("viewer", "audit.view", False),
])
def test_matrix(role, perm, expected):
    assert role_has(role, perm) is expected


def test_unknown_permission_raises():
    with pytest.raises(KeyError):
        role_has("owner", "nope.nope")


def test_legacy_mapping():
    assert LEGACY_ROLE == {"owner": "admin", "admin": "admin", "privacy_officer": "dpo",
                           "data_owner": "data_owner", "contributor": "data_owner",
                           "auditor": "data_owner", "viewer": "data_owner"}
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_tenancy_permissions.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# retention_py/app/core/permissions.py
"""Single source of truth for who can do what. Used by route guards, navigation and templates."""
ROLES = ("owner", "admin", "privacy_officer", "data_owner", "contributor", "auditor", "viewer")

_ALL = frozenset(ROLES)
_GOV = frozenset({"owner", "admin", "privacy_officer"})
_ADM = frozenset({"owner", "admin"})

PERMISSIONS: dict[str, frozenset[str]] = {
    "dashboard.view": _ALL,
    "notifications.view": _ALL,
    "records.view": _ALL,
    "records.create": _GOV | {"data_owner", "contributor"},
    "records.import": _GOV | {"data_owner", "contributor"},
    "records.edit": _GOV | {"data_owner"},
    "records.dispose.request": _GOV | {"data_owner"},
    "records.dispose.approve": _GOV,
    "records.legal_hold": _GOV,
    "records.reassign": _GOV,
    "records.export": _GOV | {"auditor"},
    "attachments.view": _GOV | {"auditor"},
    "attachments.upload": _GOV | {"data_owner"},
    "categories.view": _ALL,
    "categories.manage": _GOV,
    "recalculations.manage": _GOV,
    "ropa.view": _GOV | {"auditor", "viewer"},
    "ropa.manage": _GOV,
    "reports.view": _GOV | {"auditor", "viewer"},
    "audit.view": _GOV | {"auditor"},
    "audit.verify": _GOV | {"auditor"},
    "evidence.export": _GOV | {"auditor"},
    "users.manage": _ADM,
    "structure.manage": _ADM,
    "domains.manage": _ADM,
    "settings.manage": _ADM,
    "integrations.manage": _ADM,
    "billing.manage": frozenset({"owner"}),
    "org.delete": frozenset({"owner"}),
}

LEGACY_ROLE = {"owner": "admin", "admin": "admin", "privacy_officer": "dpo",
               "data_owner": "data_owner", "contributor": "data_owner",
               "auditor": "data_owner", "viewer": "data_owner"}


def role_has(role: str, permission: str) -> bool:
    return role in PERMISSIONS[permission]
```

- [ ] **Step 4: Run tests** → PASS.

- [ ] **Step 5: Commit**

```bash
git add retention_py/app/core/permissions.py retention_py/tests/test_tenancy_permissions.py
git commit -m "feat(auth): single role-to-permission map for the 7 scoped roles"
```

---

### Task 2: Hierarchy models and data migration

Fixes SD-04-007 (org id defaults to 1).

**Files:**
- Modify: `retention_py/app/models.py`
- Create: `retention_py/alembic/versions/0003_hierarchy.py` (hand-written)
- Create: `retention_py/app/domain/__init__.py`, `retention_py/app/domain/org/__init__.py`, `retention_py/app/domain/org/structure.py`
- Test: `retention_py/tests/test_tenancy_hierarchy.py`

**Interfaces:**
- Produces models: `Entity(id, organization_id, name, legal_name, country, timezone, dpo_user_id, status, created_at)`, `Unit(id, organization_id, entity_id, name, created_at)`, `EntityDomain(id, organization_id, entity_id, domain, status ∈ {pending, verified}, method ∈ {dns, email, legacy}, token_hash, verified_at, created_at)`, `Membership(id, user_id, organization_id, scope_type, scope_id, role, expires_at, created_by, created_at)`, `UserSession` (Task 3 uses it), `Organization.billing_mode ∈ {standard, internal, complimentary}`, `comp_plan`, `comp_ends_at`, `comp_reason`, `comp_granted_by`; `User.platform_role` nullable; `entity_id` on `data_categories`, `data_records`, `dsar_requests`, `ropa_entries`, `dpia_assessments`, `breach_incidents`, `consent_receipts`; `unit_id` on `data_records`.
- Produces: `create_default_entity(db, org: Organization) -> Entity` in `app/domain/org/structure.py`.

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_tenancy_hierarchy.py
import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.org.structure import create_default_entity
from app.models import DataCategory, Entity, EntityDomain, Membership, Organization


def test_create_default_entity_copies_org_country_and_domain(db):
    org = db.get(Organization, 1)
    ent = create_default_entity(db, org)
    assert ent.organization_id == 1 and ent.country == "NG" and ent.name == org.name
    dom = db.query(EntityDomain).filter_by(entity_id=ent.id).one()
    assert dom.domain == "test.local" and dom.status == "pending"


def test_category_requires_organization(db):
    db.add(DataCategory(name="orphan", retention_period_days=1, entity_id=None))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_verified_domain_unique_across_groups(db):
    org2 = Organization(name="O2", slug="o2", primary_domain="o2.test", country="GB", tier="core", status="active")
    db.add(org2); db.commit()
    e1 = create_default_entity(db, db.get(Organization, 1))
    e2 = create_default_entity(db, org2)
    db.add(EntityDomain(organization_id=1, entity_id=e1.id, domain="shared.com", status="verified", method="dns"))
    db.commit()
    db.add(EntityDomain(organization_id=org2.id, entity_id=e2.id, domain="shared.com", status="verified", method="dns"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_membership_scope_values_constrained(db):
    db.add(Membership(user_id=1, organization_id=1, scope_type="planet", scope_id=1, role="owner"))
    with pytest.raises(Exception):
        db.commit()
    db.rollback()
```

And a migration backfill test in `tests/test_foundation_migrations.py`:

```python
def test_hierarchy_migration_backfills_legacy_rows(tmp_path):
    from sqlalchemy import text
    from app.cli import alembic_config
    url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    cfg = alembic_config(url)
    command.upgrade(cfg, "0002_worker_tables")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("INSERT INTO organizations (id,name,slug,primary_domain,country,tier,status,subscription_status,created_at,updated_at) "
                       "VALUES (7,'Acme','acme','acme.ng','NG','core','active','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        for uid, role in ((1, "admin"), (2, "admin"), (3, "dpo"), (4, "data_owner")):
            c.execute(text("INSERT INTO users (id,organization_id,name,email,password_hash,role,is_active,must_change_password,is_platform_admin,twofa_enabled,created_at,updated_at) "
                           f"VALUES ({uid},7,'u{uid}','u{uid}@acme.ng','x','{role}',1,0,0,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        c.execute(text("INSERT INTO data_categories (id,organization_id,name,compliance_framework,legal_basis,retention_period_days,retention_period_label,disposal_method,disposal_trigger,data_classification,approval_type,requires_dual_approval,review_frequency,processing_role,source,is_active,created_at,updated_at) "
                       "VALUES (1,7,'HR','NDPR','contract',365,'1 year','delete','date_based','standard','single_approval',0,'quarterly','controller','custom',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    command.upgrade(cfg, "head")
    with eng.connect() as c:
        ent = c.execute(text("SELECT id, country FROM entities WHERE organization_id=7")).one()
        assert ent.country == "NG"
        assert c.execute(text("SELECT entity_id FROM data_categories WHERE id=1")).scalar() == ent.id
        roles = dict(c.execute(text("SELECT user_id, role FROM memberships WHERE organization_id=7")).all())
        assert roles == {1: "owner", 2: "admin", 3: "privacy_officer", 4: "data_owner"}
        dom = c.execute(text("SELECT domain, status, method FROM entity_domains WHERE organization_id=7")).one()
        assert tuple(dom) == ("acme.ng", "verified", "legacy")
```

- [ ] **Step 2: Run to verify failure** → FAIL (models missing).

- [ ] **Step 3: Models** — in `app/models.py`:
  1. Remove `default=1` from **every** `organization_id = Column(...)` (keep `nullable=False`).
  2. Add to `Organization`: 

```python
    billing_mode = Column(Enum("standard", "internal", "complimentary", name="org_billing_mode"),
                          default="standard", nullable=False)
    comp_plan = Column(String(64), nullable=True)
    comp_ends_at = Column(DateTime, nullable=True)
    comp_reason = Column(String(255), nullable=True)
    comp_granted_by = Column(Integer, nullable=True)
```
  3. Add to `User`: `platform_role = Column(Enum("platform_owner", "super_admin", "support", name="platform_role"), nullable=True)`.
  4. Add `entity_id = Column(Integer, ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False, index=True)` to `DataCategory`, `DataRecord`, `DsarRequest`, `RopaEntry`, `DpiaAssessment`, `BreachIncident`, `ConsentReceipt`; and `unit_id = Column(Integer, ForeignKey("units.id", ondelete="SET NULL"), nullable=True, index=True)` to `DataRecord`.
  5. Append new models:

```python
class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255), nullable=True)
    country = Column(String(2), nullable=False)
    timezone = Column(String(64), nullable=False, default="UTC")
    dpo_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(Enum("active", "archived", name="entity_status"), nullable=False, default="active")
    created_at = Column(DateTime, default=func.now(), nullable=False)


class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class EntityDomain(Base):
    __tablename__ = "entity_domains"
    __table_args__ = (
        Index("uq_verified_domain", "domain", unique=True,
              sqlite_where=text("status = 'verified'"), postgresql_where=text("status = 'verified'")),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    domain = Column(String(255), nullable=False, index=True)
    status = Column(Enum("pending", "verified", name="domain_status"), nullable=False, default="pending")
    method = Column(Enum("dns", "email", "legacy", name="domain_method"), nullable=True)
    token_hash = Column(String(64), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "organization_id", "scope_type", "scope_id", "role",
                                       name="uq_membership"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    scope_type = Column(Enum("group", "entity", "unit", name="membership_scope"), nullable=False)
    scope_id = Column(Integer, nullable=False)
    role = Column(Enum("owner", "admin", "privacy_officer", "data_owner", "contributor", "auditor", "viewer",
                       name="membership_role"), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(64), primary_key=True)  # sha256 hex of the cookie token
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    data = Column(JSON, nullable=False, default=dict)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
```
  Add `Index, UniqueConstraint, text` to the `from sqlalchemy import (...)` line.

- [ ] **Step 4: `app/domain/org/structure.py`**

```python
from sqlalchemy.orm import Session

from app.models import Entity, EntityDomain, Organization


def create_default_entity(db: Session, org: Organization) -> Entity:
    """Every Group starts with one Entity mirroring its country and primary domain."""
    ent = Entity(organization_id=org.id, name=org.name, country=(org.country or "NG"), timezone="UTC")
    db.add(ent)
    db.flush()
    db.add(EntityDomain(organization_id=org.id, entity_id=ent.id, domain=org.primary_domain, status="pending"))
    db.commit()
    db.refresh(ent)
    return ent
```

- [ ] **Step 5: Write `alembic/versions/0003_hierarchy.py` by hand** — structure:

```python
"""hierarchy: entities, units, domains, memberships, sessions; entity_id backfill"""
import sqlalchemy as sa
from alembic import op

revision = "0003_hierarchy"
down_revision = "0002_worker_tables"

SCOPED = ["data_categories", "data_records", "dsar_requests", "ropa_entries",
          "dpia_assessments", "breach_incidents", "consent_receipts"]
LEGACY = {"admin": "admin", "dpo": "privacy_officer", "data_owner": "data_owner"}


def upgrade():
    # 1. new tables — op.create_table(...) for entities, units, entity_domains (+ partial unique
    #    index uq_verified_domain), memberships (+ uq_membership), user_sessions, matching the models
    #    exactly (copy column definitions from app/models.py; enums as sa.Enum(..., native_enum=False,
    #    create_constraint=True, name=...)).
    # 2. new columns, nullable for now
    with op.batch_alter_table("organizations") as b:
        b.add_column(sa.Column("billing_mode", sa.Enum("standard", "internal", "complimentary",
                     name="org_billing_mode", native_enum=False, create_constraint=True),
                     nullable=False, server_default="standard"))
        for col in (sa.Column("comp_plan", sa.String(64)), sa.Column("comp_ends_at", sa.DateTime()),
                    sa.Column("comp_reason", sa.String(255)), sa.Column("comp_granted_by", sa.Integer())):
            b.add_column(col)
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("platform_role", sa.Enum("platform_owner", "super_admin", "support",
                     name="platform_role", native_enum=False, create_constraint=True), nullable=True))
    for t in SCOPED:
        with op.batch_alter_table(t) as b:
            b.add_column(sa.Column("entity_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("data_records") as b:
        b.add_column(sa.Column("unit_id", sa.Integer(), nullable=True))

    # 3. backfill
    conn = op.get_bind()
    now = sa.func.now()
    orgs = conn.execute(sa.text("SELECT id, name, country, primary_domain FROM organizations")).all()
    for org in orgs:
        conn.execute(sa.text("INSERT INTO entities (organization_id, name, country, timezone, status, created_at) "
                             "VALUES (:o, :n, :c, 'UTC', 'active', CURRENT_TIMESTAMP)"),
                     {"o": org.id, "n": org.name, "c": org.country or "NG"})
        ent_id = conn.execute(sa.text("SELECT max(id) FROM entities WHERE organization_id=:o"), {"o": org.id}).scalar()
        conn.execute(sa.text("INSERT INTO entity_domains (organization_id, entity_id, domain, status, method, verified_at, created_at) "
                             "VALUES (:o, :e, :d, 'verified', 'legacy', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
                     {"o": org.id, "e": ent_id, "d": org.primary_domain})
        for t in SCOPED:
            conn.execute(sa.text(f"UPDATE {t} SET entity_id=:e WHERE organization_id=:o"), {"e": ent_id, "o": org.id})
        users = conn.execute(sa.text("SELECT id, role FROM users WHERE organization_id=:o AND deleted_at IS NULL ORDER BY id"),
                             {"o": org.id}).all()
        first_admin = next((u.id for u in users if u.role == "admin"), None)
        for u in users:
            role = "owner" if u.id == first_admin else LEGACY.get(u.role, "data_owner")
            conn.execute(sa.text("INSERT INTO memberships (user_id, organization_id, scope_type, scope_id, role, created_at) "
                                 "VALUES (:u, :o, 'group', :o, :r, CURRENT_TIMESTAMP)"),
                         {"u": u.id, "o": org.id, "r": role})
    conn.execute(sa.text("UPDATE users SET platform_role='platform_owner' WHERE is_platform_admin = :t"), {"t": True})

    # 4. enforce
    for t in SCOPED:
        with op.batch_alter_table(t) as b:
            b.alter_column("entity_id", existing_type=sa.Integer(), nullable=False)
            b.create_foreign_key(f"fk_{t}_entity", "entities", ["entity_id"], ["id"], ondelete="RESTRICT")
            b.create_index(f"ix_{t}_entity_id", ["entity_id"])
    with op.batch_alter_table("data_records") as b:
        b.create_foreign_key("fk_data_records_unit", "units", ["unit_id"], ["id"], ondelete="SET NULL")
        b.create_index("ix_data_records_unit_id", ["unit_id"])


def downgrade():
    for t in ["data_records"]:
        with op.batch_alter_table(t) as b:
            b.drop_index("ix_data_records_unit_id")
            b.drop_constraint("fk_data_records_unit", type_="foreignkey")
            b.drop_column("unit_id")
    for t in SCOPED:
        with op.batch_alter_table(t) as b:
            b.drop_index(f"ix_{t}_entity_id")
            b.drop_constraint(f"fk_{t}_entity", type_="foreignkey")
            b.drop_column("entity_id")
    with op.batch_alter_table("users") as b:
        b.drop_column("platform_role")
    with op.batch_alter_table("organizations") as b:
        for c in ("comp_granted_by", "comp_reason", "comp_ends_at", "comp_plan", "billing_mode"):
            b.drop_column(c)
    for t in ("user_sessions", "memberships", "entity_domains", "units", "entities"):
        op.drop_table(t)
```
(Write out the five `op.create_table` calls in full in the file — they mirror the model definitions in Step 3 column-for-column. Run `test_migrations_match_models` to prove they match.)

Note: legacy domains are marked `verified/legacy` because they were already accepted as unique by the old registration; new registrations start `pending` (Task 7).

- [ ] **Step 6: Fix fixtures and seed code for NOT NULL `entity_id`** — in `tests/conftest.py` `db` fixture, after the org is created call `create_default_entity(session, org)` and keep its id as `session.info["test_entity_id"]`; add a fixture:

```python
@pytest.fixture
def entity_id(db):
    return db.info["test_entity_id"]
```
Run the full suite; every failure is a place that creates a scoped row without `entity_id`. In **tests**, pass `entity_id=entity_id`. In **app code**, do not patch here — Task 6 fixes app creation paths; temporarily mark those tests `@pytest.mark.xfail(reason="entity_id on create — Phase 1B Task 6", strict=True)` and list them in the commit body so Task 6 removes every marker.

- [ ] **Step 7: Run tests** — `python -m pytest tests/test_tenancy_hierarchy.py tests/test_foundation_migrations.py -v` → PASS; full suite green (with the strict xfails).

- [ ] **Step 8: Commit**

```bash
git add retention_py/app/models.py retention_py/app/domain retention_py/alembic/versions/0003_hierarchy.py retention_py/tests
git commit -m "feat(tenancy): entities, units, domains, memberships, sessions schema + legacy backfill; remove org_id default=1"
```

---

### Task 3: Server-side sessions

Fixes F10 / SD-04-004.

**Files:**
- Create: `retention_py/app/core/sessions.py`
- Modify: `retention_py/app/auth.py` (`get_session`, `set_session`, `clear_session`, `build_session_data` delegate), `retention_py/app/middleware.py` (remove idle/absolute/freshness blocks lines ~262–312; redirect when `request.state.session_expired`), `retention_py/app/routes/public.py` (`handle_logout` revokes), `retention_py/app/engine.py` `run_housekeeping` (prune sessions)
- Modify: `retention_py/tests/conftest.py` (add `login_as`)
- Test: `retention_py/tests/test_tenancy_sessions.py`

**Interfaces:**
- Consumes: `UserSession`, `Membership`, `LEGACY_ROLE`, `utcnow`, `SESSION_IDLE_TIMEOUT`, `SESSION_ABSOLUTE_TIMEOUT`.
- Produces:
  - `AUTH_COOKIE = "SafeData_session"`, `PRE_COOKIE = "SafeData_pre"`
  - `load(request) -> dict` (cached on `request.state._sd_session`; authenticated dict contains fresh claims + `"_sid"`)
  - `save(response, data: dict, request=None) -> None`
  - `revoke(db, sid: str) -> None`, `revoke_all(db, user_id: int, except_sid: str | None = None) -> int`
  - `claims_for(db, user, org) -> dict` (replaces `build_session_data`'s DB-derived part; `role` = legacy role)
  - conftest `login_as(client, user, org_id=1) -> None`

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_tenancy_sessions.py
from datetime import timedelta

from app.auth import hash_password
from app.core.clock import utcnow
from app.core import sessions
from app.models import Membership, User, UserSession


def _user(db, email="s@test.local", role="admin"):
    u = User(organization_id=1, name="S", email=email, password_hash=hash_password("Xyq9$mNpL2!k"),
             role=role, is_active=True, email_verified_at=utcnow())
    db.add(u); db.commit()
    db.add(Membership(user_id=u.id, organization_id=1, scope_type="group", scope_id=1, role="owner"))
    db.commit()
    return u


def test_login_creates_server_session_and_opaque_cookie(client, db):
    _user(db)
    r = client.post("/login", data={"email": "s@test.local", "password": "Xyq9$mNpL2!k"}, follow_redirects=False)
    assert r.status_code == 303
    token = client.cookies.get("SafeData_session")
    assert token and "." not in token  # opaque, not a signed payload
    assert db.query(UserSession).count() == 1


def test_logout_revokes(client, db):
    _user(db)
    client.post("/login", data={"email": "s@test.local", "password": "Xyq9$mNpL2!k"})
    client.get("/logout")
    db.expire_all()
    assert db.query(UserSession).one().revoked_at is not None
    assert client.get("/dashboard", follow_redirects=False).headers["location"].startswith("/login")


def test_deactivated_user_session_rejected(client, db, login_as):
    u = _user(db)
    login_as(client, u)
    assert client.get("/dashboard", follow_redirects=False).status_code == 200
    u.is_active = False; db.commit()
    assert client.get("/dashboard", follow_redirects=False).headers["location"].startswith("/login")


def test_idle_timeout(client, db, login_as):
    u = _user(db)
    login_as(client, u)
    row = db.query(UserSession).one()
    row.last_seen_at = utcnow() - timedelta(seconds=1801); db.commit()
    r = client.get("/dashboard", follow_redirects=False)
    assert r.headers["location"] == "/login?expired=1"


def test_revoke_all_signs_out_other_devices(db):
    u = _user(db)
    for i in range(3):
        db.add(UserSession(id=f"{i:064d}", user_id=u.id, organization_id=1, data={},
                           created_at=utcnow(), last_seen_at=utcnow()))
    db.commit()
    assert sessions.revoke_all(db, u.id, except_sid=f"{0:064d}") == 2


def test_session_lookup_failure_fails_closed(client, db, login_as, monkeypatch):
    u = _user(db)
    login_as(client, u)
    def broken(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(sessions, "_lookup", broken)
    r = client.get("/dashboard", follow_redirects=False)
    assert r.headers["location"].startswith("/login")


def test_role_change_reflected_in_claims_immediately(db):
    from app.models import Organization
    u = _user(db)
    m = db.query(Membership).filter_by(user_id=u.id).one()
    m.role = "viewer"; db.commit()
    claims = sessions.claims_for(db, u, db.get(Organization, 1))
    assert claims["roles"] == ["viewer"] and claims["role"] == "data_owner"
```

- [ ] **Step 2: Add `login_as` and `make_user` fixtures to `tests/conftest.py`**

```python
@pytest.fixture
def login_as(db):
    from app.core import sessions
    from app.models import Organization

    def _login(client, user, org_id=1):
        token = sessions.create_for_test(db, user, db.get(Organization, org_id))
        client.cookies.set(sessions.AUTH_COOKIE, token)
    return _login


@pytest.fixture
def make_user(db):
    """Create a verified, active user with a membership. Legacy User.role kept in sync."""
    from app.core.clock import utcnow
    from app.core.permissions import LEGACY_ROLE
    from app.models import Membership

    def _make(role="owner", email=None, org_id=1, scope_type="group", scope_id=None):
        u = User(organization_id=org_id, name=role, email=email or f"{role}-{utcnow().timestamp()}@test.local",
                 password_hash=hash_password("Xyq9$mNpL2!k"), role=LEGACY_ROLE[role], is_active=True,
                 email_verified_at=utcnow())
        db.add(u); db.commit()
        db.add(Membership(user_id=u.id, organization_id=org_id, scope_type=scope_type,
                          scope_id=scope_id if scope_id is not None else org_id, role=role))
        db.commit()
        return u
    return _make
```
Existing tests that create users directly and then log in must switch to `make_user` (a user with no membership is treated as signed out).

- [ ] **Step 3: Run to verify failure** → FAIL.

- [ ] **Step 4: Implement `app/core/sessions.py`**

```python
"""Hybrid sessions: anonymous/pre-auth state in a signed cookie; authenticated state in
user_sessions (cookie carries only a random token). Identity claims are rebuilt from the
database on every request, so role/status changes apply immediately. Any failure → anonymous."""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from itsdangerous import BadSignature, URLSafeSerializer

from app.config import (COOKIE_SAMESITE, COOKIE_SECURE, SECRET_KEY, SESSION_ABSOLUTE_TIMEOUT,
                        SESSION_IDLE_TIMEOUT)
from app.core.clock import utcnow
from app.core.permissions import LEGACY_ROLE

log = logging.getLogger("safedata.sessions")
AUTH_COOKIE, PRE_COOKIE = "SafeData_session", "SafeData_pre"
_pre = URLSafeSerializer(SECRET_KEY, salt="SafeData-pre-session")
_CLAIM_KEYS = {"user_id", "user_name", "email", "role", "roles", "org_id", "org_name", "org_domain",
               "org_status", "country", "is_platform_admin", "platform_role", "must_change_password",
               "twofa_enabled", "email_verified", "subscription_status", "trial_ends_at", "billing_mode"}
_ROLE_PRIORITY = ("owner", "admin", "privacy_officer", "data_owner", "contributor", "auditor", "viewer")


def _sid(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def claims_for(db, user, org) -> dict:
    from app.models import Membership
    now = utcnow()
    roles = [m.role for m in db.query(Membership).filter(
        Membership.user_id == user.id, Membership.organization_id == org.id).all()
        if m.expires_at is None or m.expires_at > now]
    top = next((r for r in _ROLE_PRIORITY if r in roles), None)
    return {
        "user_id": user.id, "user_name": user.name, "email": user.email,
        "roles": sorted(set(roles)), "role": LEGACY_ROLE.get(top, "none"),
        "org_id": org.id, "org_name": org.name, "org_domain": org.primary_domain,
        "org_status": org.status, "country": org.country or "OTHER",
        "is_platform_admin": bool(user.platform_role), "platform_role": user.platform_role,
        "must_change_password": bool(user.must_change_password), "twofa_enabled": bool(user.twofa_enabled),
        "email_verified": user.email_verified_at is not None,
        "subscription_status": org.subscription_status or "trial",
        "trial_ends_at": org.trial_ends_at.isoformat() if org.trial_ends_at else None,
        "billing_mode": org.billing_mode,
    }


def _lookup(token: str, request) -> dict | None:
    from app.database import SessionLocal
    from app.models import Organization, User, UserSession
    db = SessionLocal()
    try:
        row = db.get(UserSession, _sid(token))
        now = utcnow()
        if row is None or row.revoked_at is not None:
            return None
        if (now - row.last_seen_at).total_seconds() > SESSION_IDLE_TIMEOUT or \
           (now - row.created_at).total_seconds() > SESSION_ABSOLUTE_TIMEOUT:
            row.revoked_at = now
            db.commit()
            request.state.session_expired = True
            return None
        user, org = db.get(User, row.user_id), db.get(Organization, row.organization_id)
        if user is None or not user.is_active or user.deleted_at is not None or org is None:
            return None
        claims = claims_for(db, user, org)
        if claims["role"] == "none" and not claims["is_platform_admin"]:
            return None  # no live membership in this group
        if (now - row.last_seen_at).total_seconds() > 60:
            row.last_seen_at = now
            db.commit()
        return {**(row.data or {}), **claims, "_sid": row.id}
    finally:
        db.close()


def load(request) -> dict:
    cached = getattr(request.state, "_sd_session", None)
    if cached is not None:
        return cached
    data: dict = {}
    token = request.cookies.get(AUTH_COOKIE)
    if token:
        try:
            data = _lookup(token, request) or {}
        except Exception:
            log.exception("session lookup failed; treating request as anonymous")
            data = {}
    if not data:
        raw = request.cookies.get(PRE_COOKIE)
        if raw:
            try:
                data = dict(_pre.loads(raw))
            except BadSignature:
                data = {}
    request.state._sd_session = data
    return data


def _set_cookie(response, name: str, value: str) -> None:
    response.set_cookie(name, value, httponly=True, samesite=COOKIE_SAMESITE, secure=COOKIE_SECURE)


def _persist(db, data: dict, request=None) -> str | None:
    """Create or update the server row; returns a new token when a row was created."""
    from app.models import UserSession
    payload = {k: v for k, v in data.items() if k not in _CLAIM_KEYS and k != "_sid"}
    if data.get("_sid"):
        row = db.get(UserSession, data["_sid"])
        if row is not None and row.revoked_at is None:
            row.data = payload
            db.commit()
        return None
    token = secrets.token_urlsafe(32)
    now = utcnow()
    ip = request.client.host if request is not None and request.client else None
    ua = request.headers.get("user-agent", "")[:255] if request is not None else None
    db.add(UserSession(id=_sid(token), user_id=data["user_id"], organization_id=data["org_id"],
                       data=payload, ip_address=ip, user_agent=ua, created_at=now, last_seen_at=now))
    db.commit()
    return token


def save(response, data: dict, request=None) -> None:
    if "user_id" in data:
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            token = _persist(db, data, request)
        finally:
            db.close()
        if token:
            _set_cookie(response, AUTH_COOKIE, token)
            response.delete_cookie(PRE_COOKIE)
    else:
        _set_cookie(response, PRE_COOKIE, _pre.dumps(data))


def clear(response) -> None:
    response.delete_cookie(AUTH_COOKIE)
    response.delete_cookie(PRE_COOKIE)


def revoke(db, sid: str) -> None:
    from app.models import UserSession
    row = db.get(UserSession, sid)
    if row is not None and row.revoked_at is None:
        row.revoked_at = utcnow()
        db.commit()


def revoke_all(db, user_id: int, except_sid: str | None = None) -> int:
    from app.models import UserSession
    q = db.query(UserSession).filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if except_sid:
        q = q.filter(UserSession.id != except_sid)
    n = q.update({UserSession.revoked_at: utcnow()}, synchronize_session=False)
    db.commit()
    return n


def prune(db, older_than_days: int = 30) -> int:
    from app.models import UserSession
    cutoff = utcnow() - timedelta(days=older_than_days)
    n = db.query(UserSession).filter(UserSession.last_seen_at < cutoff).delete(synchronize_session=False)
    db.commit()
    return n


def create_for_test(db, user, org) -> str:
    return _persist(db, claims_for(db, user, org))
```

- [ ] **Step 5: Delegate in `app/auth.py`** — replace `serializer` usages and the four functions:

```python
from app.core import sessions as _sessions


def get_session(request: Request) -> dict:
    return _sessions.load(request)


def set_session(response: Response, data: dict, request: Request | None = None):
    _sessions.save(response, data, request)


def clear_session(response: Response):
    _sessions.clear(response)


def build_session_data(user, org, extra: dict = None) -> dict:
    """Login helper: claims + fresh CSRF token (rotated at every login)."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        data = _sessions.claims_for(db, user, org)
    finally:
        db.close()
    data["csrf_token"] = secrets.token_hex(32)
    if extra:
        data.update(extra)
    return data
```
Keep `serializer` defined only if other modules import it (`grep -rn "serializer" app tests`); migrate test usages to `login_as` and delete it.

- [ ] **Step 6: Simplify `SessionEnforcementMiddleware.dispatch`** — delete the setup-complete guard (moved to Task 9), the idle/absolute timeout blocks and the freshness re-sync block. After `session = get_session(request)` add:

```python
        if getattr(request.state, "session_expired", False):
            response = RedirectResponse(url="/login?expired=1", status_code=303)
            clear_session(response)
            return response
        if not session or "user_id" not in session:
            return await call_next(request)
```
Keep the must-change-password, email-verification, 2FA and subscription checks. Replace the trailing `set_session(response, session)` with `set_session(response, session, request)`.

- [ ] **Step 7: Logout revokes** — in `routes/public.py` `handle_logout`, before clearing:

```python
    sid = session.get("_sid") if session else None
    if sid:
        from app.core.sessions import revoke
        revoke(db, sid)
```
Login handlers: pass `request` to `set_session(redir, session_data, request)` so IP/UA are recorded.

- [ ] **Step 8: Housekeeping** — in `engine.run_housekeeping` add `result["sessions_pruned"] = sessions.prune(db, 30)` (import inside function).

- [ ] **Step 9: Profile: sign out other devices** — add to `routes/app_pages.py`:

```python
@router.post("/profile/sessions/revoke-others")
def revoke_other_sessions(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    from app.core.sessions import revoke_all
    n = revoke_all(db, session["user_id"], except_sid=session.get("_sid"))
    log_audit(db, session["org_id"], "sessions_revoked", "user", session["user_id"], session["user_id"],
              {"count": n}, request.client.host if request.client else None)
    return RedirectResponse(url="/profile?sessions_revoked=1", status_code=303)
```
and in `profile.html` add a "Signed-in devices" card listing `UserSession` rows for the user (created, last seen, IP, user agent; "this device" badge for `_sid`) with a POST form to the route above (pass `sessions` from `view_profile`).

- [ ] **Step 10: Run tests** — `python -m pytest tests/test_tenancy_sessions.py -v` → PASS; full suite green (replace remaining `serializer.dumps(...)` cookie setting in tests with `login_as`).

- [ ] **Step 11: Commit**

```bash
git add retention_py/app retention_py/tests
git commit -m "feat(auth): server-side sessions with revocation, fresh claims per request, fail-closed lookup"
```

---

### Task 4: Request context, permission guard and automatic tenant/scope filter

**Files:**
- Create: `retention_py/app/core/context.py`, `retention_py/app/core/tenancy.py`
- Modify: `retention_py/main.py` (import `app.core.tenancy` to register the event), `retention_py/tests/conftest.py` (`client` override clears tenant info)
- Test: `retention_py/tests/test_tenancy_isolation.py`

**Interfaces:**
- Consumes: `get_session`, `Membership`, `Entity`, `Unit`, `role_has`, `PERMISSIONS`.
- Produces:
  - `@dataclass Ctx(user_id, org_id, memberships: list[tuple[str, str, int]] (role, scope_type, scope_id), full_entity_ids: set[int] | None, unit_ids: set[int], default_entity_id: int, is_platform_admin: bool)` with methods `can(perm, entity_id=None, unit_id=None) -> bool`, `roles() -> set[str]`, `only_own_records() -> bool` (True when every role is `data_owner`/`contributor`).
  - `build_ctx(db, user_id: int, org_id: int) -> Ctx`
  - `tenant_context(request, db=Depends(get_db)) -> Ctx | None` (sets `db.info["tenant_org_id"]`, `db.info["tenant_entities"]`, `db.info["tenant_units"]`, `request.state.ctx`)
  - `require(permission: str)` → FastAPI dependency returning `Ctx`
  - `TENANT_MODELS: list[type]`, `ENTITY_SCOPED_MODELS: list[type]`; execution option `skip_tenant_filter=True` for deliberate cross-tenant platform queries.

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_tenancy_isolation.py
import pytest
from sqlalchemy import select

from app.auth import hash_password
from app.core.clock import utcnow
from app.core.context import build_ctx
from app.core.tenancy import TENANT_MODELS
from app.domain.org.structure import create_default_entity
from app.models import DataCategory, DataRecord, Entity, Membership, Organization, Unit, User


def _org(db, slug):
    o = Organization(name=slug, slug=slug, primary_domain=f"{slug}.test", country="GB", tier="core",
                     status="active", subscription_status="active")
    db.add(o); db.commit()
    return o, create_default_entity(db, o)


def _user(db, org_id, email, role, scope_type="group", scope_id=None):
    u = User(organization_id=org_id, name=email, email=email, password_hash=hash_password("Xyq9$mNpL2!k"),
             role="admin", is_active=True, email_verified_at=utcnow())
    db.add(u); db.commit()
    db.add(Membership(user_id=u.id, organization_id=org_id, scope_type=scope_type,
                      scope_id=scope_id if scope_id is not None else org_id, role=role))
    db.commit()
    return u


def test_every_table_with_organization_id_is_a_tenant_model():
    from app.database import Base
    tables = {t.name for t in Base.metadata.sorted_tables if "organization_id" in t.c}
    assert tables == {m.__tablename__ for m in TENANT_MODELS}


def test_tenant_filter_hides_other_groups_rows(db, entity_id):
    o2, e2 = _org(db, "other")
    db.add_all([DataCategory(organization_id=1, entity_id=entity_id, name="mine", retention_period_days=1),
                DataCategory(organization_id=o2.id, entity_id=e2.id, name="theirs", retention_period_days=1)])
    db.commit()
    db.info["tenant_org_id"] = 1
    try:
        names = [c.name for c in db.scalars(select(DataCategory))]
    finally:
        db.info.pop("tenant_org_id")
    assert names == ["mine"]


def test_skip_tenant_filter_option(db, entity_id):
    o2, e2 = _org(db, "other")
    db.add(DataCategory(organization_id=o2.id, entity_id=e2.id, name="theirs", retention_period_days=1)); db.commit()
    db.info["tenant_org_id"] = 1
    try:
        rows = db.scalars(select(DataCategory).execution_options(skip_tenant_filter=True)).all()
    finally:
        db.info.pop("tenant_org_id")
    assert [r.name for r in rows] == ["theirs"]


def test_entity_scope_hides_sibling_entity_records(client, db, login_as, entity_id):
    sibling = Entity(organization_id=1, name="Sibling", country="GB"); db.add(sibling); db.commit()
    cat = DataCategory(organization_id=1, entity_id=sibling.id, name="sib", retention_period_days=1)
    db.add(cat); db.commit()
    rec = DataRecord(organization_id=1, entity_id=sibling.id, category_id=cat.id, record_reference="SIB-1")
    db.add(rec); db.commit()
    po = _user(db, 1, "po@test.local", "privacy_officer", "entity", entity_id)
    login_as(client, po)
    assert client.get(f"/records/view/{rec.id}", follow_redirects=False).status_code == 404


def test_unit_member_sees_only_unit_records(db, entity_id):
    u1 = Unit(organization_id=1, entity_id=entity_id, name="HR"); u2 = Unit(organization_id=1, entity_id=entity_id, name="Fin")
    db.add_all([u1, u2]); db.commit()
    member = _user(db, 1, "hr@test.local", "data_owner", "unit", u1.id)
    ctx = build_ctx(db, member.id, 1)
    assert ctx.full_entity_ids == set() and ctx.unit_ids == {u1.id}
    assert ctx.can("records.create", entity_id=entity_id, unit_id=u1.id)
    assert not ctx.can("records.create", entity_id=entity_id, unit_id=u2.id)


def test_group_member_sees_all(db, entity_id):
    owner = _user(db, 1, "o@test.local", "owner")
    ctx = build_ctx(db, owner.id, 1)
    assert ctx.full_entity_ids is None and ctx.can("billing.manage")


def test_expired_membership_ignored(db):
    from datetime import timedelta
    aud = _user(db, 1, "aud@test.local", "auditor")
    m = db.query(Membership).filter_by(user_id=aud.id).one()
    m.expires_at = utcnow() - timedelta(minutes=1); db.commit()
    assert build_ctx(db, aud.id, 1).roles() == set()


def test_switch_to_foreign_group_forbidden(client, db, login_as):
    o2, _ = _org(db, "foreign")
    me = _user(db, 1, "me@test.local", "owner")
    login_as(client, me)
    r = client.post("/context/switch", data={"organization_id": o2.id}, follow_redirects=False)
    assert r.status_code == 403
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Implement `app/core/tenancy.py`**

```python
"""Automatic tenant and scope filtering for every ORM SELECT on a request-bound session."""
from sqlalchemy import event, or_
from sqlalchemy.orm import Session, with_loader_criteria

from app.database import Base


def _classes_with(column: str) -> list[type]:
    out = []
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if column in mapper.columns and cls.__tablename__ != "organizations":
            out.append(cls)
    return sorted(out, key=lambda c: c.__tablename__)


import app.models  # noqa: E402,F401  (ensure mappers are configured)

TENANT_MODELS = _classes_with("organization_id")
ENTITY_SCOPED_MODELS = [c for c in _classes_with("entity_id") if c.__tablename__ not in ("units", "entity_domains")]


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(state):
    if not state.is_select or state.execution_options.get("skip_tenant_filter"):
        return
    org_id = state.session.info.get("tenant_org_id")
    if org_id is None:
        return
    opts = [with_loader_criteria(cls, lambda c: c.organization_id == org_id, include_aliases=True)
            for cls in TENANT_MODELS]
    entity_set = state.session.info.get("tenant_entities")  # None = all entities in the group
    if entity_set is not None:
        from app.models import DataRecord
        # lists (not sets): lambda closure values become expanding bound parameters
        entities = sorted(entity_set)
        units = sorted(state.session.info.get("tenant_units") or ())
        visible = sorted(set(entity_set) | set(state.session.info.get("tenant_unit_entities") or ()))
        for cls in ENTITY_SCOPED_MODELS:
            if cls is DataRecord:
                opts.append(with_loader_criteria(
                    cls, lambda c: or_(c.entity_id.in_(entities), c.unit_id.in_(units)), include_aliases=True))
            else:
                opts.append(with_loader_criteria(cls, lambda c: c.entity_id.in_(visible), include_aliases=True))
    state.statement = state.statement.options(*opts)
```

- [ ] **Step 4: Implement `app/core/context.py`**

```python
"""Per-request context: who, which group, which scopes, what they may do."""
from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import get_session
from app.core.clock import utcnow
from app.core.permissions import role_has
from app.database import get_db


@dataclass
class Ctx:
    user_id: int
    org_id: int
    memberships: list[tuple[str, str, int]]  # (role, scope_type, scope_id)
    full_entity_ids: set[int] | None          # None = every entity in the group
    unit_ids: set[int] = field(default_factory=set)
    unit_entity: dict[int, int] = field(default_factory=dict)  # unit_id -> entity_id
    default_entity_id: int = 0
    is_platform_admin: bool = False

    def roles(self) -> set[str]:
        return {r for r, _, _ in self.memberships}

    def _covers(self, scope_type: str, scope_id: int, entity_id: int | None, unit_id: int | None) -> bool:
        if scope_type == "group":
            return True
        if scope_type == "entity":
            return entity_id is None or entity_id == scope_id
        # unit scope: page-level checks pass; resource checks need the same unit
        if entity_id is None and unit_id is None:
            return True
        return unit_id == scope_id

    def can(self, permission: str, entity_id: int | None = None, unit_id: int | None = None) -> bool:
        return any(role_has(role, permission) and self._covers(st, sid, entity_id, unit_id)
                   for role, st, sid in self.memberships)

    def only_own_records(self) -> bool:
        return bool(self.memberships) and self.roles() <= {"data_owner", "contributor"}


def build_ctx(db: Session, user_id: int, org_id: int) -> Ctx:
    from app.models import Entity, Membership, Unit, User
    now = utcnow()
    rows = [m for m in db.query(Membership).filter(Membership.user_id == user_id,
                                                    Membership.organization_id == org_id)
                                           .execution_options(skip_tenant_filter=True).all()
            if m.expires_at is None or m.expires_at > now]
    memberships = [(m.role, m.scope_type, m.scope_id) for m in rows]
    entity_ids = [e.id for e in db.query(Entity.id).filter(Entity.organization_id == org_id)
                  .order_by(Entity.id).execution_options(skip_tenant_filter=True).all()]
    unit_entity = {u.id: u.entity_id for u in db.query(Unit).filter(Unit.organization_id == org_id)
                   .execution_options(skip_tenant_filter=True).all()}
    if any(st == "group" for _, st, _ in memberships):
        full, units = None, set()
    else:
        full = {sid for _, st, sid in memberships if st == "entity"}
        units = {sid for _, st, sid in memberships if st == "unit"}
    user = db.get(User, user_id)
    return Ctx(user_id=user_id, org_id=org_id, memberships=memberships, full_entity_ids=full,
               unit_ids=units, unit_entity=unit_entity,
               default_entity_id=entity_ids[0] if entity_ids else 0,
               is_platform_admin=bool(user and user.platform_role))


def tenant_context(request: Request, db: Session = Depends(get_db)) -> Ctx | None:
    session = get_session(request)
    if not session or "user_id" not in session:
        return None
    ctx = build_ctx(db, session["user_id"], session["org_id"])
    db.info["tenant_org_id"] = ctx.org_id
    db.info["tenant_entities"] = ctx.full_entity_ids
    db.info["tenant_units"] = ctx.unit_ids
    db.info["tenant_unit_entities"] = {ctx.unit_entity[u] for u in ctx.unit_ids if u in ctx.unit_entity}
    request.state.ctx = ctx
    return ctx


def require(permission: str):
    def dependency(ctx: Ctx | None = Depends(tenant_context)) -> Ctx:
        if ctx is None:
            raise HTTPException(status_code=303, detail="login required")  # handled → /login
        if not ctx.can(permission):
            raise HTTPException(status_code=403, detail="Permission denied")
        return ctx
    return dependency
```

- [ ] **Step 5: Register the event** — in `main.py` after router imports: `import app.core.tenancy  # noqa: F401 (registers tenant filter)`.

- [ ] **Step 6: Clear tenant info after each test request** — in `conftest.py` `client` fixture:

```python
    def override_get_db():
        try:
            yield db
        finally:
            for k in ("tenant_org_id", "tenant_entities", "tenant_units", "tenant_unit_entities"):
                db.info.pop(k, None)
```
And in `app/database.py` `get_db`, the session is new per request so nothing to clear.

- [ ] **Step 7: Group switch endpoint** — add to `routes/app_pages.py`:

```python
@router.post("/context/switch")
def switch_group(request: Request, organization_id: int = Form(...), db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    from app.models import Membership, Organization, User
    has = db.query(Membership).filter(Membership.user_id == session["user_id"],
                                      Membership.organization_id == organization_id) \
            .execution_options(skip_tenant_filter=True).first()
    if not has:
        raise HTTPException(status_code=403, detail="Not a member of that organisation")
    from app.core.sessions import revoke
    revoke(db, session["_sid"])
    user, org = db.get(User, session["user_id"]), db.get(Organization, organization_id)
    redir = RedirectResponse(url="/dashboard", status_code=303)
    set_session(redir, build_session_data(user, org), request)
    log_audit(db, organization_id, "group_switched", "user", user.id, user.id, {}, request.client.host if request.client else None)
    return redir
```

- [ ] **Step 8: Run tests** — `python -m pytest tests/test_tenancy_isolation.py -v`. `test_entity_scope_hides_sibling_entity_records` needs Task 5's router dependency; mark it `xfail(strict=True, reason="router deps in Task 5")` now and remove the marker in Task 5. Others PASS; full suite green.

- [ ] **Step 9: Commit**

```bash
git add retention_py/app/core/context.py retention_py/app/core/tenancy.py retention_py/main.py retention_py/app/routes/app_pages.py retention_py/tests
git commit -m "feat(tenancy): request context, permission guard, automatic tenant and scope query filter"
```

---

### Task 5: Guard every route with permissions

Fixes F2 / SD-04-001 and F3 / SD-04-002.

**Files:**
- Modify: `retention_py/app/routes/{dashboard,categories,records,app_pages,ropa,recalculations,import_records,integrations_routes,platform}.py`
- Test: `retention_py/tests/test_tenancy_route_guards.py`

**Interfaces:**
- Consumes: `tenant_context`, `require`, `Ctx`.

- [ ] **Step 1: Router-level context** — in each authenticated router module change `router = APIRouter()` to `router = APIRouter(dependencies=[Depends(tenant_context)])` (import from `app.core.context`). For `app_pages.py` (which also serves public `/invite/accept` and `/legal`) this is safe because `tenant_context` returns `None` for anonymous requests.

- [ ] **Step 2: Write the failing guard test** (expected matrix — this is the executable form of spec §7.3):

```python
# retention_py/tests/test_tenancy_route_guards.py
import pytest

from app.auth import hash_password
from app.core.clock import utcnow
from app.models import Membership, User

GET_EXPECT = {
    # path: roles allowed (others must get 403)
    "/categories": {"owner", "admin", "privacy_officer", "data_owner", "contributor", "auditor", "viewer"},
    "/categories/create": {"owner", "admin", "privacy_officer"},
    "/ropa": {"owner", "admin", "privacy_officer", "auditor", "viewer"},
    "/ropa/create": {"owner", "admin", "privacy_officer"},
    "/import": {"owner", "admin", "privacy_officer", "data_owner", "contributor"},
    "/audit": {"owner", "admin", "privacy_officer", "auditor"},
    "/reports": {"owner", "admin", "privacy_officer", "auditor", "viewer"},
    "/recalculations": {"owner", "admin", "privacy_officer"},
    "/users": {"owner", "admin"},
    "/settings": {"owner", "admin"},
    "/integrations": {"owner", "admin"},
    "/billing": {"owner"},
    "/attachments": {"owner", "admin", "privacy_officer", "auditor"},
}
ROLES = ["owner", "admin", "privacy_officer", "data_owner", "contributor", "auditor", "viewer"]


@pytest.mark.parametrize("role", ROLES)
def test_get_guards(client, db, login_as, role):
    u = User(organization_id=1, name=role, email=f"{role}@test.local", role="admin",
             password_hash=hash_password("Xyq9$mNpL2!k"), is_active=True, email_verified_at=utcnow())
    db.add(u); db.commit()
    db.add(Membership(user_id=u.id, organization_id=1, scope_type="group", scope_id=1, role=role)); db.commit()
    login_as(client, u)
    for path, allowed in GET_EXPECT.items():
        status = client.get(path, follow_redirects=False).status_code
        if role in allowed:
            assert status == 200, f"{role} should reach {path}, got {status}"
        else:
            assert status == 403, f"{role} must be denied {path}, got {status}"


@pytest.mark.parametrize("path,data", [
    ("/categories/create", {"name": "X"}),
    ("/ropa/create", {"activity_name": "X"}),
])
def test_data_owner_cannot_post_governance_changes(client, db, login_as, path, data):
    u = User(organization_id=1, name="do", email="do@test.local", role="data_owner",
             password_hash=hash_password("Xyq9$mNpL2!k"), is_active=True, email_verified_at=utcnow())
    db.add(u); db.commit()
    db.add(Membership(user_id=u.id, organization_id=1, scope_type="group", scope_id=1, role="data_owner")); db.commit()
    login_as(client, u)
    assert client.post(path, data=data, follow_redirects=False).status_code == 403


def test_role_change_takes_effect_immediately(client, db, login_as, make_user):
    u = make_user("owner")
    login_as(client, u)
    assert client.get("/users", follow_redirects=False).status_code == 200
    m = db.query(Membership).filter_by(user_id=u.id).one()
    m.role = "viewer"; db.commit()
    assert client.get("/users", follow_redirects=False).status_code == 403


def test_anonymous_redirected_to_login(client):
    r = client.get("/categories/create", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")
```

- [ ] **Step 3: Run to verify failure** — FAIL (data_owner reaches `/categories/create`, etc.).

- [ ] **Step 4: Apply guards** — for each route add `ctx: Ctx = Depends(require("<permission>"))` as a parameter (keep existing `session = get_session(request)` lines for now; they still provide `user_name` etc. to templates) and **delete** the inline `if session["role"] ...` / `if ... not in ("admin","dpo")` checks the guard replaces. Mapping (route → permission):

| Route(s) | Permission |
|---|---|
| `GET /dashboard`, `GET /help`, `GET/POST /notifications*`, `GET/POST /profile*` | `dashboard.view` (notifications/profile: `notifications.view`) |
| `GET /categories`, `GET /categories/view/{id}`, `GET /categories/export` | `categories.view` |
| `GET/POST /categories/create`, `GET/POST /categories/edit/{id}`, `POST /categories/delete/{id}` | `categories.manage` |
| `GET /records`, `GET /records/view/{id}` | `records.view` |
| `POST /records/create` | `records.create` |
| `GET/POST /records/edit/{id}` | `records.edit` |
| `POST /records/reassign/{id}` | `records.reassign` |
| `POST /records/dispose/{id}`, `POST /records/bulk_dispose`, `POST /records/approve/{id}` | `records.dispose.request` (approve path inside engine still enforces dual approval) |
| `POST /records/disposal_approve/{id}`, `POST /records/disposal_reject/{id}` | `records.dispose.approve` |
| `POST /records/legal_hold/{id}` | `records.legal_hold` |
| `GET /records/export` | `records.export` |
| `GET /attachments`, `GET /attachments/download/{id}` | `attachments.view` |
| `POST /attachments/upload/{record_id}` | `attachments.upload` |
| `GET/POST /import`, `GET /import/sample` | `records.import` |
| `GET /recalculations`, `POST /recalculations/{id}/action` | `recalculations.manage` |
| `GET /ropa`, `GET /ropa/{entry_id}`, `GET /ropa/export/csv` | `ropa.view` |
| `GET/POST /ropa/create`, `GET/POST /ropa/{entry_id}/edit`, `POST /ropa/{entry_id}/processors/*` | `ropa.manage` |
| `GET /reports*` | `reports.view` |
| `GET /audit`, `GET /audit/export` | `audit.view` |
| `GET /users`, `POST /users/*` | `users.manage` |
| `GET /settings`, `POST /settings/save` | `settings.manage` (2FA tab of settings: any signed-in user — split the twofa branch into `/profile/2fa` guarded by `dashboard.view`) |
| `GET /integrations*`, `POST /integrations/*` | `integrations.manage` |
| `GET /billing`, `POST /billing/*` | `billing.manage` |
| `/platform*` | platform guard from Task 9 (not a tenant permission) |

- [ ] **Step 5: Own-records filtering via ctx** — in `records.py` `list_records`, replace `is_owner = (session.get("role") == "data_owner")` with `is_owner = ctx.only_own_records()`; same pattern in `handle_create_record` (`role == "data_owner"` → `ctx.only_own_records()`) and anywhere else `session.get("role") == "data_owner"` gates data (grep `"data_owner"` in `app/routes`).

- [ ] **Step 6: Remove the Task 4 xfail marker** on `test_entity_scope_hides_sibling_entity_records`.

- [ ] **Step 7: Run tests** — `python -m pytest tests/test_tenancy_route_guards.py tests/test_tenancy_isolation.py -v` → PASS. Re-run Phase 0's `tests/audit/test_access_matrix.py` and commit the regenerated matrix. Full suite green — existing tests that created users with `role="dpo"` but no membership must add a membership (helper: add a `make_user(db, role, scope=...)` fixture in conftest and use it).

- [ ] **Step 8: Commit**

```bash
git add retention_py/app/routes retention_py/tests docs/audit/evidence/access-matrix.md
git commit -m "fix(security): permission guard on every route; data owners can no longer change retention rules, RoPA or settings"
```

---

### Task 6: Set entity (and unit) on every creation path

**Files:**
- Modify: `retention_py/app/routes/categories.py` (create), `records.py` (create), `ropa.py` (create), `import_records.py`, `api_v1.py` (`/ingest`, `/ingest/batch`), `app/enterprise.py` (`process_intake_item`), `app/helpers.py` (`provision_org_categories`, `clone_category_retention_rules`)
- Test: `retention_py/tests/test_tenancy_create_paths.py`

**Interfaces:**
- Rule: records inherit `entity_id` from their category; categories and RoPA entries take `ctx.default_entity_id` unless the form posts an `entity_id` the user `can("categories.manage", entity_id=…)`; provisioning takes an explicit `entity_id`. `unit_id` on records: form field `unit_id` (optional) validated against `ctx.unit_ids`/entity units; a unit-scoped user's records default to their single unit.
- Signature change: `provision_org_categories(db, org_id: int, country_code: str, entity_id: int)`.

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_tenancy_create_paths.py
from app.auth import hash_password
from app.core.clock import utcnow
from app.helpers import provision_org_categories
from app.models import DataCategory, DataRecord, Membership, RopaEntry, Unit, User


def _owner(db):
    u = User(organization_id=1, name="o", email="o@test.local", role="admin",
             password_hash=hash_password("Xyq9$mNpL2!k"), is_active=True, email_verified_at=utcnow())
    db.add(u); db.commit()
    db.add(Membership(user_id=u.id, organization_id=1, scope_type="group", scope_id=1, role="owner")); db.commit()
    return u


def test_category_create_sets_default_entity(client, db, login_as, entity_id):
    login_as(client, _owner(db))
    client.post("/categories/create", data={"name": "Payroll"})
    assert db.query(DataCategory).filter_by(name="Payroll").one().entity_id == entity_id


def test_record_inherits_category_entity_and_unit(client, db, login_as, entity_id):
    login_as(client, _owner(db))
    unit = Unit(organization_id=1, entity_id=entity_id, name="HR"); db.add(unit); db.commit()
    cat = DataCategory(organization_id=1, entity_id=entity_id, name="C", retention_period_days=30)
    db.add(cat); db.commit()
    client.post("/records/create", data={"record_reference": "R-1", "category_id": cat.id,
                                         "collection_date": "2026-01-01", "unit_id": unit.id})
    rec = db.query(DataRecord).filter_by(record_reference="R-1").one()
    assert rec.entity_id == entity_id and rec.unit_id == unit.id


def test_ropa_create_sets_entity(client, db, login_as, entity_id):
    login_as(client, _owner(db))
    client.post("/ropa/create", data={"activity_name": "Payroll processing"})
    assert db.query(RopaEntry).one().entity_id == entity_id


def test_provisioning_requires_entity(db, entity_id):
    provision_org_categories(db, 1, "NG", entity_id)
    assert db.query(DataCategory).count() > 0
    assert {c.entity_id for c in db.query(DataCategory)} == {entity_id}
```
Plus an API-ingest test: create a `ConnectedSystem` + API key via `app.enterprise.create_api_key`, POST `/api/v1/ingest` with a category id, assert the created record's `entity_id` equals the category's.

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Implement each path** —
  - `categories.handle_create_category`: add `entity_id: int = Form(0)`; `eid = entity_id if entity_id and ctx.can("categories.manage", entity_id=entity_id) else ctx.default_entity_id`; pass `entity_id=eid` to `DataCategory(...)`.
  - `records.handle_create_record`: add `unit_id: int = Form(0)`; after loading `cat`: `entity = cat.entity_id`; `unit = unit_id or (next(iter(ctx.unit_ids)) if len(ctx.unit_ids) == 1 else None)`; if `unit` is set and `not ctx.can("records.create", entity_id=entity, unit_id=unit)` → 403; verify the unit belongs to `entity` (`db.get(Unit, unit).entity_id == entity`) else 400; pass `entity_id=entity, unit_id=unit`.
  - `ropa` create: same rule as categories (`ropa.manage`).
  - `import_records`: each row's record takes `entity_id=cat.entity_id` of its resolved category.
  - `api_v1` `/ingest` and `/ingest/batch`, `enterprise.process_intake_item`: `entity_id=category.entity_id`.
  - `helpers.provision_org_categories(db, org_id, country_code, entity_id)`: set `entity_id` on each created `DataCategory`; `clone_category_retention_rules` unchanged (rules hang off categories). Update callers (registration — rewritten in Task 7).

- [ ] **Step 4: Remove every Task 2 strict-xfail marker**; run the full suite → green.

- [ ] **Step 5: Commit**

```bash
git add retention_py/app retention_py/tests
git commit -m "feat(tenancy): entity and unit assignment on every creation path"
```

---

### Task 7: Registration, verified domains and enforced email verification

Fixes F4 / SD-04-003; implements spec §5.2 domain rules.

**Files:**
- Create: `retention_py/app/domain/org/domains.py`, `retention_py/app/domain/org/memberships.py`
- Modify: `retention_py/app/routes/public.py` (`handle_register`), `retention_py/app/routes/app_pages.py` (domain pages), templates `register.html` (copy), new `domains.html`
- Modify: `retention_py/requirements.txt` (+ `dnspython==2.7.0`)
- Test: `retention_py/tests/test_tenancy_domains.py`

**Interfaces:**
- Produces (`domains.py`): `claim(db, org_id: int, entity_id: int, domain: str) -> tuple[EntityDomain, str]` (returns row + raw token; token stored hashed), `dns_txt_value(raw_token: str) -> str` (`"safedata-verify=" + raw_token`), `verify_dns(db, domain_row: EntityDomain, resolver=None) -> bool`, `send_email_challenge(db, domain_row, local_part: str) -> str` (local_part ∈ `admin`, `postmaster`, `hostmaster`, `webmaster`), `verify_email_token(db, raw_token: str) -> EntityDomain | None`, `_mark_verified(db, row, method) -> None` (releases competing pending claims, notifies their org admins), `normalise(domain: str) -> str`.
- Produces (`memberships.py`): `grant(db, user_id, org_id, role, scope_type="group", scope_id=None, expires_at=None, by=None) -> Membership`.

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_tenancy_domains.py
from app.domain.org import domains
from app.domain.org.structure import create_default_entity
from app.models import EntityDomain, Membership, Organization, User


class FakeResolver:
    def __init__(self, records):
        self.records = records

    def resolve(self, name, rtype):
        assert rtype == "TXT"
        return [type("R", (), {"strings": [r.encode()]})() for r in self.records.get(name, [])]


def test_normalise():
    assert domains.normalise(" HTTPS://www.Acme.co.uk/ ") == "acme.co.uk"


def test_dns_verification(db, entity_id):
    row, token = domains.claim(db, 1, entity_id, "acme.ng")
    assert row.status == "pending" and row.token_hash and token not in (row.token_hash or "")
    ok = domains.verify_dns(db, row, resolver=FakeResolver({"acme.ng": [domains.dns_txt_value(token)]}))
    assert ok and row.status == "verified" and row.method == "dns"


def test_dns_verification_wrong_value(db, entity_id):
    row, _ = domains.claim(db, 1, entity_id, "acme.ng")
    assert not domains.verify_dns(db, row, resolver=FakeResolver({"acme.ng": ["safedata-verify=nope"]}))
    assert row.status == "pending"


def test_verification_releases_competing_claims(db, entity_id):
    o2 = Organization(name="O2", slug="o2", primary_domain="o2.test", country="GB", tier="core", status="active")
    db.add(o2); db.commit()
    e2 = create_default_entity(db, o2)
    mine, t1 = domains.claim(db, 1, entity_id, "contested.com")
    theirs, _ = domains.claim(db, o2.id, e2.id, "contested.com")
    domains.verify_dns(db, mine, resolver=FakeResolver({"contested.com": [domains.dns_txt_value(t1)]}))
    db.expire_all()
    assert db.get(EntityDomain, theirs.id) is None


def test_register_does_not_auto_verify_email(client, db):
    r = client.post("/register", data={
        "org_name": "Acme", "domain": "acme-new.ng", "user_name": "Ada", "email": "ada@acme-new.ng",
        "password": "Xyq9$mNpL2!k", "password_confirm": "Xyq9$mNpL2!k", "country": "NG"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/verify_email"
    u = db.query(User).filter_by(email="ada@acme-new.ng").one()
    assert u.email_verified_at is None
    m = db.query(Membership).filter_by(user_id=u.id).one()
    assert (m.role, m.scope_type) == ("owner", "group")
    assert db.query(EntityDomain).filter_by(domain="acme-new.ng").one().status == "pending"


def test_register_blocked_only_by_verified_domain(client, db, entity_id):
    db.add(EntityDomain(organization_id=1, entity_id=entity_id, domain="taken.com", status="verified", method="dns"))
    db.commit()
    r = client.post("/register", data={
        "org_name": "X", "domain": "taken.com", "user_name": "X", "email": "x@taken.com",
        "password": "Xyq9$mNpL2!k", "password_confirm": "Xyq9$mNpL2!k", "country": "GB"})
    assert "already uses SafeData" in r.text
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Implement `domains.py`**

```python
"""Domain claims: pending claims never block anyone; a verified domain belongs to one Group."""
from __future__ import annotations

import hashlib
import re
import secrets

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.models import EntityDomain

EMAIL_LOCAL_PARTS = ("admin", "postmaster", "hostmaster", "webmaster")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalise(domain: str) -> str:
    d = domain.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0]


def dns_txt_value(raw_token: str) -> str:
    return f"safedata-verify={raw_token}"


def claim(db: Session, org_id: int, entity_id: int, domain: str) -> tuple[EntityDomain, str]:
    token = secrets.token_urlsafe(24)
    row = EntityDomain(organization_id=org_id, entity_id=entity_id, domain=normalise(domain),
                       status="pending", token_hash=_hash(token))
    db.add(row)
    db.commit()
    return row, token


def _mark_verified(db: Session, row: EntityDomain, method: str) -> None:
    from app.engine import notify_role
    row.status, row.method, row.verified_at, row.token_hash = "verified", method, utcnow(), None
    losers = db.query(EntityDomain).filter(EntityDomain.domain == row.domain, EntityDomain.id != row.id,
                                           EntityDomain.status == "pending") \
               .execution_options(skip_tenant_filter=True).all()
    for other in losers:
        notify_role(db, other.organization_id, ["admin"], "domain_claim_released",
                    f"Domain {other.domain} was verified by another organisation",
                    f"Your pending claim on {other.domain} was released because another organisation proved "
                    "ownership. Contact support@safedata.3consult-ng.com if this is wrong.")
        db.delete(other)
    db.commit()


def verify_dns(db: Session, row: EntityDomain, resolver=None) -> bool:
    if row.status == "verified" or not row.token_hash:
        return row.status == "verified"
    if resolver is None:
        import dns.resolver
        resolver = dns.resolver.Resolver()
    try:
        answers = resolver.resolve(row.domain, "TXT")
    except Exception:
        return False
    for ans in answers:
        for s in getattr(ans, "strings", []):
            value = s.decode() if isinstance(s, bytes) else str(s)
            if value.startswith("safedata-verify=") and _hash(value.split("=", 1)[1]) == row.token_hash:
                _mark_verified(db, row, "dns")
                return True
    return False


def send_email_challenge(db: Session, row: EntityDomain, local_part: str) -> str:
    from app.config import APP_URL
    from app.helpers import email_layout, send_system_email
    if local_part not in EMAIL_LOCAL_PARTS:
        raise ValueError("unsupported mailbox")
    token = secrets.token_urlsafe(24)
    row.token_hash = _hash(token)
    db.commit()
    link = f"{APP_URL}/domains/verify?token={token}"
    send_system_email(db, f"{local_part}@{row.domain}", f"Confirm {row.domain} for SafeData",
                      email_layout("Confirm domain ownership",
                                   f"<p>Someone asked to link <strong>{row.domain}</strong> to an organisation on "
                                   f"SafeData by 3Consulting.</p><p><a href=\"{link}\">Confirm this domain</a></p>"
                                   "<p>If you did not expect this, ignore this email.</p>"))
    return token


def verify_email_token(db: Session, raw_token: str) -> EntityDomain | None:
    row = db.query(EntityDomain).filter(EntityDomain.token_hash == _hash(raw_token),
                                        EntityDomain.status == "pending") \
            .execution_options(skip_tenant_filter=True).first()
    if row:
        _mark_verified(db, row, "email")
    return row
```

- [ ] **Step 4: Implement `memberships.py`**

```python
from sqlalchemy.orm import Session

from app.models import Membership


def grant(db: Session, user_id: int, org_id: int, role: str, scope_type: str = "group",
          scope_id: int | None = None, expires_at=None, by: int | None = None) -> Membership:
    m = Membership(user_id=user_id, organization_id=org_id, role=role, scope_type=scope_type,
                   scope_id=org_id if scope_type == "group" and scope_id is None else scope_id,
                   expires_at=expires_at, created_by=by)
    db.add(m)
    db.commit()
    return m
```

- [ ] **Step 5: Rewrite `handle_register`** (keep validation messages and form re-fill):
  - Domain uniqueness: replace the `Organization.primary_domain == domain` check with a check on `EntityDomain(domain=normalise(domain), status="verified")` (use `execution_options(skip_tenant_filter=True)`). Message: `"An organisation using {domain} already uses SafeData. Ask your SafeData administrator to invite you."`. Keep the email-must-match-domain rule.
  - `Organization.primary_domain` is unique in the schema, which would let an unverified squatter block the real owner. Make it non-unique: model `primary_domain = Column(String(255), nullable=False, index=True)` and a new migration `0004_org_domain_nonunique.py` (autogenerate, then review: a batch `drop_constraint`/unique-index drop on `organizations.primary_domain` plus `create_index("ix_organizations_primary_domain", ...)`). Ownership is decided by `entity_domains` verification only.
  - Create org (trial 14 days), then `ent = create_default_entity(db, org)`, `provision_org_categories(db, org.id, country, ent.id)`, create the user **without** `email_verified_at`, `grant(db, user.id, org.id, "owner")`, `issue_email_verification_token` + send via existing `email_verification(...)` helper, redirect to `/verify_email` with a session.
  - Keep the welcome email but send it **after** verification (move into the `/verify_email` success branch).

- [ ] **Step 6: Domain management pages** (`app_pages.py`, guarded by `domains.manage`): `GET /domains` (list rows for the group with status and instructions: TXT record name/value, or "send email to admin@/postmaster@…"), `POST /domains/claim` (`entity_id`, `domain`), `POST /domains/{id}/verify-dns`, `POST /domains/{id}/send-email` (`local_part`), public `GET /domains/verify?token=` (add `/domains/verify` to `PUBLIC_PATHS`). The raw DNS token is shown once after claim (flash) and can be regenerated (new `claim` replaces token_hash). Minimal Bootstrap template `domains.html` consistent with existing pages (Phase 2 restyles).

- [ ] **Step 7: Run tests** — `pip install dnspython==2.7.0; python -m pytest tests/test_tenancy_domains.py -v` → PASS; full suite green (update `test_onboarding.py` expectations: registration now lands on `/verify_email`).

- [ ] **Step 8: Commit**

```bash
git add retention_py/app retention_py/alembic retention_py/requirements.txt retention_py/tests
git commit -m "feat(tenancy): verified domains (DNS/email), registration creates owner membership, email verification enforced"
```

---

### Task 8: Users and invitations with scoped roles

**Files:**
- Modify: `retention_py/app/models.py` (`OrganizationInvitation`: role enum → 7 roles; add `scope_type`, `scope_id`, `access_expires_at`), migration `0005_invitation_scopes.py` (autogenerate + review), `retention_py/app/routes/app_pages.py` (`/users*`, `/invite/accept`), `users.html`, `invite_accept.html`
- Test: `retention_py/tests/test_tenancy_users.py`

**Interfaces:**
- `POST /users/invite` form: `email`, `name`, `role`, `scope_type`, `scope_id`, `access_days` (auditor only, 1–90).
- `POST /users/{uid}/memberships` (add role at scope), `POST /users/{uid}/memberships/{mid}/delete`.
- `/users/create` (admin sets a password) is **removed** — invitations only (no admin-known passwords).

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_tenancy_users.py
import hashlib
from datetime import timedelta

from app.auth import hash_password
from app.core.clock import utcnow
from app.models import Membership, OrganizationInvitation, User


def _owner(db):
    u = User(organization_id=1, name="o", email="o@test.local", role="admin",
             password_hash=hash_password("Xyq9$mNpL2!k"), is_active=True, email_verified_at=utcnow())
    db.add(u); db.commit()
    db.add(Membership(user_id=u.id, organization_id=1, scope_type="group", scope_id=1, role="owner")); db.commit()
    return u


def _invite(db, role="auditor", scope_type="entity", scope_id=1, token="tok"):
    inv = OrganizationInvitation(organization_id=1, email="new@ext.com", name="New", role=role,
                                 scope_type=scope_type, scope_id=scope_id,
                                 access_expires_at=utcnow() + timedelta(days=30) if role == "auditor" else None,
                                 token_hash=hashlib.sha256(token.encode()).hexdigest(),
                                 expires_at=utcnow() + timedelta(days=7))
    db.add(inv); db.commit()
    return inv


def test_users_create_route_removed(client, db, login_as):
    login_as(client, _owner(db))
    assert client.post("/users/create", data={"name": "x", "email": "x@test.local", "password": "p"}).status_code in (404, 405)


def test_accept_enforces_password_policy(client, db, entity_id):
    _invite(db, scope_id=entity_id)
    r = client.post("/invite/accept", data={"token": "tok", "password": "weak", "password_confirm": "weak"},
                    follow_redirects=False)
    assert "error" in r.headers["location"]
    assert db.query(User).filter_by(email="new@ext.com").first() is None


def test_accept_creates_scoped_time_limited_membership(client, db, entity_id):
    _invite(db, scope_id=entity_id)
    client.post("/invite/accept", data={"token": "tok", "password": "Xyq9$mNpL2!k",
                                        "password_confirm": "Xyq9$mNpL2!k"})
    u = db.query(User).filter_by(email="new@ext.com").one()
    m = db.query(Membership).filter_by(user_id=u.id).one()
    assert (m.role, m.scope_type, m.scope_id) == ("auditor", "entity", entity_id)
    assert m.expires_at is not None
    assert u.email_verified_at is not None  # accepting the emailed link proves the mailbox


def test_existing_user_accepting_invite_gets_second_group(client, db, entity_id):
    from app.models import Organization
    existing = User(organization_id=1, name="Consultant", email="new@ext.com", role="data_owner",
                    password_hash=hash_password("Xyq9$mNpL2!k"), is_active=True, email_verified_at=utcnow())
    db.add(existing); db.commit()
    _invite(db, role="privacy_officer", scope_type="group", scope_id=1)
    r = client.post("/invite/accept", data={"token": "tok", "password": "Xyq9$mNpL2!k",
                                            "password_confirm": "Xyq9$mNpL2!k"}, follow_redirects=False)
    assert r.status_code == 303
    assert db.query(Membership).filter_by(user_id=existing.id, role="privacy_officer").count() == 1
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Implement** —
  - Model + migration for invitation scope columns (`scope_type` default `'group'`, `scope_id` nullable → group id, `access_expires_at`); role enum to the 7 roles.
  - `invite_user`: validate `role in ROLES`; validate scope belongs to the group (entity/unit with `organization_id == ctx.org_id`); auditor requires `access_days` 1–90 → `access_expires_at`; **allow** inviting an email that already exists (consultants/auditors) — do not error with `email_exists` unless that user already has a membership in this group.
  - `handle_accept_invite`: run `password_policy_error(password, invite.email, invite.name)`; on error redirect with `error=password`. If a user with that email exists: verify the posted password with `verify_password` (the existing account's password) instead of creating a user; else create the user with `email_verified_at=utcnow()`. Then `grant(...)` with the invite's role/scope and `expires_at=invite.access_expires_at`. Mark invite accepted. Audit log `invite_accepted`.
  - Delete `create_user` (`/users/create`) and its form in `users.html`.
  - `users.html`: list members with their role@scope chips; add-role and remove-role forms (guarded `users.manage`); prevent removing the last `owner` (return error "A group must keep at least one Owner").
  - `toggle_user` (`/users/{uid}/toggle`): on deactivate call `revoke_all(db, uid)`.

- [ ] **Step 4: Run tests** → PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add retention_py/app retention_py/alembic retention_py/tests
git commit -m "feat(users): invitations with scoped and time-limited roles; password policy on accept; no admin-set passwords"
```

---

### Task 9: Platform Owner bootstrap, remove the setup wizard, platform guard

Fixes SD-04-006 (first-visitor setup takeover).

**Files:**
- Modify: `retention_py/app/cli.py` (`create-platform-owner`, `grant-platform-role`, `set-billing-mode`)
- Modify: `retention_py/app/routes/public.py` (delete `/setup` routes), `retention_py/app/templates/setup.html` (delete), `retention_py/app/middleware.py` (remove `/setup` from `PUBLIC_PATHS`, delete setup guard), `retention_py/app/auth.py` (delete `setup_is_complete`), `retention_py/app/routes/platform.py` (platform guard), `retention_py/tests/test_setup.py` (replace)
- Create: `retention_py/app/core/platform.py`
- Test: `retention_py/tests/test_tenancy_platform.py`

**Interfaces:**
- Produces: `create_platform_owner(db, email: str, name: str, password: str, org_name: str = "3Consulting") -> User` (internal Group `billing_mode="internal"`, user `platform_role="platform_owner"`, Owner membership), CLI prompts with `getpass` (twice, policy-checked); `require_platform(*roles)` dependency: requires `platform_role in roles`, email domain `@3consult-ng.com`, and `twofa_enabled` (else redirect `/settings?tab=twofa` → after Task 5 `/profile/2fa`).
- `PLATFORM_EMAIL_DOMAIN = "3consult-ng.com"` in config.

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_tenancy_platform.py
import pytest

from app.core.platform import create_platform_owner
from app.models import Membership, Organization, User


def test_setup_routes_removed(client):
    assert client.get("/setup", follow_redirects=False).status_code == 404


def test_fresh_database_serves_login_not_setup(client):
    r = client.get("/dashboard", follow_redirects=False)
    assert r.headers["location"].startswith("/login")


def test_create_platform_owner(db):
    u = create_platform_owner(db, "owner@3consult-ng.com", "Platform Owner", "Xyq9$mNpL2!k")
    org = db.get(Organization, u.organization_id)
    assert u.platform_role == "platform_owner" and org.billing_mode == "internal"
    assert db.query(Membership).filter_by(user_id=u.id, role="owner").count() == 1


def test_platform_owner_requires_company_domain(db):
    with pytest.raises(ValueError):
        create_platform_owner(db, "boss@gmail.com", "X", "Xyq9$mNpL2!k")


def test_platform_pages_require_2fa(client, db, login_as):
    u = create_platform_owner(db, "owner@3consult-ng.com", "Platform Owner", "Xyq9$mNpL2!k")
    u.email_verified_at = u.created_at; db.commit()
    login_as(client, u, org_id=u.organization_id)
    r = client.get("/platform", follow_redirects=False)
    assert r.status_code == 303 and "2fa" in r.headers["location"]


def test_tenant_admin_cannot_reach_platform(client, db, login_as):
    from app.auth import hash_password
    from app.core.clock import utcnow
    t = User(organization_id=1, name="t", email="t@test.local", role="admin", password_hash=hash_password("Xyq9$mNpL2!k"),
             is_active=True, email_verified_at=utcnow())
    db.add(t); db.commit()
    db.add(Membership(user_id=t.id, organization_id=1, scope_type="group", scope_id=1, role="owner")); db.commit()
    login_as(client, t)
    assert client.get("/platform", follow_redirects=False).status_code == 403
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Implement `app/core/platform.py`**

```python
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import get_session, hash_password, password_policy_error
from app.config import PLATFORM_EMAIL_DOMAIN
from app.core.clock import utcnow
from app.database import get_db
from app.domain.org.memberships import grant
from app.domain.org.structure import create_default_entity
from app.models import Organization, User


def create_platform_owner(db: Session, email: str, name: str, password: str,
                          org_name: str = "3Consulting") -> User:
    email = email.strip().lower()
    if not email.endswith("@" + PLATFORM_EMAIL_DOMAIN):
        raise ValueError(f"Platform roles require an @{PLATFORM_EMAIL_DOMAIN} email")
    err = password_policy_error(password, email, name)
    if err:
        raise ValueError(err)
    if db.query(User).filter(User.platform_role == "platform_owner").first():
        raise ValueError("A Platform Owner already exists; use grant-platform-role for additional admins")
    org = db.query(Organization).filter(Organization.primary_domain == PLATFORM_EMAIL_DOMAIN).first()
    if org is None:
        org = Organization(name=org_name, slug="3consulting", primary_domain=PLATFORM_EMAIL_DOMAIN, country="NG",
                           tier="core", status="active", subscription_status="active", billing_mode="internal")
        db.add(org); db.commit()
        create_default_entity(db, org)
    user = User(organization_id=org.id, name=name, email=email, password_hash=hash_password(password),
                role="admin", is_active=True, email_verified_at=utcnow(), platform_role="platform_owner")
    db.add(user); db.commit()
    grant(db, user.id, org.id, "owner")
    return user


def require_platform(*roles: str):
    allowed = set(roles) or {"platform_owner", "super_admin", "support"}

    def dependency(request: Request, db: Session = Depends(get_db)) -> dict:
        s = get_session(request)
        if not s or "user_id" not in s:
            raise HTTPException(status_code=303, detail="login required")
        if s.get("platform_role") not in allowed or not s.get("email", "").endswith("@" + PLATFORM_EMAIL_DOMAIN):
            raise HTTPException(status_code=403, detail="Platform access only")
        if not s.get("twofa_enabled"):
            raise HTTPException(status_code=307, detail="/profile/2fa?required=1")
        return s
    return dependency
```
Add an exception handler in `main.py` for status 307 that redirects to `exc.detail` with 303 (only for details starting with `/`). Add `PLATFORM_EMAIL_DOMAIN = os.getenv("PLATFORM_EMAIL_DOMAIN", "3consult-ng.com")` to config.

- [ ] **Step 4: CLI commands** in `app/cli.py`:

```python
def cmd_create_platform_owner(args) -> int:
    import getpass
    from app.core.platform import create_platform_owner
    from app.database import SessionLocal
    pw = getpass.getpass("Password: ")
    if pw != getpass.getpass("Repeat password: "):
        log.error("Passwords do not match"); return 1
    db = SessionLocal()
    try:
        u = create_platform_owner(db, args.email, args.name, pw)
        log.info("Platform Owner created: %s (enable 2FA at first sign-in)", u.email)
        return 0
    except ValueError as exc:
        log.error("%s", exc); return 1
    finally:
        db.close()
```
Register `create-platform-owner --email --name`; `grant-platform-role --email --role {super_admin,support}` (user must exist, `@3consult-ng.com`, sets `platform_role`); `set-billing-mode --org-id --mode {standard,internal,complimentary} [--plan] [--ends YYYY-MM-DD] [--reason]` (writes comp fields, logs audit).

- [ ] **Step 5: Delete the setup wizard** — remove `/setup` GET/POST from `public.py`, `setup.html`, `setup_is_complete` from `auth.py`, `/setup` from `PUBLIC_PATHS`, the setup guard block in `SessionEnforcementMiddleware`, and the `SystemSetting(setup_complete)` seed from `conftest.py`. Replace `tests/test_setup.py` content with the two route tests above (or delete it, keeping them in `test_tenancy_platform.py`).

- [ ] **Step 6: Guard `/platform*`** — in `platform.py` replace inline `is_platform_admin` checks with `s: dict = Depends(require_platform())`; platform queries that list all organisations use `.execution_options(skip_tenant_filter=True)` explicitly.

- [ ] **Step 7: Run tests** → PASS; full suite green.

- [ ] **Step 8: Commit**

```bash
git add retention_py/app retention_py/tests
git commit -m "fix(security): remove first-visitor setup wizard; Platform Owner CLI bootstrap; platform pages require company domain + 2FA"
```

---

### Task 10: Enforce past-due, cancelled and billing-exempt states (interim until Phase 3)

Fixes F11 / SD-11-002.

**Files:**
- Modify: `retention_py/app/middleware.py` (subscription block)
- Test: `retention_py/tests/test_tenancy_subscription.py`

**Interfaces:**
- Rules: `billing_mode in {internal, complimentary}` (and comp not expired) → never redirected; `past_due` → allowed with banner flag `request.state.billing_banner = "past_due"`; `cancelled` or expired trial → redirect to `/billing?…` for every path except `/billing`, `/logout`, `/profile*`, `/records/export`, `/audit/export`, `/reports*` (read and export stay available — "never data-hostage").

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_tenancy_subscription.py
from datetime import timedelta

import pytest

from app.auth import hash_password
from app.core.clock import utcnow
from app.models import Membership, Organization, User


@pytest.fixture
def owner(db, login_as, client):
    u = User(organization_id=1, name="o", email="o@test.local", role="admin",
             password_hash=hash_password("Xyq9$mNpL2!k"), is_active=True, email_verified_at=utcnow())
    db.add(u); db.commit()
    db.add(Membership(user_id=u.id, organization_id=1, scope_type="group", scope_id=1, role="owner")); db.commit()
    login_as(client, u)
    return u


def _org(db, **kw):
    o = db.get(Organization, 1)
    for k, v in kw.items():
        setattr(o, k, v)
    db.commit()


def test_cancelled_redirects_but_exports_stay_open(client, db, owner):
    _org(db, subscription_status="cancelled")
    assert client.get("/categories", follow_redirects=False).headers["location"].startswith("/billing")
    assert client.get("/records/export", follow_redirects=False).status_code == 200


def test_past_due_allowed(client, db, owner):
    _org(db, subscription_status="past_due")
    assert client.get("/categories", follow_redirects=False).status_code == 200


def test_internal_never_redirected(client, db, owner):
    _org(db, subscription_status="trial", trial_ends_at=utcnow() - timedelta(days=30), billing_mode="internal")
    assert client.get("/categories", follow_redirects=False).status_code == 200


def test_expired_complimentary_falls_back_to_standard_rules(client, db, owner):
    _org(db, subscription_status="trial", trial_ends_at=utcnow() - timedelta(days=1),
         billing_mode="complimentary", comp_ends_at=utcnow() - timedelta(days=1))
    assert client.get("/categories", follow_redirects=False).headers["location"].startswith("/billing")
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Implement** — replace the "Enforce subscription + trial expiry" block in `SessionEnforcementMiddleware` with:

```python
        READ_EXPORT_OK = ("/billing", "/logout", "/profile", "/records/export", "/audit/export", "/reports")
        read_export_ok = path.startswith(READ_EXPORT_OK)
        if not session.get("is_platform_admin"):
            mode = session.get("billing_mode", "standard")
            comp_live = False
            if mode == "complimentary":
                from app.database import SessionLocal
                from app.models import Organization
                _db = SessionLocal()
                try:
                    o = _db.get(Organization, session["org_id"])
                    comp_live = o is not None and (o.comp_ends_at is None or o.comp_ends_at > utcnow())
                finally:
                    _db.close()
            exempt = mode == "internal" or comp_live
            sub = session.get("subscription_status", "trial")
            blocked_reason = None
            if session.get("org_status") == "suspended":
                blocked_reason = "suspended=1"
            elif not exempt and sub == "cancelled":
                blocked_reason = "cancelled=1"
            elif not exempt and sub == "trial" and session.get("trial_ends_at") \
                    and utcnow() > datetime.fromisoformat(session["trial_ends_at"]):
                blocked_reason = "trial_expired=1"
            if sub == "past_due" and not exempt:
                request.state.billing_banner = "past_due"
            if blocked_reason and not read_export_ok:
                response = RedirectResponse(url=f"/billing?{blocked_reason}", status_code=303)
                set_session(response, session, request)
                return response
```
(import `utcnow` from `app.core.clock` and `datetime` at the top of the module.) Show the past-due banner in `layout.html` when `request.state.billing_banner == "past_due"` ("Payment failed — update your billing details within 7 days to avoid read-only mode").

- [ ] **Step 4: Run tests** → PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add retention_py/app retention_py/tests
git commit -m "fix(billing): enforce cancelled/past-due states; internal and complimentary orgs exempt; exports never blocked"
```
