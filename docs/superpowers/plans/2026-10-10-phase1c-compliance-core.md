# Phase 1C — Compliance Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SafeData's compliance evidence trustworthy and its legal clocks correct: jurisdiction rules as cited data with correct deadline arithmetic, a per-organisation tamper-evident audit chain that is fully verified and race-free, separate data-encryption keys, clean time and error handling, translation scaffolding, and a hardened disposal-safety regression net.

**Architecture:** `app/content/jurisdictions/*.toml` (stdlib `tomllib`, no new parser dependency) loaded by `app/domain/rules/` with validation; `app/domain/rules/clock.py` does statutory date arithmetic in the entity's timezone. The audit log gains `chain_version` and an `audit_chain_heads` table so each organisation has its own chain, appended under a row lock and verified in full by streaming. `app/core/crypto.py` wraps `MultiFernet` keyed by `DATA_ENCRYPTION_KEY(S)`. Babel provides gettext + locale formatting.

**Tech Stack:** Python 3.12 `tomllib`, `zoneinfo`, SQLAlchemy 2.0 (`with_for_update`, `yield_per`), cryptography `MultiFernet`, Babel 2.17, pytest.

**Spec:** `docs/superpowers/specs/2026-10-10-safedata-launch-programme-design.md` (§5.3, §5.5, §5.7, §7.6, §16 R2/R7; findings F13, F15, SD-02-003, SD-04-005)

## Global Constraints

- Depends on Phase 1A and 1B merged.
- Storage convention (refines spec §5.3): database `DateTime` columns store **naive UTC** (portable across SQLite and PostgreSQL); application code obtains now from `app.core.clock.utcnow()`; conversion to an entity's local time happens only in `app/domain/rules/clock.py` and presentation helpers. Statutory deadlines are computed on the entity's **local calendar date**.
- Every statutory value in a rules file carries a `citation` (statute + article/section) and `source_url` (official regulator or legislation site). Values come from the Phase 0 Task 6 verified table (`docs/audit/evidence/jurisdiction-review.md`); no value may be entered without that evidence.
- Audit hash payload format for chain version 2 is fixed by this plan and documented in `docs/adr/0002-audit-chain-v2.md`; never change it without a new version number.
- Disposal safety (B5): records requiring dual approval are **never** auto-disposed by any engine path, any worker job, any API call, for any organisation, entity or unit.
- No new swallowed exceptions; every remaining broad `except` logs and carries a `# fail-open:` or `# fail-closed:` comment stating why.

## Review Focus

1. **DSAR received on 31 January under a "1 month" law** — expect due date 28 February (29 in leap years), not 3 March (Task 1 test `test_add_months_clamps_month_end`).
2. **Two audit events for the same org written concurrently** — expect a single unbroken chain; verification passes (Task 2 test `test_concurrent_appends_do_not_fork`).
3. **Tampering with a row older than the 5,000 most recent** — expect verification reports it (Task 2 test `test_tamper_beyond_5000_detected`).
4. **`DATA_ENCRYPTION_KEY` rotated** — expect existing 2FA secrets still decrypt via the old key in `DATA_ENCRYPTION_KEYS`, and `cli reencrypt-secrets` moves them to the new key (Task 3 test).
5. **Category with dual approval whose records are long expired, in a unit-scoped entity** — expect the worker retention job flags for review and never disposes (Task 6 test `test_worker_never_disposes_dual_approval_records`).

---

## File Structure

```
retention_py/app/content/jurisdictions/{GDPR,UK_GDPR,NDPA,CCPA,LGPD,POPIA,DPA_KE,DPA_GH,PDPA_SG,DPDP,PDPL,PIPEDA,APPs,EGDPL}.toml
retention_py/app/domain/rules/__init__.py
retention_py/app/domain/rules/loader.py   # load/validate rules; rules_for(code); rules_for_country(cc)
retention_py/app/domain/rules/clock.py    # add_months, statutory_deadline, local_date
retention_py/app/domain/audit.py          # append_event (v2 chain), verify_org_chain
retention_py/app/helpers.py               # log_audit delegates to domain.audit
retention_py/app/engine.py                # verify_audit_chain delegates; dsar/breach helpers use rules
retention_py/app/core/crypto.py           # encrypt/decrypt with MultiFernet
retention_py/app/core/i18n.py             # Babel setup, gettext for Jinja, format helpers
retention_py/babel.cfg, retention_py/app/locale/en/LC_MESSAGES/messages.po
retention_py/alembic/versions/0006_audit_chain_v2.py
docs/adr/0001-record-architecture-decisions.md, docs/adr/0002-audit-chain-v2.md
retention_py/tests/test_core_*.py
```

---

### Task 1: Jurisdiction rules as cited data, and statutory date arithmetic

Fixes F13 / SD-02-002. Depends on Phase 0 Task 6 (verified values).

**Files:**
- Create: `retention_py/app/content/jurisdictions/*.toml` (14 files), `retention_py/app/domain/rules/{__init__,loader,clock}.py`
- Modify: `retention_py/app/helpers.py` (`get_country_regulation_labels` reads rules)
- Test: `retention_py/tests/test_core_rules.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Period(amount: int, unit: Literal["days", "business_days", "months", "hours"])`
  - `@dataclass(frozen=True) JurisdictionRules(code, name, authority, authority_url, report_label, dsar_deadline: Period | None, dsar_extension: Period | None, breach_authority_deadline: Period | None, breach_standard: str, child_consent_age: int | None, lawful_bases: tuple[str, ...], citations: dict[str, dict[str, str]])`
  - `load_all() -> dict[str, JurisdictionRules]` (cached; raises `RulesError` on invalid files)
  - `rules_for(code: str) -> JurisdictionRules`; `rules_for_country(country_code: str) -> list[JurisdictionRules]` (via existing `COUNTRY_REGULATION_MAP`)
  - `add_months(d: date, n: int) -> date`; `add_business_days(d: date, n: int) -> date` (Mon–Fri); `statutory_deadline(start_utc: datetime, period: Period, tz: str) -> datetime` (returns naive UTC; for day/month units the deadline is 23:59:59 local on the computed local date; for hours it is start + hours)

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_core_rules.py
from datetime import date, datetime

import pytest

from app.domain.rules.clock import add_business_days, add_months, statutory_deadline
from app.domain.rules.loader import Period, RulesError, load_all, rules_for, rules_for_country
from app.helpers import COUNTRY_REGULATION_MAP


def test_add_months_clamps_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert add_months(date(2026, 3, 15), 2) == date(2026, 5, 15)


def test_add_business_days_skips_weekends():
    assert add_business_days(date(2026, 10, 9), 3) == date(2026, 10, 14)  # Fri + 3 → Wed


def test_hours_deadline_is_exact():
    start = datetime(2026, 10, 10, 9, 30)
    assert statutory_deadline(start, Period(72, "hours"), "Africa/Lagos") == datetime(2026, 10, 13, 9, 30)


def test_month_deadline_ends_local_day():
    # 31 Jan 23:30 UTC is 1 Feb 00:30 in Lagos (UTC+1) → 1 month later local = 1 Mar, end of day local
    start = datetime(2026, 1, 31, 23, 30)
    assert statutory_deadline(start, Period(1, "months"), "Africa/Lagos") == datetime(2026, 3, 1, 22, 59, 59)


def test_every_mapped_law_has_a_rules_file():
    codes = {c for laws in COUNTRY_REGULATION_MAP.values() for c in laws}
    assert codes <= set(load_all())


def test_every_value_is_cited():
    for code, r in load_all().items():
        for key in ("dsar_deadline", "breach_authority_deadline", "child_consent_age"):
            if getattr(r, key) is not None:
                cit = r.citations.get(key, {})
                assert cit.get("citation") and cit.get("source_url", "").startswith("https://"), (code, key)


def test_gdpr_values():
    g = rules_for("GDPR")
    assert g.dsar_deadline == Period(1, "months") and g.dsar_extension == Period(2, "months")
    assert g.breach_authority_deadline == Period(72, "hours")


def test_country_lookup():
    assert [r.code for r in rules_for_country("FR")] == ["GDPR"]


def test_invalid_file_rejected(tmp_path, monkeypatch):
    (tmp_path / "BAD.toml").write_text('code = "BAD"\nname = "Bad"\n[dsar]\ndeadline = "soon"\n', encoding="utf-8")
    monkeypatch.setattr("app.domain.rules.loader.RULES_DIR", tmp_path)
    load_all.cache_clear()
    with pytest.raises(RulesError):
        load_all()
    load_all.cache_clear()
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Rules file format** — example `app/content/jurisdictions/GDPR.toml` (values verified in Phase 0 Task 6; the GDPR ones below are from Regulation (EU) 2016/679):

```toml
code = "GDPR"
name = "General Data Protection Regulation (EU) 2016/679"
authority = "National supervisory authority (EU/EEA)"
authority_url = "https://www.edpb.europa.eu/about-edpb/about-edpb/members_en"
report_label = "GDPR Annual Compliance Report"
lawful_bases = ["consent", "contract", "legal_obligation", "vital_interest", "public_task", "legitimate_interest"]

[dsar]
deadline = "1 months"
extension = "2 months"
citation = "GDPR Art. 12(3)"
source_url = "https://eur-lex.europa.eu/eli/reg/2016/679/oj"

[breach]
authority_deadline = "72 hours"
standard = "without undue delay and, where feasible, not later than 72 hours"
citation = "GDPR Art. 33(1)"
source_url = "https://eur-lex.europa.eu/eli/reg/2016/679/oj"

[children]
consent_age = 16
note = "Member States may lower to no less than 13 (Art. 8(1)); use the member-state value when known."
citation = "GDPR Art. 8(1)"
source_url = "https://eur-lex.europa.eu/eli/reg/2016/679/oj"
```
Laws whose statute gives no fixed number (e.g. "as soon as reasonably possible") set `authority_deadline` absent and put the wording in `standard`. Create the remaining 13 files from `docs/audit/evidence/jurisdiction-review.md`, one commit-reviewable file per law.

- [ ] **Step 4: Implement `app/domain/rules/loader.py`**

```python
"""Load and validate jurisdiction rule files (TOML)."""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

RULES_DIR = Path(__file__).resolve().parents[2] / "content" / "jurisdictions"
_PERIOD = re.compile(r"^(\d+) (days|business_days|months|hours)$")


class RulesError(ValueError):
    pass


@dataclass(frozen=True)
class Period:
    amount: int
    unit: Literal["days", "business_days", "months", "hours"]


@dataclass(frozen=True)
class JurisdictionRules:
    code: str
    name: str
    authority: str
    authority_url: str
    report_label: str
    dsar_deadline: Period | None
    dsar_extension: Period | None
    breach_authority_deadline: Period | None
    breach_standard: str
    child_consent_age: int | None
    lawful_bases: tuple[str, ...]
    citations: dict = field(default_factory=dict)


def _period(value, where: str) -> Period | None:
    if value is None:
        return None
    m = _PERIOD.match(str(value))
    if not m:
        raise RulesError(f"{where}: invalid period {value!r} (expected e.g. '30 days', '1 months', '72 hours')")
    return Period(int(m.group(1)), m.group(2))  # type: ignore[arg-type]


def _cite(section: dict, where: str) -> dict:
    if not section.get("citation") or not str(section.get("source_url", "")).startswith("https://"):
        raise RulesError(f"{where}: citation and https source_url are required")
    return {"citation": section["citation"], "source_url": section["source_url"]}


def _parse(path: Path) -> JurisdictionRules:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    where = path.name
    for key in ("code", "name", "authority", "report_label"):
        if not data.get(key):
            raise RulesError(f"{where}: missing {key}")
    dsar, breach, children = data.get("dsar", {}), data.get("breach", {}), data.get("children", {})
    citations = {}
    dsar_deadline = _period(dsar.get("deadline"), f"{where} dsar.deadline")
    if dsar_deadline:
        citations["dsar_deadline"] = _cite(dsar, f"{where} [dsar]")
    breach_deadline = _period(breach.get("authority_deadline"), f"{where} breach.authority_deadline")
    if breach_deadline:
        citations["breach_authority_deadline"] = _cite(breach, f"{where} [breach]")
    age = children.get("consent_age")
    if age is not None:
        citations["child_consent_age"] = _cite(children, f"{where} [children]")
    return JurisdictionRules(
        code=data["code"], name=data["name"], authority=data["authority"],
        authority_url=data.get("authority_url", ""), report_label=data["report_label"],
        dsar_deadline=dsar_deadline, dsar_extension=_period(dsar.get("extension"), f"{where} dsar.extension"),
        breach_authority_deadline=breach_deadline, breach_standard=breach.get("standard", ""),
        child_consent_age=int(age) if age is not None else None,
        lawful_bases=tuple(data.get("lawful_bases", ())), citations=citations,
    )


@lru_cache(maxsize=1)
def load_all() -> dict[str, JurisdictionRules]:
    out = {}
    for path in sorted(RULES_DIR.glob("*.toml")):
        r = _parse(path)
        out[r.code] = r
    return out


def rules_for(code: str) -> JurisdictionRules:
    return load_all()[code]


def rules_for_country(country_code: str) -> list[JurisdictionRules]:
    from app.helpers import get_country_regulations
    return [rules_for(c) for c in get_country_regulations(country_code)]
```

- [ ] **Step 5: Implement `app/domain/rules/clock.py`**

```python
"""Statutory date arithmetic in the entity's local calendar."""
from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.domain.rules.loader import Period


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def add_business_days(d: date, n: int) -> date:
    cur = d
    while n > 0:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            n -= 1
    return cur


def local_date(dt_utc: datetime, tz: str) -> date:
    return dt_utc.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz)).date()


def statutory_deadline(start_utc: datetime, period: Period, tz: str) -> datetime:
    if period.unit == "hours":
        return start_utc + timedelta(hours=period.amount)
    start_local = local_date(start_utc, tz)
    if period.unit == "months":
        end_local = add_months(start_local, period.amount)
    elif period.unit == "business_days":
        end_local = add_business_days(start_local, period.amount)
    else:
        end_local = start_local + timedelta(days=period.amount)
    end = datetime.combine(end_local, time(23, 59, 59), tzinfo=ZoneInfo(tz))
    return end.astimezone(timezone.utc).replace(tzinfo=None)
```

- [ ] **Step 6: Labels from rules** — rewrite `helpers.get_country_regulation_labels(country_code)` to return `{"authority": r.authority, "law": r.name-short, "audit_label": r.report_label}` from the first `rules_for_country` entry (keep the `OTHER` fallback dict). Keep the function signature; delete `COUNTRY_REGULATION_LABELS`.

- [ ] **Step 7: Run tests** → PASS; full suite green.

- [ ] **Step 8: Commit**

```bash
git add retention_py/app/content retention_py/app/domain/rules retention_py/app/helpers.py retention_py/tests/test_core_rules.py
git commit -m "feat(rules): cited jurisdiction rules as data and statutory deadline arithmetic in entity local time"
```

---

### Task 2: Per-organisation audit chain v2, race-free and fully verified

Fixes SD-02-003 and two new findings: verification only covers the oldest 5,000 rows; concurrent appends can fork the chain.

**Files:**
- Modify: `retention_py/app/models.py` (`AuditLog.chain_version`, new `AuditChainHead`)
- Create: `retention_py/alembic/versions/0006_audit_chain_v2.py`, `retention_py/app/domain/audit.py`, `docs/adr/0001-record-architecture-decisions.md`, `docs/adr/0002-audit-chain-v2.md`
- Modify: `retention_py/app/helpers.py:276-314` (`log_audit` → delegate), `retention_py/app/engine.py:1426-1499` (`verify_audit_chain` → delegate), `retention_py/app/worker/jobs.py` (`_audit_chain` per org)
- Test: `retention_py/tests/test_core_audit_chain.py`

**Interfaces:**
- Produces: `append_event(db, org_id: int, action: str, entity_type: str, entity_id: int | None, performed_by: int | None, details, ip_address: str | None) -> AuditLog`; `verify_org_chain(db, org_id: int, batch: int = 1000) -> dict` with keys `ok`, `verified_count`, `first_broken_log_id`, `checked`, `broken_at` (backward-compatible keys); `verify_legacy_chain(db) -> dict` (v1 rows, full scan); `payload_v2(entry_fields...) -> str`.
- v2 payload: `"v2|{org_id}|{action}|{entity_type}|{entity_id or ''}|{performed_by or ''}|{canonical_details}|{ip or ''}|{created_at:%Y-%m-%dT%H:%M:%S.%f}|{prev_hash}"`, `canonical_details` = `json.dumps(details, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` or `""`.
- Genesis: the first v2 row of an org uses `prev_hash = sha256("genesis|{org_id}|{last_global_v1_hash or '0'*64}")`.

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_core_audit_chain.py
import threading

from app.database import SessionLocal
from app.domain.audit import append_event, verify_org_chain
from app.models import AuditLog, Organization


def _org2(db):
    o = Organization(name="O2", slug="o2", primary_domain="o2.test", country="GB", tier="core", status="active")
    db.add(o); db.commit()
    return o.id


def test_chains_are_per_org(db):
    o2 = _org2(db)
    append_event(db, 1, "a", "x", None, None, {"k": 1}, None)
    append_event(db, o2, "b", "x", None, None, None, None)
    append_event(db, 1, "c", "x", None, None, None, None)
    rows = db.query(AuditLog).filter_by(organization_id=1).order_by(AuditLog.id).all()
    assert rows[1].prev_hash == rows[0].row_hash
    assert verify_org_chain(db, 1)["ok"] and verify_org_chain(db, o2)["ok"]


def test_tamper_detected(db):
    for i in range(3):
        append_event(db, 1, f"a{i}", "x", None, None, {"i": i}, None)
    row = db.query(AuditLog).filter_by(organization_id=1).order_by(AuditLog.id).all()[1]
    row.details = {"i": 999}; db.commit()
    res = verify_org_chain(db, 1)
    assert res["ok"] is False and res["first_broken_log_id"] == row.id


def test_tamper_beyond_5000_detected(db):
    for i in range(5005):
        db.add(AuditLog(organization_id=1, action="bulk", entity_type="x", chain_version=1, row_hash=None))
    db.commit()
    for i in range(3):
        append_event(db, 1, f"v2-{i}", "x", None, None, None, None)
    newest = db.query(AuditLog).filter_by(organization_id=1, chain_version=2).order_by(AuditLog.id.desc()).first()
    newest.action = "forged"; db.commit()
    assert verify_org_chain(db, 1)["ok"] is False


def test_concurrent_appends_do_not_fork(db):
    def worker(n):
        s = SessionLocal()
        try:
            for i in range(10):
                append_event(s, 1, f"t{n}-{i}", "x", None, None, None, None)
        finally:
            s.close()
    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert db.query(AuditLog).filter_by(organization_id=1).count() == 40
    assert verify_org_chain(db, 1)["ok"]


def test_log_audit_uses_v2(db):
    from app.helpers import log_audit
    log_audit(db, 1, "x", "y", None, None, {"a": 1}, "1.2.3.4")
    assert db.query(AuditLog).one().chain_version == 2
```
(The concurrency test is meaningful on PostgreSQL — CI — where `with_for_update` takes a row lock; on SQLite writes serialise. Mark it `@pytest.mark.skipif(engine.dialect.name == "sqlite", reason="row locks need PostgreSQL")` only if it flakes on SQLite with `database is locked`; on SQLite set the engine `connect_args={"timeout": 30}` in `app/database.py` first.)

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Models + migration**

```python
# app/models.py — AuditLog: add
    chain_version = Column(Integer, nullable=False, default=1)
# and index: __table_args__ = (Index("ix_audit_org_id_id", "organization_id", "id"),)


class AuditChainHead(Base):
    __tablename__ = "audit_chain_heads"

    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    last_hash = Column(String(64), nullable=False)
    last_id = Column(Integer, nullable=True)
```
Generate `0006_audit_chain_v2.py` with autogenerate, then edit: `chain_version` added with `server_default="1"` so existing rows are v1. Add `AuditChainHead` to the tenant filter's exclusions? It has `organization_id`, so it is a tenant model — correct, nothing to change.

- [ ] **Step 4: Implement `app/domain/audit.py`**

```python
"""Tamper-evident audit chain v2: one hash chain per organisation, appended under a row lock."""
from __future__ import annotations

import hashlib
import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.models import AuditChainHead, AuditLog


def _canon(details) -> str:
    if details is None:
        return ""
    if isinstance(details, str):
        return details
    return json.dumps(details, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def payload_v2(org_id, action, entity_type, entity_id, performed_by, details, ip, created_at, prev_hash) -> str:
    return "|".join(["v2", str(org_id), action, entity_type,
                     "" if entity_id is None else str(entity_id),
                     "" if performed_by is None else str(performed_by),
                     _canon(details), ip or "", created_at.strftime("%Y-%m-%dT%H:%M:%S.%f"), prev_hash])


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _genesis(db: Session, org_id: int) -> str:
    last_v1 = (db.query(AuditLog.row_hash).filter(AuditLog.chain_version == 1, AuditLog.row_hash.isnot(None))
               .order_by(AuditLog.id.desc()).execution_options(skip_tenant_filter=True).first())
    return _sha(f"genesis|{org_id}|{last_v1[0] if last_v1 else '0' * 64}")


def _locked_head(db: Session, org_id: int) -> AuditChainHead:
    head = (db.query(AuditChainHead).filter(AuditChainHead.organization_id == org_id)
            .with_for_update().execution_options(skip_tenant_filter=True).first())
    if head is not None:
        return head
    db.add(AuditChainHead(organization_id=org_id, last_hash=_genesis(db, org_id), last_id=None))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
    return (db.query(AuditChainHead).filter(AuditChainHead.organization_id == org_id)
            .with_for_update().execution_options(skip_tenant_filter=True).one())


def append_event(db: Session, org_id: int, action: str, entity_type: str, entity_id=None,
                 performed_by=None, details=None, ip_address=None) -> AuditLog:
    head = _locked_head(db, org_id)
    created_at = utcnow()
    row_hash = _sha(payload_v2(org_id, action, entity_type, entity_id, performed_by, details,
                               ip_address, created_at, head.last_hash))
    entry = AuditLog(organization_id=org_id, action=action, entity_type=entity_type, entity_id=entity_id,
                     performed_by=performed_by, details=details, ip_address=ip_address,
                     prev_hash=head.last_hash, row_hash=row_hash, created_at=created_at, chain_version=2)
    db.add(entry)
    db.flush()
    head.last_hash, head.last_id = row_hash, entry.id
    db.commit()
    return entry


def verify_org_chain(db: Session, org_id: int, batch: int = 1000) -> dict:
    expected_prev = None
    verified, broken = 0, None
    q = (db.query(AuditLog).filter(AuditLog.organization_id == org_id, AuditLog.chain_version == 2)
         .order_by(AuditLog.id.asc()).execution_options(skip_tenant_filter=True, yield_per=batch))
    for e in q:
        if expected_prev is None:
            expected_prev = _genesis_for_verify(db, org_id, e)
        recomputed = _sha(payload_v2(e.organization_id, e.action, e.entity_type, e.entity_id, e.performed_by,
                                     e.details, e.ip_address, e.created_at, e.prev_hash))
        if e.prev_hash != expected_prev or e.row_hash != recomputed:
            broken = e.id
            break
        expected_prev = e.row_hash
        verified += 1
    ok = broken is None
    return {"ok": ok, "verified_count": verified, "first_broken_log_id": broken,
            "checked": verified, "broken_at": broken}


def _genesis_for_verify(db: Session, org_id: int, first_entry: AuditLog) -> str:
    """The genesis anchor is the last v1 hash at the moment the first v2 row was written."""
    last_v1 = (db.query(AuditLog.row_hash).filter(AuditLog.chain_version == 1, AuditLog.row_hash.isnot(None),
                                                  AuditLog.id < first_entry.id)
               .order_by(AuditLog.id.desc()).execution_options(skip_tenant_filter=True).first())
    return _sha(f"genesis|{org_id}|{last_v1[0] if last_v1 else '0' * 64}")
```

Note on `_genesis`: it reads the latest v1 hash at the time the head is created; since v1 writes stop once Task 2 is deployed, the anchor used at write time equals the one recomputed at verify time (`AuditLog.id < first_entry.id`).

- [ ] **Step 5: Delegate** — `helpers.log_audit(...)` body becomes `from app.domain.audit import append_event; append_event(db, org_id, action, entity_type, entity_id, performed_by, details, ip_address)`. Login-failure calls with `org_id=0` (unknown user) must not create a chain for a non-existent org: in `public.handle_login`, when `user is None` write a `LoginAttempt` only (already done) and skip `log_audit`.
  `engine.verify_audit_chain(db, org_id=None, limit=...)`: if `org_id` given → `verify_org_chain(db, org_id)`; else iterate all org ids and AND the results; keep the `limit` parameter accepted but unused (document as deprecated). Keep the v1 verifier as `verify_legacy_chain(db)` (move the old loop into `domain/audit.py`, remove the `.limit(limit)`, iterate with `yield_per`).

- [ ] **Step 6: Worker job per org** — in `jobs._audit_chain`, loop orgs: on failure notify **that org's** admins/DPOs only and collect broken ids; raise at the end if any broke (so `job_runs` records the failure).

- [ ] **Step 7: ADRs** — `docs/adr/0001-record-architecture-decisions.md` (Nygard template: context, decision, consequences; this repo records decisions in `docs/adr/NNNN-title.md`). `docs/adr/0002-audit-chain-v2.md`: why per-org, payload format (verbatim from Interfaces), genesis anchoring, locking, verification cost, how a tenant can verify its export offline (Phase 6 adds a downloadable verifier script).

- [ ] **Step 8: Run tests** → PASS on SQLite and (CI) PostgreSQL; full suite green (update `tests/test_audit_chain.py` expectations if they assert v1 internals).

- [ ] **Step 9: Commit**

```bash
git add retention_py/app retention_py/alembic retention_py/tests docs/adr
git commit -m "feat(audit): per-organisation v2 hash chain with row-locked appends and full streaming verification"
```

---

### Task 3: Separate data-encryption keys with rotation

Fixes SD-04-005.

**Files:**
- Create: `retention_py/app/core/crypto.py`
- Modify: `retention_py/app/config.py`, `retention_py/app/auth.py:27-50`, `retention_py/app/cli.py` (`reencrypt-secrets`)
- Test: `retention_py/tests/test_core_crypto.py`

**Interfaces:**
- Config: `DATA_ENCRYPTION_KEYS` = comma-separated Fernet keys, **first is primary** (production: required; local/test: derived dev key with a warning).
- Produces: `encrypt(plaintext: str) -> str`, `decrypt(token: str) -> str` (raises `DecryptionError` — never returns ciphertext), `is_legacy_secret(stored: str) -> bool`, `reencrypt(token: str) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_core_crypto.py
import pytest
from cryptography.fernet import Fernet

from app.core import crypto


@pytest.fixture
def keys(monkeypatch):
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    monkeypatch.setattr(crypto, "_keys", lambda: [old])
    yield old, new


def test_roundtrip(keys):
    assert crypto.decrypt(crypto.encrypt("JBSWY3DPEHPK3PXP")) == "JBSWY3DPEHPK3PXP"


def test_rotation_reads_old_writes_new(keys, monkeypatch):
    old, new = keys
    token = crypto.encrypt("secret")
    monkeypatch.setattr(crypto, "_keys", lambda: [new, old])
    assert crypto.decrypt(token) == "secret"
    rotated = crypto.reencrypt(token)
    monkeypatch.setattr(crypto, "_keys", lambda: [new])
    assert crypto.decrypt(rotated) == "secret"


def test_decrypt_failure_raises(keys):
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt("gAAAAABnotavalidtoken")


def test_legacy_plaintext_detected():
    assert crypto.is_legacy_secret("JBSWY3DPEHPK3PXP") is True
    assert crypto.is_legacy_secret("gAAAAAB...") is False
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Config** (append):

```python
_DEK = [k.strip() for k in os.getenv("DATA_ENCRYPTION_KEYS", "").split(",") if k.strip()]
if IS_PRODUCTION and not _DEK:
    print("FATAL: DATA_ENCRYPTION_KEYS must be set in production.", file=sys.stderr)
    sys.exit(1)
DATA_ENCRYPTION_KEYS = _DEK
```

- [ ] **Step 4: Implement `app/core/crypto.py`**

```python
"""Application-level encryption for secrets at rest (TOTP secrets, signing secrets, contact data)."""
from __future__ import annotations

import base64
import hashlib
import warnings

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class DecryptionError(Exception):
    pass


def _keys() -> list[str]:
    from app import config
    if config.DATA_ENCRYPTION_KEYS:
        return config.DATA_ENCRYPTION_KEYS
    warnings.warn("DATA_ENCRYPTION_KEYS not set; using a development key derived from SECRET_KEY", stacklevel=2)
    return [base64.urlsafe_b64encode(hashlib.sha256(f"SafeData_TOTP_KEY_{config.SECRET_KEY}".encode()).digest()).decode()]


def _mf() -> MultiFernet:
    return MultiFernet([Fernet(k.encode()) for k in _keys()])


def encrypt(plaintext: str) -> str:
    return _mf().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _mf().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError("cannot decrypt secret with configured keys") from exc


def reencrypt(token: str) -> str:
    return _mf().rotate(token.encode()).decode()


def is_legacy_secret(stored: str) -> bool:
    return not stored.startswith("gAAAAA")
```
The development fallback key equals the old SECRET_KEY-derived key, so existing local 2FA secrets keep working; production sets `DATA_ENCRYPTION_KEYS="<new>,<old-derived>"` once, runs `reencrypt-secrets`, then drops the old key.

- [ ] **Step 5: Use it in `app/auth.py`** — replace `_get_totp_fernet_key`, `encrypt_totp_secret`, `decrypt_totp_secret` with:

```python
from app.core import crypto


def encrypt_totp_secret(secret_b32: str) -> str:
    return crypto.encrypt(secret_b32.strip()) if secret_b32 else ""


def decrypt_totp_secret(stored_secret: str) -> str:
    if not stored_secret:
        return ""
    if crypto.is_legacy_secret(stored_secret):
        return stored_secret  # pre-encryption plaintext; re-encrypted by `cli reencrypt-secrets`
    return crypto.decrypt(stored_secret)  # raises on failure — callers treat as invalid 2FA
```
Wrap the three call sites (`/login/2fa`, step-up auth, settings 2FA) so a `DecryptionError` logs an error and returns the generic "Invalid verification code" message.

- [ ] **Step 6: CLI `reencrypt-secrets`** — iterate users with `twofa_secret`: plaintext → `encrypt`; encrypted → `reencrypt`; same for `ConnectedSystem.signing_secret`; print counts; idempotent.

- [ ] **Step 7: Run tests** → PASS; full suite green.

- [ ] **Step 8: Commit**

```bash
git add retention_py/app/core/crypto.py retention_py/app/config.py retention_py/app/auth.py retention_py/app/cli.py retention_py/tests/test_core_crypto.py
git commit -m "feat(security): dedicated rotating data-encryption keys; decryption failures fail loudly"
```

---

### Task 4: Time and error hygiene

Fixes F15 / SD-05-002.

**Files:**
- Modify: every file listed by `python ../tools/audit/collect_metrics.py --app app --out <scratch>/m` under `utcnow`, `prints`, `swallowed_excepts`
- Modify: `retention_py/pyproject.toml` (widen ruff `include` to the modules cleaned)
- Test: `retention_py/tests/test_core_hygiene.py`

- [ ] **Step 1: Write the failing test** (uses the Phase 0 metrics tool as the gate)

```python
# retention_py/tests/test_core_hygiene.py
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.audit.collect_metrics import collect  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "app"


def test_no_naive_utcnow_or_print():
    m = collect(APP)
    assert m["utcnow"] == [], m["utcnow"]
    assert m["prints"] == [], m["prints"]


def test_no_unexplained_broad_excepts():
    offenders = []
    for py in APP.rglob("*.py"):
        lines = py.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if re.match(r"\s*except( Exception)?( as \w+)?:\s*(#.*)?$", line):
                window = " ".join(lines[i:i + 3])
                if "fail-open:" not in window and "fail-closed:" not in window and "log" not in window \
                        and "raise" not in window:
                    offenders.append(f"{py.relative_to(APP)}:{i + 1}")
    assert offenders == [], offenders
```

- [ ] **Step 2: Run to verify failure** → FAIL with the current lists.

- [ ] **Step 3: Fix, file by file**
  - `datetime.utcnow()` and `datetime.now(timezone.utc).replace(tzinfo=None)` → `utcnow()` from `app.core.clock`.
  - `print(...)` → `log = logging.getLogger(__name__)` + `log.info/warning/error(...)`.
  - Each broad `except`: decide and annotate —
    - **fail-closed** (security decisions: session, permission, CSRF, throttling decision path): log at `error`, deny. Example: `login_throttle_seconds` currently returns 0 (allows login) on DB error → keep returning 0 only because login itself will fail without DB; annotate `# fail-open: login also requires the DB; throttling cannot be checked when it is down` and log `warning`.
    - **fail-open** (non-critical presentation: unread-notification badge count, trial-days banner): log at `warning`, continue with a safe default, annotate with the reason.
    - **unexpected**: remove the `try/except` so the global handler logs a 500 with request id.
  - After each module, add it to the ruff `include` list and run `ruff check` on it.

- [ ] **Step 4: Run tests** — `python -m pytest tests/test_core_hygiene.py -v` → PASS; full suite green.

- [ ] **Step 5: Commit** (one commit per 2–3 modules is fine; final commit:)

```bash
git add retention_py/app retention_py/pyproject.toml retention_py/tests/test_core_hygiene.py
git commit -m "refactor: central clock, structured logging, every broad except justified or removed"
```

---

### Task 5: Translation scaffolding and locale formatting

Implements spec D17 / §7.6 foundation.

**Files:**
- Create: `retention_py/app/core/i18n.py`, `retention_py/babel.cfg`, `retention_py/app/locale/en/LC_MESSAGES/messages.po`
- Modify: `retention_py/requirements.txt` (+ `Babel==2.17.0`), every `Jinja2Templates(...)` creation (install i18n), `retention_py/app/templates/layout.html` (wrap strings), `retention_py/app/cli.py` (`i18n-extract`, `i18n-compile`)
- Test: `retention_py/tests/test_core_i18n.py`

**Interfaces:**
- Produces: `install_i18n(templates: Jinja2Templates) -> None` (adds `jinja2.ext.i18n`, installs gettext callables resolving per-request locale via a ContextVar), `locale_var: ContextVar[str]`, `LocaleMiddleware` (sets `locale_var` from user preference → `Accept-Language` → `en`), template globals `format_date(d)`, `format_number(n)`, `format_money(amount_minor: int, currency: str)`.

- [ ] **Step 1: Write the failing tests**

```python
# retention_py/tests/test_core_i18n.py
from datetime import date

from fastapi.templating import Jinja2Templates

from app.core.i18n import format_date, format_money, install_i18n, locale_var


def test_trans_tag_renders(tmp_path):
    (tmp_path / "t.html").write_text("{% trans %}Retention Register{% endtrans %}", encoding="utf-8")
    t = Jinja2Templates(directory=str(tmp_path))
    install_i18n(t)
    assert t.get_template("t.html").render() == "Retention Register"


def test_locale_formatting():
    token = locale_var.set("en_GB")
    try:
        assert format_date(date(2026, 11, 3)) == "3 Nov 2026"
        assert "119,000.00" in format_money(11900000, "NGN")
    finally:
        locale_var.reset(token)
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Implement `app/core/i18n.py`**

```python
"""gettext for Jinja templates and locale-aware formatting (Babel)."""
from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path

from babel import Locale, UnknownLocaleError
from babel.dates import format_date as _fd
from babel.numbers import format_currency, format_decimal
from babel.support import NullTranslations, Translations

LOCALE_DIR = Path(__file__).resolve().parents[1] / "locale"
SUPPORTED = ("en",)
locale_var: ContextVar[str] = ContextVar("locale", default="en")
_cache: dict[str, NullTranslations] = {}


def _translations() -> NullTranslations:
    lang = locale_var.get().split("_")[0]
    if lang not in _cache:
        _cache[lang] = Translations.load(str(LOCALE_DIR), [lang]) if lang in SUPPORTED else NullTranslations()
    return _cache[lang]


def gettext(s: str) -> str:
    return _translations().gettext(s)


def ngettext(s: str, p: str, n: int) -> str:
    return _translations().ngettext(s, p, n)


def format_date(d) -> str:
    return _fd(d, format="d MMM y", locale=locale_var.get())


def format_number(n) -> str:
    return format_decimal(n, locale=locale_var.get())


def format_money(amount_minor: int, currency: str) -> str:
    return format_currency(amount_minor / 100, currency, locale=locale_var.get())


def install_i18n(templates) -> None:
    env = templates.env
    env.add_extension("jinja2.ext.i18n")
    env.install_gettext_callables(gettext, ngettext, newstyle=True)
    env.globals.update(format_date=format_date, format_number=format_number, format_money=format_money)


class LocaleMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        header = dict(scope.get("headers") or []).get(b"accept-language", b"").decode("latin-1")
        chosen = "en"
        for part in header.split(","):
            tag = part.split(";")[0].strip().replace("-", "_")
            try:
                if tag and Locale.parse(tag):
                    chosen = tag
                    break
            except (ValueError, UnknownLocaleError):
                continue
        token = locale_var.set(chosen)
        try:
            await self.app(scope, receive, send)
        finally:
            locale_var.reset(token)
```
(Text stays English because only `en` is in `SUPPORTED`; dates, numbers and currency follow the visitor's locale.)

- [ ] **Step 4: Wire up** — call `install_i18n(templates)` right after every `templates = Jinja2Templates(...)` (grep `Jinja2Templates(` in `app/routes` and `main.py`); add `LocaleMiddleware` in `main.py` (inside `RequestIdMiddleware`). `babel.cfg`:

```
[python: app/**.py]
[jinja2: app/templates/**.html]
extensions=jinja2.ext.i18n
```
CLI: `i18n-extract` → `pybabel extract -F babel.cfg -o app/locale/messages.pot .`; `i18n-compile` → `pybabel compile -d app/locale`. Wrap every user-facing string in `layout.html` with `{% trans %}…{% endtrans %}` / `{{ _("…") }}`; Phase 2 does the rest as templates are rebuilt (rule recorded in `docs/adr/0003-translatable-strings.md`: every new template string is wrapped).

- [ ] **Step 5: Run tests** → PASS; full suite green.

- [ ] **Step 6: Commit**

```bash
git add retention_py/app retention_py/babel.cfg retention_py/requirements.txt retention_py/tests/test_core_i18n.py docs/adr
git commit -m "feat(i18n): gettext in templates and locale-aware date/number/money formatting"
```

---

### Task 6: Disposal-safety net across the hierarchy and display-currency fixes

Implements spec R2 guarantees under the new tenancy; fixes F12 mapping errors.

**Files:**
- Modify: `retention_py/app/helpers.py` (`COUNTRY_TO_CURRENCY`)
- Test: `retention_py/tests/test_core_safety.py`, `retention_py/tests/test_geo_pricing.py` (extend)

- [ ] **Step 1: Write the failing/pinning tests**

```python
# retention_py/tests/test_core_safety.py
from datetime import date, timedelta

from app.database import SessionLocal
from app.models import DataCategory, DataRecord, Unit
from app.worker.jobs import JOBS
from app.worker.runner import run_job


def _expired_dual_record(db, entity_id, unit_id=None):
    cat = DataCategory(organization_id=1, entity_id=entity_id, name="Children", retention_period_days=1,
                       data_classification="children", approval_type="dual_approval", requires_dual_approval=True)
    db.add(cat); db.commit()
    rec = DataRecord(organization_id=1, entity_id=entity_id, unit_id=unit_id, category_id=cat.id,
                     record_reference="CH-1", collection_date=date.today() - timedelta(days=400),
                     retention_end_date=date.today() - timedelta(days=30))
    db.add(rec); db.commit()
    return rec


def test_worker_never_disposes_dual_approval_records(db, entity_id):
    unit = Unit(organization_id=1, entity_id=entity_id, name="Paediatrics"); db.add(unit); db.commit()
    rec = _expired_dual_record(db, entity_id, unit.id)
    job = next(j for j in JOBS if j.name == "retention")
    assert run_job(job, SessionLocal, "safety-test") == "success"
    db.expire_all()
    rec = db.get(DataRecord, rec.id)
    assert rec.status != "disposed" and rec.disposed_at is None


def test_api_disposed_endpoint_cannot_bypass_dual_approval(client, db, entity_id):
    from app.enterprise import create_api_key
    from app.models import ConnectedSystem
    rec = _expired_dual_record(db, entity_id)
    sysm = ConnectedSystem(organization_id=1, name="CRM"); db.add(sysm); db.commit()
    key = create_api_key(db, sysm.id, "k", ["records:write", "records:read"])
    raw = key["raw_key"] if isinstance(key, dict) else key
    r = client.post("/api/v1/records/disposed", headers={"X-API-Key": raw},
                    json={"record_reference": "CH-1"})
    db.expire_all()
    assert db.get(DataRecord, rec.id).status != "disposed", r.text
```
(Adjust the `create_api_key` return handling and payload keys to the actual function/endpoint contracts — read `app/enterprise.py:74` and `app/routes/api_v1.py:478` first; the assertion — dual-approval record not disposed — is the fixed requirement. If the API currently disposes it, that is a Critical finding: fix `api_v1.records_disposed` to route through `engine.request_disposal` so dual approval applies, and record the finding in `docs/audit/findings.md`.)

Extend `tests/test_geo_pricing.py`:

```python
def test_non_euro_eu_countries_not_mapped_to_eur():
    for cc, cur in {"SE": "SEK", "PL": "PLN", "DK": "DKK", "CZ": "CZK", "HU": "HUF", "RO": "RON",
                    "BG": "EUR", "CH": "CHF", "NO": "NOK", "IS": "ISK"}.items():
        assert COUNTRY_TO_CURRENCY.get(cc, "USD") in (cur, "USD"), cc
    for cc in ("LU", "SK", "SI", "EE", "LV", "LT", "MT", "CY", "HR"):
        assert COUNTRY_TO_CURRENCY[cc] == "EUR", cc
```
(Bulgaria joined the euro on 1 January 2026; confirm with the ECB page during implementation and record the source URL in the test comment.)

- [ ] **Step 2: Run** → the currency test FAILS (SE/PL → EUR; LU… missing); safety tests PASS or reveal a Critical bypass (fix as described).

- [ ] **Step 3: Fix `COUNTRY_TO_CURRENCY`** — remove `"SE": "EUR"` and `"PL": "EUR"`; add the missing eurozone members; non-euro EU states map to their currency only if that currency exists in `CURRENCY_DATA`, otherwise fall back to USD (Phase 3 price books add them properly).

- [ ] **Step 4: Run tests** → PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add retention_py/app/helpers.py retention_py/app/routes/api_v1.py retention_py/tests docs/audit/findings.md
git commit -m "test(safety): dual-approval disposal safety pinned across worker, API and hierarchy; fix EU currency mapping"
```
