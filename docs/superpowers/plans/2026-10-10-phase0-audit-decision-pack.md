# Phase 0 — Full Audit & Stakeholder Decision Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an evidence-backed 14-dimension audit of SafeData and a stakeholder decision pack (pricing, payments, hosting/domain/cost, consent explainer, go-to-market) that stakeholders can decide from without further explanation.

**Architecture:** Re-runnable evidence tools (a metrics collector, a route × role access-matrix generator, a cross-tenant isolation probe, a Git-history blob inspector) produce machine-generated evidence under `docs/audit/evidence/`. Human analysis of each dimension goes into a findings register; the report and decision-pack documents are written from that register. The same tools are re-run in Phase 6 to prove closure.

**Tech Stack:** Python 3.12+ (stdlib + existing deps), pytest, FastAPI TestClient, Playwright (MCP or `playwright` CLI) for screenshots, `pip-audit`, `bandit`, Markdown → PDF via existing `Documents/convert_to_pdf.py`.

**Spec:** `docs/superpowers/specs/2026-10-10-safedata-launch-programme-design.md` (§4, §13, §15, §6, §10–12)

## Global Constraints

- Product name in all documents: **SafeData by 3Consulting**. Tagline: **"Keep what you must. Release what you should."**
- App domain at launch: `safedata.3consult-ng.com`. Platform admin domain: `@3consult-ng.com`.
- Severity scale: **Critical / High / Medium / Low** (definitions in Task 1).
- Every finding carries: id, dimension (1–14 from spec §13), severity, evidence (`file:line`, command output, or screenshot path), user/business impact, fix, phase (0–6), verification method.
- Audience of stakeholder documents: non-technical business stakeholders; plain language, legal/technical terms explained on first use.
- Never copy personal data (real names, emails, phone numbers) from any database or Git blob into the repository, documents or chat. Extract to the session scratchpad only.
- Evidence tools must run against the **test** database only, never `retention.db` or any production URL.
- Payments facts to state: Stripe does not onboard Nigeria-registered companies; the director resides in Nigeria, so a personal Stripe account is not an option; launch on Paystack; evaluate Paddle (Merchant of Record) payouts to Nigeria; UK Ltd for Stripe otherwise.
- Prices are **drafts for stakeholder tuning** and must be labelled as such.
- Phase 0 Tasks 3 and 4 depend on Phase 1A Task 1 (test-database isolation fix) being merged first.

## Review Focus

1. **Evidence tool pointed at the wrong database** — expect: the tools refuse to run unless `APP_ENV=test` and the DB URL is the test URL (Task 2 and Task 3 tests pin this).
2. **Git-history inspection leaking personal data** — expect: blobs extracted only to a directory outside the repo; report contains counts/categories, never values (Task 5 test pins redaction).
3. **Access-matrix false "OK" because a redirect to /login looks like 303 success** — expect: matrix classifies 303→/login as DENIED, 200 as ALLOWED, 403 as DENIED, 404 as NOT-FOUND (Task 3 test pins classification).
4. **Prices that silently go stale** — expect: every local price in the pack shows the reference FX rate and the date it was taken (Task 9 checklist).
5. **Claims in documents not backed by evidence** — expect: every statement of fact in the audit report links to a finding id or evidence file (Task 8 self-check step).

---

## File Structure

```
tools/audit/
  __init__.py
  collect_metrics.py        # static code metrics → JSON + Markdown
  inspect_history_blobs.py  # lists/inspects .db blobs in git history (redacted summary)
retention_py/tests/audit/
  __init__.py
  test_collect_metrics.py
  test_inspect_history_blobs.py
  test_access_matrix.py     # generates docs/audit/evidence/access-matrix.md
  test_tenant_isolation_probe.py  # generates docs/audit/evidence/isolation-probe.md
docs/audit/
  README.md                 # severity rubric, finding format, how to re-run tools
  findings.md               # findings register (single source of truth)
  2026-10-audit-report.md   # the 14-dimension report
  evidence/                 # generated outputs + screenshots (no personal data)
Documents/launch/
  00_EXECUTIVE_DECISION_PACK.md
  01_PRICING_AND_PACKAGING.md
  02_PAYMENTS_AND_BILLING_OPTIONS.md
  03_HOSTING_DOMAIN_AND_COST_MODEL.md
  04_CONSENT_MANAGEMENT_EXPLAINED.md
  05_GO_TO_MARKET_AND_LAUNCH_CHECKLIST.md
  PDFs/                     # generated
```

---

### Task 1: Audit scaffolding — rubric, findings register, README

**Files:**
- Create: `docs/audit/README.md`
- Create: `docs/audit/findings.md`
- Create: `docs/audit/evidence/.gitkeep`

**Interfaces:**
- Produces: finding id format `SD-<dimension 2 digits>-<seq 3 digits>` (e.g. `SD-04-002`), used by every later task.

- [ ] **Step 1: Write `docs/audit/README.md`**

```markdown
# SafeData Audit

## Severity rubric
| Severity | Definition | Launch rule |
|---|---|---|
| Critical | Data loss, cross-tenant exposure, unlawful disposal, auth bypass, or legal non-compliance of SafeData itself. | Must be fixed before any customer data is accepted. |
| High | Security weakness exploitable by an authenticated user, broken core workflow, missing advertised feature, data-integrity risk. | Must be fixed before go-live. |
| Medium | Degraded UX, maintainability or operability problem with a workaround. | Fix in programme; may ship with a dated plan. |
| Low | Polish, consistency, minor docs. | Backlog. |

## Dimensions (spec §13)
01 Product & UX · 02 Compliance correctness · 03 SafeData legal posture · 04 Security ·
05 Engineering & architecture · 06 Data & database · 07 Testing & QA · 08 Performance ·
09 Reliability & operations · 10 DevOps & SDLC · 11 Billing & commercial · 12 Accessibility
& i18n · 13 Documentation · 14 Go-to-market

## Finding format (one row per finding in findings.md)
| ID | Dim | Sev | Title | Evidence | Impact | Fix | Phase | Verify |

## Re-running evidence tools
    cd retention_py
    python ../tools/audit/collect_metrics.py --app app --out ../docs/audit/evidence/metrics
    $env:APP_ENV="test"; python -m pytest tests/audit -q
    python ../tools/audit/inspect_history_blobs.py --repo .. --scratch <scratchpad-dir> --out ../docs/audit/evidence/history-blobs.md
```

- [ ] **Step 2: Write `docs/audit/findings.md`** seeded with spec §4 findings F1–F20 converted to the register format, ids `SD-xx-nnn`, keeping the spec's evidence and severity. Header:

```markdown
# Findings Register
Source of truth for the audit report. Never delete a row; mark closed rows with the closing commit.

| ID | Dim | Sev | Title | Evidence | Impact | Fix | Phase | Verify | Status |
|---|---|---|---|---|---|---|---|---|---|
| SD-11-001 | 11 | Critical | No payment integration | `retention_py/app/templates/billing.html`; `app/models.py:21,511` | Cannot take money; trial expiry dead-ends | Phase 3 billing layer | 3 | E2E test-mode purchase | Open |
```
(Continue for all 20, mapping F2→SD-04-001, F3→SD-04-002, F4→SD-04-003, F5→SD-09-001, F6→SD-02-001, F7→SD-09-002, F8→SD-06-001, F9→SD-01-001, F10→SD-04-004, F11→SD-11-002, F12→SD-11-003, F13→SD-02-002, F14→SD-05-001, F15→SD-05-002, F16→SD-01-002, F17→SD-07-001, F18→SD-10-001, F19→SD-10-002, F20→SD-09-003. Add these new findings discovered while planning:)

```markdown
| SD-07-002 | 07 | High | Tests and middleware hit the dev DB: conftest builds its own engine but `app.database.SessionLocal` (used by SessionEnforcementMiddleware and the patched TemplateResponse) still points at `retention.db` | `tests/conftest.py:24`; `app/middleware.py:246,290`; `main.py:47` | Tests pass or fail depending on dev data; can mutate dev DB | Phase 1A Task 1 | 1 | Test asserts single engine | Open |
| SD-05-003 | 05 | High | `main.py` performs schema changes and seeding at import time | `main.py:99-180` | Any import (tests, workers, CLI) mutates the configured DB | Phase 1A Task 2/3 | 1 | Import with read-only DB succeeds | Open |
| SD-04-005 | 04 | Medium | TOTP encryption key derived from SECRET_KEY; rotating SECRET_KEY breaks every user's 2FA; decrypt failure silently returns ciphertext | `app/auth.py:29-50` | Lockout on key rotation; silent auth errors | Separate `DATA_ENCRYPTION_KEY`, fail loudly | 1 | Unit test | Open |
| SD-06-002 | 06 | High | Schema cannot be created on PostgreSQL: unnamed native `Enum` columns (`CompileError: PostgreSQL ENUM type requires a name`); current `render.yaml` Postgres deployment cannot have worked | `app/models.py` (all `Enum(...)` columns) | Production target database unusable | Non-native enums (Phase 1A Task 2) | 1 | create_all on PostgreSQL in CI | Open |
| SD-04-006 | 04 | Critical | First-visitor setup takeover: on a fresh deployment every protected route redirects to public `/setup`, and whoever submits it first creates the first organisation and sets **global** `app_name`/`white_label_name` for all tenants | `routes/public.py:619-729`; `middleware.py:243-256` | Platform hijack on deploy; one tenant renames the platform for everyone | Remove setup wizard; Platform Owner CLI bootstrap; white-label per organisation (Phase 1B) | 1 | Test: /setup gone; fresh DB serves login | Open |
| SD-09-004 | 09 | High | Backups fail on PostgreSQL (MySQL-only `SHOW CREATE TABLE`) and are written unencrypted to local disk containing all tenants | `app/backups.py:49-71` | No usable backups in production | pg_dump to encrypted object storage (Phase 1A Task 5) | 1 | Restore drill | Open |
| SD-04-007 | 04 | High | Every tenant-owned column defaults `organization_id` to 1, so any insert that forgets the org silently writes into organisation 1 | `app/models.py` (`default=1` on organization_id columns) | Silent cross-tenant data placement | Remove defaults; NOT NULL without default (Phase 1B) | 1 | Insert without org raises | Open |
| SD-02-003 | 02 | Medium | Single global audit hash chain across all tenants; a tenant cannot independently verify or export its own chain | `app/helpers.py:276`; `app/engine.py:1426` | Weak tenant-level evidence; cross-tenant coupling | Per-organisation chain | 1 | Verify per org | Open |
```

- [ ] **Step 3: Commit**

```bash
git add docs/audit
git commit -m "docs(audit): rubric, findings register seeded from spec"
```

---

### Task 2: Static metrics collector

**Files:**
- Create: `tools/audit/__init__.py` (empty)
- Create: `tools/audit/collect_metrics.py`
- Test: `retention_py/tests/audit/__init__.py` (empty), `retention_py/tests/audit/test_collect_metrics.py`

**Interfaces:**
- Produces: `collect(app_dir: Path) -> dict` with keys `module_lines: dict[str,int]`, `large_modules: list[str]` (>500 lines), `inline_styles: int`, `swallowed_excepts: list[str]` (`file:line`), `prints: list[str]`, `utcnow: list[str]`, `session_boilerplate: int`, `post_routes_without_role_check: list[str]`; `render_markdown(m: dict) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# retention_py/tests/audit/test_collect_metrics.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.audit.collect_metrics import collect, render_markdown  # noqa: E402


def _make_app(tmp_path: Path) -> Path:
    app = tmp_path / "app"
    (app / "routes").mkdir(parents=True)
    (app / "templates").mkdir()
    (app / "routes" / "things.py").write_text(
        '@router.post("/things/create")\n'
        "def create(request):\n"
        "    session = get_session(request)\n"
        "    print('x')\n"
        "    return 1\n"
        '@router.post("/things/delete")\n'
        "def delete(request):\n"
        "    session = get_session(request)\n"
        "    if session.get('role') != 'admin':\n"
        "        return 403\n",
        encoding="utf-8",
    )
    (app / "engine.py").write_text(
        "from datetime import datetime\n"
        "try:\n    x = datetime.utcnow()\nexcept Exception:\n    pass\n",
        encoding="utf-8",
    )
    (app / "templates" / "a.html").write_text('<div style="a"></div><p style="b"></p>', encoding="utf-8")
    return app


def test_collect_counts_signals(tmp_path):
    m = collect(_make_app(tmp_path))
    assert m["inline_styles"] == 2
    assert m["session_boilerplate"] == 2
    assert any(p.endswith("things.py:4") for p in m["prints"])
    assert any(p.endswith("engine.py:3") for p in m["utcnow"])
    assert any(p.endswith("engine.py:4") for p in m["swallowed_excepts"])
    assert m["post_routes_without_role_check"] == ["routes/things.py:/things/create"]


def test_render_markdown_has_sections(tmp_path):
    md = render_markdown(collect(_make_app(tmp_path)))
    assert "# Code Metrics" in md
    assert "POST routes without a role check" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd retention_py; python -m pytest tests/audit/test_collect_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.audit.collect_metrics'`

- [ ] **Step 3: Write the implementation**

```python
# tools/audit/collect_metrics.py
"""Static code metrics for the SafeData audit. Re-run in Phase 6 to prove closure."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROUTE_RE = re.compile(r'@router\.post\("([^"]+)"')
ROLE_TOKENS = ("role", "require(", "require_role", "can(")


def _rel(p: Path, base: Path) -> str:
    return p.relative_to(base).as_posix()


def _post_routes_without_role(path: Path, base: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[str] = []
    for i, line in enumerate(lines):
        m = ROUTE_RE.search(line)
        if not m:
            continue
        body: list[str] = []
        for nxt in lines[i + 1:]:
            if nxt.startswith("@router."):
                break
            body.append(nxt)
        text = "\n".join(body)
        if not any(tok in text for tok in ROLE_TOKENS):
            out.append(f"{_rel(path, base)}:{m.group(1)}")
    return out


def collect(app_dir: Path) -> dict:
    app_dir = Path(app_dir)
    module_lines: dict[str, int] = {}
    swallowed, prints, utcnow = [], [], []
    session_boilerplate = 0
    no_role: list[str] = []
    for py in sorted(app_dir.rglob("*.py")):
        rel = _rel(py, app_dir)
        lines = py.read_text(encoding="utf-8", errors="replace").splitlines()
        module_lines[rel] = len(lines)
        for n, line in enumerate(lines, start=1):
            s = line.strip()
            if s.startswith("print("):
                prints.append(f"{rel}:{n}")
            if "utcnow(" in s:
                utcnow.append(f"{rel}:{n}")
            if s in ("except Exception:", "except:"):
                nxt = lines[n].strip() if n < len(lines) else ""
                if nxt == "pass":
                    swallowed.append(f"{rel}:{n}")
            if "session = get_session(request)" in s:
                session_boilerplate += 1
        if "routes" in py.parts:
            no_role.extend(_post_routes_without_role(py, app_dir))
    inline_styles = sum(
        html.read_text(encoding="utf-8", errors="replace").count('style="')
        for html in app_dir.rglob("*.html")
    )
    return {
        "module_lines": module_lines,
        "large_modules": sorted(k for k, v in module_lines.items() if v > 500),
        "inline_styles": inline_styles,
        "swallowed_excepts": swallowed,
        "prints": prints,
        "utcnow": utcnow,
        "session_boilerplate": session_boilerplate,
        "post_routes_without_role_check": sorted(no_role),
    }


def render_markdown(m: dict) -> str:
    rows = "\n".join(f"| `{k}` | {v} |" for k, v in sorted(m["module_lines"].items(), key=lambda kv: -kv[1])[:15])
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- `{i}`" for i in items) or "- none"
    return (
        "# Code Metrics\n\n"
        f"- Modules over 500 lines: {len(m['large_modules'])}\n"
        f"- Inline `style=` attributes in templates: {m['inline_styles']}\n"
        f"- Swallowed exceptions (`except …: pass`): {len(m['swallowed_excepts'])}\n"
        f"- `print()` calls: {len(m['prints'])}\n"
        f"- `utcnow()` calls: {len(m['utcnow'])}\n"
        f"- Hand-written session checks: {m['session_boilerplate']}\n\n"
        "## Largest modules\n\n| Module | Lines |\n|---|---|\n" + rows + "\n\n"
        "## POST routes without a role check\n\n" + bullets(m["post_routes_without_role_check"]) + "\n\n"
        "## Swallowed exceptions\n\n" + bullets(m["swallowed_excepts"]) + "\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True)
    ap.add_argument("--out", required=True, help="output path without extension")
    a = ap.parse_args()
    m = collect(Path(a.app))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    out.with_suffix(".md").write_text(render_markdown(m), encoding="utf-8")
    print(f"wrote {out.with_suffix('.md')}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd retention_py; python -m pytest tests/audit/test_collect_metrics.py -v`
Expected: 2 passed

- [ ] **Step 5: Generate evidence against the real app**

Run: `cd retention_py; python ../tools/audit/collect_metrics.py --app app --out ../docs/audit/evidence/metrics`
Expected: `wrote ../docs/audit/evidence/metrics.md`; open it and confirm the POST-routes list includes `routes/categories.py:/categories/create`, `routes/ropa.py:/ropa/create`, `routes/import_records.py:/import`.

- [ ] **Step 6: Commit**

```bash
git add tools/audit retention_py/tests/audit docs/audit/evidence/metrics.md docs/audit/evidence/metrics.json
git commit -m "feat(audit): static metrics collector + baseline evidence"
```

---

### Task 3: Route × role access-matrix generator

Depends on Phase 1A Task 1 (single test engine) being merged.

**Files:**
- Create: `retention_py/tests/audit/test_access_matrix.py`
- Output: `docs/audit/evidence/access-matrix.md`

**Interfaces:**
- Consumes: fixtures `db`, `client` from `tests/conftest.py` (post-1A Task 1); `app.auth.serializer`, `app.auth.build_session_data`; `main.app`.
- Produces: `classify(status: int, location: str | None) -> str` returning one of `ALLOWED`, `DENIED`, `NOT_FOUND`, `ERROR`.

- [ ] **Step 1: Write the test + generator**

```python
# retention_py/tests/audit/test_access_matrix.py
"""Generates docs/audit/evidence/access-matrix.md: what each current role can reach."""
from pathlib import Path

from fastapi.routing import APIRoute

from app.auth import build_session_data, hash_password, serializer
from app.models import DataCategory, DataRecord, Organization, User
from main import app

OUT = Path(__file__).resolve().parents[3] / "docs" / "audit" / "evidence" / "access-matrix.md"
ROLES = ["anonymous", "data_owner", "dpo", "admin"]


def classify(status: int, location: str | None) -> str:
    if status in (301, 302, 303, 307) and location and "/login" in location:
        return "DENIED"
    if status in (401, 403):
        return "DENIED"
    if status == 404:
        return "NOT_FOUND"
    if status >= 500:
        return "ERROR"
    return "ALLOWED"


def test_classify():
    assert classify(303, "/login") == "DENIED"
    assert classify(303, "/login?expired=1") == "DENIED"
    assert classify(303, "/dashboard") == "ALLOWED"
    assert classify(200, None) == "ALLOWED"
    assert classify(403, None) == "DENIED"
    assert classify(404, None) == "NOT_FOUND"
    assert classify(500, None) == "ERROR"


def _seed(db):
    org = db.get(Organization, 1)
    org.status = "active"
    org.subscription_status = "active"
    users = {}
    for role in ("data_owner", "dpo", "admin"):
        u = User(organization_id=1, name=f"{role} user", email=f"{role}@test.local",
                 password_hash=hash_password("Xyq9$mNpL2!k"), role=role, is_active=True,
                 email_verified_at=org.created_at)
        db.add(u)
        users[role] = u
    db.commit()
    cat = DataCategory(organization_id=1, name="Audit cat", retention_period_days=365)
    db.add(cat)
    db.commit()
    rec = DataRecord(organization_id=1, category_id=cat.id, record_reference="AUD-1")
    db.add(rec)
    db.commit()
    return org, users, {"id": rec.id, "record_id": rec.id, "entry_id": 1, "uid": users["admin"].id,
                        "nid": 1, "proc_id": 1}


def test_generate_access_matrix(db, client):
    org, users, ids = _seed(db)
    rows = []
    gets = sorted(
        (r for r in app.routes if isinstance(r, APIRoute) and "GET" in r.methods
         and not r.path.startswith("/api/")),
        key=lambda r: r.path,
    )
    for route in gets:
        path = route.path
        for k, v in ids.items():
            path = path.replace("{" + k + "}", str(v))
        if "{" in path:
            continue
        cells = []
        for role in ROLES:
            client.cookies.clear()
            if role != "anonymous":
                client.cookies.set("SafeData_session", serializer.dumps(build_session_data(users[role], org)))
            resp = client.get(path, follow_redirects=False)
            cells.append(classify(resp.status_code, resp.headers.get("location")))
        rows.append(f"| `{route.path}` | " + " | ".join(cells) + " |")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "# Access Matrix (current roles, GET pages)\n\n"
        "Generated by `tests/audit/test_access_matrix.py`. ALLOWED = page rendered; "
        "DENIED = redirected to login or 401/403.\n\n"
        "| Route | " + " | ".join(ROLES) + " |\n|---|" + "---|" * len(ROLES) + "\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    assert rows, "no routes enumerated"
```

- [ ] **Step 2: Run it**

Run: `cd retention_py; $env:APP_ENV="test"; python -m pytest tests/audit/test_access_matrix.py -v`
Expected: 2 passed; `docs/audit/evidence/access-matrix.md` exists with one row per GET route.

- [ ] **Step 3: Analyse and record findings**

Open the matrix. For every row where `data_owner` is ALLOWED on an admin/DPO concern (settings, users, integrations, billing, audit, reports, recalculations) add a finding (dimension 04, High) to `docs/audit/findings.md` with the matrix as evidence. For every ERROR cell add a finding (dimension 07, High).

- [ ] **Step 4: Commit**

```bash
git add retention_py/tests/audit/test_access_matrix.py docs/audit/evidence/access-matrix.md docs/audit/findings.md
git commit -m "feat(audit): route x role access matrix + findings"
```

---

### Task 4: Cross-tenant isolation probe

Depends on Phase 1A Task 1.

**Files:**
- Create: `retention_py/tests/audit/test_tenant_isolation_probe.py`
- Output: `docs/audit/evidence/isolation-probe.md`

**Interfaces:**
- Consumes: same fixtures and helpers as Task 3.

- [ ] **Step 1: Write the probe**

```python
# retention_py/tests/audit/test_tenant_isolation_probe.py
"""Org A admin requests every id-bearing route with Org B's ids. Anything other than
404/403/redirect is a cross-tenant exposure and is written to the evidence file."""
from pathlib import Path

from fastapi.routing import APIRoute

from app.auth import build_session_data, hash_password, serializer
from app.models import (Attachment, DataCategory, DataRecord, Organization, RopaEntry, User)
from main import app

OUT = Path(__file__).resolve().parents[3] / "docs" / "audit" / "evidence" / "isolation-probe.md"


def test_probe(db, client):
    org_a = db.get(Organization, 1)
    org_a.status = org_a.subscription_status = "active"
    org_b = Organization(name="Victim Org", slug="victim", primary_domain="victim.test",
                         country="GB", tier="core", status="active", subscription_status="active")
    db.add(org_b)
    db.commit()
    admin_a = User(organization_id=org_a.id, name="A admin", email="a@test.local",
                   password_hash=hash_password("Xyq9$mNpL2!k"), role="admin", is_active=True,
                   email_verified_at=org_a.created_at)
    admin_b = User(organization_id=org_b.id, name="B admin", email="b@victim.test",
                   password_hash=hash_password("Xyq9$mNpL2!k"), role="admin", is_active=True,
                   email_verified_at=org_b.created_at)
    db.add_all([admin_a, admin_b])
    db.commit()
    cat_b = DataCategory(organization_id=org_b.id, name="B secret cat", retention_period_days=30)
    db.add(cat_b)
    db.commit()
    rec_b = DataRecord(organization_id=org_b.id, category_id=cat_b.id, record_reference="B-SECRET-1")
    ropa_b = RopaEntry(organization_id=org_b.id, activity_name="B secret activity")
    db.add_all([rec_b, ropa_b])
    db.commit()
    att_b = Attachment(organization_id=org_b.id, record_id=rec_b.id, original_filename="b.pdf",
                       stored_filename="b.pdf", file_size=1, mime_type="application/pdf")
    db.add(att_b)
    db.commit()
    ids = {"id": rec_b.id, "record_id": rec_b.id, "entry_id": ropa_b.id, "uid": admin_b.id}

    client.cookies.set("SafeData_session", serializer.dumps(build_session_data(admin_a, org_a)))
    leaks, checked = [], 0
    for route in app.routes:
        if not isinstance(route, APIRoute) or "GET" not in route.methods or "{" not in route.path:
            continue
        path = route.path
        for k, v in ids.items():
            path = path.replace("{" + k + "}", str(v))
        if route.path.startswith("/attachments/download/"):
            path = f"/attachments/download/{att_b.id}"
        if "{" in path:
            continue
        checked += 1
        resp = client.get(path, follow_redirects=False)
        body = resp.text if resp.status_code == 200 else ""
        if resp.status_code == 200 and any(s in body for s in ("B-SECRET-1", "B secret", "victim.test")):
            leaks.append(f"| `{route.path}` | {resp.status_code} | Org B data rendered |")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        f"# Cross-tenant Isolation Probe\n\nRoutes checked: {checked}. Leaks: {len(leaks)}.\n\n"
        "| Route | Status | Result |\n|---|---|---|\n" + ("\n".join(leaks) or "| — | — | no leaks |") + "\n",
        encoding="utf-8",
    )
    assert checked > 0
```

- [ ] **Step 2: Run it**

Run: `cd retention_py; $env:APP_ENV="test"; python -m pytest tests/audit/test_tenant_isolation_probe.py -v`
Expected: PASS (the probe records, it does not fail on leaks); evidence file written.

- [ ] **Step 3: Record findings** — each leak row becomes a **Critical** dimension-04 finding.

- [ ] **Step 4: Commit**

```bash
git add retention_py/tests/audit/test_tenant_isolation_probe.py docs/audit/evidence/isolation-probe.md docs/audit/findings.md
git commit -m "feat(audit): cross-tenant isolation probe + findings"
```

---

### Task 5: Git-history database blob inspector (decision S4)

**Files:**
- Create: `tools/audit/inspect_history_blobs.py`
- Test: `retention_py/tests/audit/test_inspect_history_blobs.py`
- Output: `docs/audit/evidence/history-blobs.md`

**Interfaces:**
- Produces: `classify_emails(emails: list[str]) -> dict[str,int]` with keys `test_like`, `real_like`; `summarise_sqlite(path: Path) -> dict` with `tables: dict[str,int]` (row counts) and `email_classes: dict[str,int]` — **never values**.

- [ ] **Step 1: Write the failing test**

```python
# retention_py/tests/audit/test_inspect_history_blobs.py
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.audit.inspect_history_blobs import classify_emails, summarise_sqlite  # noqa: E402


def test_classify_emails():
    c = classify_emails(["a@test.com", "b@example.com", "x@test.local", "ceo@realbank.ng"])
    assert c == {"test_like": 3, "real_like": 1}


def test_summary_contains_no_values(tmp_path):
    db = tmp_path / "x.db"
    con = sqlite3.connect(db)
    con.execute("create table users (id integer, email text)")
    con.execute("insert into users values (1, 'ceo@realbank.ng')")
    con.commit()
    con.close()
    s = summarise_sqlite(db)
    assert s["tables"] == {"users": 1}
    assert s["email_classes"] == {"test_like": 0, "real_like": 1}
    assert "realbank" not in repr(s)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd retention_py; python -m pytest tests/audit/test_inspect_history_blobs.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```python
# tools/audit/inspect_history_blobs.py
"""Find .db files ever committed, extract each blob OUTSIDE the repo, and summarise
(table row counts + email classification). Never prints or writes actual values."""
from __future__ import annotations

import argparse
import re
import sqlite3
import subprocess
from pathlib import Path

TEST_DOMAINS = re.compile(r"@(test|example)\.|\.local$|\.test$|@localhost", re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def classify_emails(emails: list[str]) -> dict[str, int]:
    test_like = sum(1 for e in emails if TEST_DOMAINS.search(e))
    return {"test_like": test_like, "real_like": len(emails) - test_like}


def summarise_sqlite(path: Path) -> dict:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
        counts, emails = {}, []
        for t in tables:
            counts[t] = con.execute(f'select count(*) from "{t}"').fetchone()[0]
            cols = [r[1] for r in con.execute(f'pragma table_info("{t}")')]
            for c in cols:
                if "email" in c.lower():
                    emails += [r[0] for r in con.execute(f'select "{c}" from "{t}"') if r[0]]
        emails = [e for e in emails if EMAIL_RE.fullmatch(str(e))]
        return {"tables": counts, "email_classes": classify_emails(emails)}
    finally:
        con.close()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--scratch", required=True, help="directory OUTSIDE the repo")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    repo, scratch = Path(a.repo).resolve(), Path(a.scratch).resolve()
    if repo in scratch.parents or scratch == repo:
        raise SystemExit("scratch dir must be outside the repository")
    scratch.mkdir(parents=True, exist_ok=True)
    lines = ["# Database blobs in Git history", "",
             "| Commit | Path | Tables (rows) | Emails test-like / real-like |", "|---|---|---|---|"]
    seen = set()
    for row in _git(repo, "rev-list", "--all", "--objects").splitlines():
        parts = row.split(" ", 1)
        if len(parts) != 2 or not parts[1].endswith(".db") or parts[0] in seen:
            continue
        sha, p = parts
        seen.add(sha)
        blob = scratch / f"{sha}.db"
        blob.write_bytes(subprocess.run(["git", "-C", str(repo), "cat-file", "-p", sha],
                                        check=True, capture_output=True).stdout)
        try:
            s = summarise_sqlite(blob)
            tbl = ", ".join(f"{k}({v})" for k, v in s["tables"].items() if v)
            ec = s["email_classes"]
            lines.append(f"| `{sha[:8]}` | `{p}` | {tbl} | {ec['test_like']} / {ec['real_like']} |")
        except sqlite3.DatabaseError:
            lines.append(f"| `{sha[:8]}` | `{p}` | not a SQLite file | — |")
    Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {a.out}; blobs kept in {scratch} (delete after review)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests** — `python -m pytest tests/audit/test_inspect_history_blobs.py -v` → 2 passed.

- [ ] **Step 5: Run against the repo** (scratch = the session scratchpad directory, never inside the repo)

Run: `python ../tools/audit/inspect_history_blobs.py --repo .. --scratch "<scratchpad>/blobs" --out ../docs/audit/evidence/history-blobs.md`

- [ ] **Step 6: Decide S4** — if any blob shows `real_like > 0`, add a **High** finding SD-10-003 "Personal data in Git history" with the recommendation "rewrite history with git filter-repo, force-push, rotate secrets, collaborators re-clone" and flag it in the decision pack; otherwise record "history keeps test data only; no rewrite (S4 resolved)". Delete the scratch blobs.

- [ ] **Step 7: Commit**

```bash
git add tools/audit/inspect_history_blobs.py retention_py/tests/audit/test_inspect_history_blobs.py docs/audit/evidence/history-blobs.md docs/audit/findings.md
git commit -m "feat(audit): git-history db blob inspector (redacted) + S4 evidence"
```

---

### Task 6: Security, dependency and compliance-correctness review

**Files:**
- Output: `docs/audit/evidence/pip-audit.txt`, `docs/audit/evidence/bandit.txt`, `docs/audit/evidence/headers.md`, `docs/audit/evidence/jurisdiction-review.md`
- Modify: `docs/audit/findings.md`

- [ ] **Step 1: Dependency vulnerabilities**

Run: `cd retention_py; pip install pip-audit bandit; pip-audit -r requirements.txt > ../docs/audit/evidence/pip-audit.txt`
Each vulnerable package → finding (dim 04; severity from advisory: critical/high → High, else Medium).

- [ ] **Step 2: Static security scan**

Run: `bandit -r app -q -f txt -o ../docs/audit/evidence/bandit.txt`
Triage every Medium/High bandit item: real issue → finding; false positive → note in the evidence file under "Triaged as false positive" with reason.

- [ ] **Step 3: Header and session review** — start the app on a test DB (`$env:APP_ENV="local"; $env:DATABASE_URL="sqlite:///./audit_tmp.db"; python main.py`), then `curl -sI http://127.0.0.1:8200/login` and record the response headers in `headers.md`. Check against ASVS L2 V3/V14: HSTS (prod only — note), CSP (`style-src 'unsafe-inline'` → Medium finding until Phase 2 removes inline styles), cookie flags (`HttpOnly`, `Secure` in prod, `SameSite=Lax`), no `Server` version leak. Stop the server and delete `audit_tmp.db`.

- [ ] **Step 4: Jurisdiction correctness** — for each law in `COUNTRY_REGULATION_MAP` (`app/helpers.py:7`) build a table in `jurisdiction-review.md`: law · DSAR deadline in code vs statute · breach window in code vs statute · child consent age · number of seeded categories · categories with a legal citation. Source statutory values from the official regulator site of each law and cite the URL per row. Every mismatch → dimension-02 finding (High if it would make a customer miss a statutory deadline).

- [ ] **Step 5: Commit**

```bash
git add docs/audit
git commit -m "docs(audit): security, dependency and jurisdiction correctness evidence"
```

---

### Task 7: Experience, accessibility, operations and documentation review

**Files:**
- Output: `docs/audit/evidence/screens/<role>/<page>.png`, `docs/audit/evidence/a11y.md`, `docs/audit/evidence/ops-devops-docs.md`
- Modify: `docs/audit/findings.md`

- [ ] **Step 1: Seed a demo dataset on a throwaway SQLite DB** — `$env:DATABASE_URL="sqlite:///./audit_demo.db"; python main.py` then register via `/register` one org (domain `demo-audit.test`), create users for `dpo` and `data_owner` from `/users`, create 3 categories and 10 records through the UI. Use only invented names.

- [ ] **Step 2: Screenshot every navigation page per role** using Playwright (MCP `browser_navigate` + `browser_take_screenshot`, or `npx playwright screenshot`) at 1440×900 and 390×844 (mobile). Save as `screens/<role>/<page>-<desktop|mobile>.png`.

- [ ] **Step 3: UX heuristics per page** — for each screenshot record in `findings.md` (dimension 01) any: missing empty state, unclear primary action, jargon without explanation, destructive action without consequence text, inconsistent naming, broken mobile layout. Reference the screenshot path as evidence.

- [ ] **Step 4: Accessibility** — run axe on login, dashboard, records, records view, categories, settings (Playwright: inject `https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js` then `axe.run()`); write violations to `a11y.md`; each serious/critical violation → dimension-12 finding (High).

- [ ] **Step 5: Operations / DevOps / docs** — in `ops-devops-docs.md` answer with evidence: backups location and restore procedure exists? monitoring/alerting? health check depth (`/healthz` checks DB?) CI present? environments? secrets handling? README claims vs reality (list each claim in `README.md` and `Documents/01–06` not backed by a route/UI → dimension-13 finding). Delete `audit_demo.db` afterwards.

- [ ] **Step 6: Commit**

```bash
git add docs/audit
git commit -m "docs(audit): UX screenshots, accessibility, ops/devops/docs evidence"
```

---

### Task 8: Write the 14-dimension audit report

**Files:**
- Create: `docs/audit/2026-10-audit-report.md`

- [ ] **Step 1: Write the report** with this exact structure:

```markdown
# SafeData by 3Consulting — Production Readiness Audit (October 2026)

## 1. Summary for decision-makers
- One paragraph: overall readiness, in plain language.
- Counts table: Critical / High / Medium / Low, open per dimension.
- The five things that must be fixed before any customer data is accepted.

## 2. Method
Tools and evidence (link each file in docs/audit/evidence/), roles tested, standards used
(OWASP ASVS 4.0.3 Level 2, WCAG 2.2 AA, GDPR/NDPA/… statutory texts), date and commit audited.

## 3–16. One section per dimension (01 … 14)
For each: what good looks like for SafeData's customers · what we found (finding ids, each
with one-sentence plain-language impact) · what we will do and in which phase.

## 17. What each user sees today vs. what they should see
Table per role × level from the access matrix and screenshots vs. spec §7.3.

## 18. Closure tracking
How Phase 6 re-runs the tools and how a finding is closed (commit + evidence).
```

- [ ] **Step 2: Self-check** — search the report for every sentence stating a fact about the system; each must cite a finding id or evidence file. Remove or evidence any that do not.

- [ ] **Step 3: Commit**

```bash
git add docs/audit/2026-10-audit-report.md
git commit -m "docs(audit): 14-dimension production readiness report"
```

---

### Task 9: Pricing & packaging document

**Files:**
- Create: `Documents/launch/01_PRICING_AND_PACKAGING.md`

- [ ] **Step 1: Competitor scan** — use WebSearch (`mode: "extended"`) for current public pricing of OneTrust, Osano, DataGrail, Usercentrics, Cookiebot, Securiti, TrustArc, and two Africa-focused privacy tools; record name, what they sell, entry price, pricing metric, source URL and date. Note where pricing is "contact sales".

- [ ] **Step 2: Write the document** with sections: Pricing principles (fairness, never price on categories, frozen local prices, band by billing country) · Products and plans (spec §6.1 table, marked DRAFT) · Feature inclusion (spec §6.2) · Regional bands (A–D definitions, World Bank source URL + date, 15 example countries per band) · Local price books for USD, EUR, GBP, NGN, GHS, KES, ZAR, EGP, INR, BRL, AED, CAD, AUD, SGD, XOF (monthly + yearly, every plan; show reference FX rate and date; round to natural local figures) · Equity programmes · Expert services price list (DPIA done-for-you, gap assessment, DPO-as-a-service, banded) · Competitor comparison table · Unit economics (hosting cost per customer from Task 11, payment fees: Paystack and Stripe published rates with source URL, gross margin per plan per band) · Price review policy (quarterly, >10% FX trigger, first review after 20 paying customers or 90 days).

- [ ] **Step 3: Check** — every local price shows FX rate + date; every competitor figure has a URL + date; DRAFT label present on all prices.

- [ ] **Step 4: Commit**

```bash
git add Documents/launch/01_PRICING_AND_PACKAGING.md
git commit -m "docs(launch): pricing and packaging (draft prices, bands, price books)"
```

---

### Task 10: Payments & billing options document

**Files:**
- Create: `Documents/launch/02_PAYMENTS_AND_BILLING_OPTIONS.md`

- [ ] **Step 1: Verify facts** with WebSearch/WebFetch and record source URLs + date: (a) Stripe supported countries (official `stripe.com/global`); (b) Paystack international card acceptance and USD settlement for Nigerian businesses, fees; (c) Paddle seller eligibility and payout methods for Nigeria (official Paddle docs; if unclear, write the exact question to send Paddle support); (d) Lemon Squeezy seller payout countries; (e) UK Ltd formation cost/time at Companies House (official gov.uk) and UK registered-office requirement.

- [ ] **Step 2: Write** sections: Plain-language summary · Why a company (not a person) must be the seller · Option A Paystack now (what it covers, fees, settlement) · Option B UK Ltd + Stripe (steps, cost, timeline, accountant check) · Option C Merchant of Record (Paddle/Lemon Squeezy; fees; payout status for Nigeria with evidence; what remains unknown) · Comparison table (coverage, local methods, tax handling, fees, setup time, risk) · Recommendation (Paystack at launch → Paddle if payouts confirmed, else UK Ltd + Stripe) · Actions for 3Consulting with owners.

- [ ] **Step 3: Commit**

```bash
git add Documents/launch/02_PAYMENTS_AND_BILLING_OPTIONS.md
git commit -m "docs(launch): payments and billing options with verified sources"
```

---

### Task 11: Hosting, domain and cost model document

**Files:**
- Create: `Documents/launch/03_HOSTING_DOMAIN_AND_COST_MODEL.md`

- [ ] **Step 1: Verify current prices** (WebFetch official pricing pages, record URL + date): Render web service + background worker + Postgres (Frankfurt), DigitalOcean App Platform + Managed Postgres (Frankfurt) as alternative, Cloudflare free/pro, Cloudflare R2, Postmark and Brevo, Sentry, an uptime/status page service, domain registration for a `.com`.

- [ ] **Step 2: Write** sections: Plain-language summary · Why the app cannot run on InMotion shared hosting (cite InMotion community answers) and what shared hosting can do (static marketing site) · Domain vs hosting explained · Launch architecture diagram (ASCII) · Monthly cost table at launch, at 50 customers, at 500 customers · Data residency (EU region) and what to tell customers · Domain plan: `safedata.3consult-ng.com` now, standalone domain later, migration steps (config + 301) · DNS records needed at InMotion (CNAME for app, SPF/DKIM/DMARC for mail subdomain) · Risks and mitigations (spec R12).

- [ ] **Step 3: Commit**

```bash
git add Documents/launch/03_HOSTING_DOMAIN_AND_COST_MODEL.md
git commit -m "docs(launch): hosting, domain and cost model with sourced prices"
```

---

### Task 12: Consent Management explained

**Files:**
- Create: `Documents/launch/04_CONSENT_MANAGEMENT_EXPLAINED.md`

- [ ] **Step 1: Write** for a non-technical reader: What consent is (one paragraph) · The Ada and Acme story (spec §5 explanation, expanded into 6 numbered steps with a simple diagram) · What SafeData records and what it deliberately does not (data minimisation) · How withdrawal connects to automatic deletion (the differentiator) · How it differs from a cookie banner (and why the banner comes later) · What a customer must do on their side (shared responsibility) · Glossary (purpose, notice, lawful basis, receipt, preference centre, data subject, DSAR).

- [ ] **Step 2: Commit**

```bash
git add Documents/launch/04_CONSENT_MANAGEMENT_EXPLAINED.md
git commit -m "docs(launch): consent management explained in plain language"
```

---

### Task 13: Executive decision pack and go-to-market checklist

**Files:**
- Create: `Documents/launch/00_EXECUTIVE_DECISION_PACK.md`
- Create: `Documents/launch/05_GO_TO_MARKET_AND_LAUNCH_CHECKLIST.md`

- [ ] **Step 1: Write the decision pack** (max ~6 pages): What SafeData is (tagline, two products) · Where it stands today (audit summary counts + top 5 must-fix) · What we will build and when (phases, plain language) · Decisions needed from stakeholders — S1–S6 from spec §15, each with: the question, options, recommendation, cost, deadline · Budget summary (hosting, legal review, pen test, UK Ltd or Paddle, insurance) · Risks (top 6 from spec §16) · Links to documents 01–05 and the audit report.

- [ ] **Step 2: Write the go-to-market checklist**: positioning statement; ideal customer profiles (establishing vs established; industries); launch channels (3Consulting clients, free gap check, partners); sales materials to refresh (one-pager, deck — reuse `Documents/SafeData_Case_Study_3Consulting.pptx` structure); support model (S6 recommendation); legal pack readiness; go-live gates (spec §14 Phase 6); first-90-days metrics (sign-ups, activation = first category + 10 records, trial→paid, churn).

- [ ] **Step 3: Commit**

```bash
git add Documents/launch/00_EXECUTIVE_DECISION_PACK.md Documents/launch/05_GO_TO_MARKET_AND_LAUNCH_CHECKLIST.md
git commit -m "docs(launch): executive decision pack and go-to-market checklist"
```

---

### Task 14: Render stakeholder PDFs and final review

**Files:**
- Modify: `Documents/convert_to_pdf.py` (accept a source directory argument)
- Output: `Documents/launch/PDFs/*.pdf`

- [ ] **Step 1: Add a `--src` argument** to `convert_to_pdf.py` so it converts `Documents/launch/*.md` into `Documents/launch/PDFs/`. Replace the module-level `SCRIPT_DIR`/`PDF_DIR` usage with:

```python
import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--src", default=os.path.dirname(os.path.abspath(__file__)))
args = ap.parse_args()
SCRIPT_DIR = os.path.abspath(args.src)
PDF_DIR = os.path.join(SCRIPT_DIR, "PDFs")
os.makedirs(PDF_DIR, exist_ok=True)
```

- [ ] **Step 2: Render** — `python Documents/convert_to_pdf.py --src Documents/launch`. Open each PDF; confirm currency symbols (₦, ₵, €, £, ₹) render. If a glyph is missing, set the body font in `PDF_STYLE` to a bundled TTF that has them (DejaVu Sans) via `@font-face` and re-render.

- [ ] **Step 3: Final consistency pass** — names (SafeData by 3Consulting), domain (`safedata.3consult-ng.com`), prices identical across 00/01, recommendations identical across 00/02/03 and spec §15.

- [ ] **Step 4: Commit**

```bash
git add Documents/convert_to_pdf.py Documents/launch
git commit -m "docs(launch): stakeholder PDFs"
```
