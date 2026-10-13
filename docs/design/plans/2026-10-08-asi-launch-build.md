# ASI Launch Build Implementation Plan

**Goal:** Turn the ASI repository into a launch-ready, organised news & intelligence platform: server-rendered public
site (SEO-complete) on the existing design, a full editorial admin panel, pictures, Big Story curation, admin-controlled
Market Snapshot and Live Ticker, all 54 countries, a working newsletter, and a single-VM production deployment.

**Architecture:** One FastAPI service (`apps/api`) serves both the JSON API and the Jinja2-rendered public site from a
shared services layer, so honesty/visibility rules live in one place. A React SPA (`apps/admin`) is the editorial panel,
same-origin with `/admin/*` via a proxy (Vite in dev, Caddy in prod) so auth uses an httpOnly cookie. Postgres/Timescale,
Redis, MinIO and Airflow as today; Caddy terminates HTTPS in production.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy Core (raw SQL, existing pattern), Alembic, Jinja2, markdown-it-py, nh3,
Pillow, pyotp, cryptography, gunicorn/uvicorn, Redis, TimescaleDB pg16, MinIO, Airflow 2.9; React 18 + Vite 5 +
react-router 6; Caddy 2; GitHub Actions; pytest.

**Spec:** `docs/design/specs/2026-10-08-asi-launch-build-design.md`

## Global Constraints

- Article section values stay `Markets` / `Regulation` in `content.articles.tag`; public URLs `/markets/{slug}`, `/regulation/{slug}`.
- Role DB values stay `author` / `editor` / `admin`; UI label for `author` is **Writer**.
- An author can never publish their own article; nothing publishes with 0 sources (existing rules, keep tests green).
- Unverified/pending figures are never returned or rendered as numbers — only the pending note.
- A live value past its feed's `stale_after_minutes` is labelled **Delayed**, never **Live**.
- Public "is live" predicate for articles everywhere: `status IN ('published','scheduled') AND published_at <= now()`.
- All new DDL in Alembic revision `0003` (idempotent: `IF NOT EXISTS`, `ON CONFLICT DO NOTHING`, `DO $$ … duplicate_object`); `db/init/001_schemas.sql` stays the base schema.
- Images: JPEG/PNG/WebP, ≤ 10 MB, ≤ 40 megapixels; WebP variants 480/800/1200/1600; social card 1200×630 JPEG; EXIF stripped.
- Production refuses to start if any of `JWT_SECRET`, `POSTGRES_PASSWORD`, `S3_SECRET_KEY` is a known dev default.
- Design tokens/fonts from `frontend/styles.css` are preserved (ink `#1B1916`, paper `#F3EEE1`, ochre `#C7862B`, forest `#2B5D45`, rust `#93412A`; Fraunces / IBM Plex Sans / IBM Plex Mono).
- Default editorial timezone `Africa/Lagos`; all storage in UTC.
- Domain: `africastablecoinintelligence.com`; admin at `admin.africastablecoinintelligence.com`.

## Review Focus

1. **Hostile article Markdown** (raw `<script>`, `javascript:` links, `onerror=` attributes, iframes) → rendered output contains none of it; links get `rel="nofollow noopener"`. Test in Task 6.
2. **Non-ASCII titles and country names** ("Côte d'Ivoire", "São Tomé and Príncipe", "Naira à 1,600") → slugs are ASCII kebab-case and pages resolve. Test in Tasks 2 and 6.
3. **Empty launch database** (no articles, no pipeline data, no curation) → Home, sections, countries, feeds and sitemaps all render 200 with empty states; no 500s. Test in Tasks 15 and 18.
4. **Messy subscriber emails** (`"  Reader@Example.COM "`, previously unsubscribed address re-subscribing) → normalised, and a fresh confirmation is sent; unsubscribed address re-enters as pending. Test in Task 8.
5. **Awkward images** (CMYK JPEG, PNG with alpha, EXIF-rotated photo, a file renamed `.jpg` that is really text) → first three processed correctly (RGB, alpha flattened for JPEG card, upright); the fake is rejected with 422. Test in Task 11.

---

## File Structure (target)

```
.
├── apps/
│   ├── api/
│   │   ├── Dockerfile, requirements.txt, requirements-dev.txt, pytest.ini, alembic.ini, gunicorn.conf.py
│   │   ├── alembic/versions/0001_baseline.py, 0002_…py, 0003_launch_platform.py
│   │   ├── app/
│   │   │   ├── main.py                 # app factory: middleware, routers, static, templates, errors
│   │   │   ├── core/ settings.py db.py cache.py email.py security.py audit.py text.py middleware.py storage.py
│   │   │   ├── services/ countries.py live.py snapshot.py articles.py markdown.py media.py homepage.py
│   │   │   │             newsletter.py site_text.py search.py views.py seo.py
│   │   │   ├── api/public/ home.py metrics.py news.py countries.py regulatory.py newsletter.py
│   │   │   ├── api/admin/  auth.py users.py articles.py media.py homepage.py snapshot.py metrics.py fx.py
│   │   │   │               countries.py regulatory.py newsletter.py site_text.py flags.py dashboard.py audit.py
│   │   │   ├── site/ routes.py context.py templates/… static/{css,js,fonts,img}
│   │   │   ├── seo/ routes.py
│   │   │   └── cli/ bootstrap_admin.py seed_demo.py migrate.py send_issue.py regenerate_media.py
│   │   └── tests/ …
│   └── admin/ (Vite React SPA)
├── pipelines/ Dockerfile, dags/*.py
├── db/init/001_schemas.sql
├── infra/ docker-compose.prod.yml, Caddyfile, backup/{Dockerfile,backup.sh,restore.sh}, .env.prod.example
├── docs/ product/, reference/, ARCHITECTURE.md, DEPLOYMENT.md, LAUNCH_CHECKLIST.md, EDITORIAL_GUIDE.md, design/
├── docker-compose.yml, Makefile, README.md, .env.example, .gitignore, .editorconfig
└── .github/ workflows/ci.yml, dependabot.yml
```

---

## Phase A — Organise

### Task 1: Repository reorganisation (no behaviour change)

**Files:**
- Move: `backend/backend/*` → `apps/api/`; `backend/dags/` → `pipelines/dags/`; `backend/airflow/Dockerfile` → `pipelines/Dockerfile`; `backend/init-db/` → `db/init/`; `backend/docker-compose.yml` → `docker-compose.yml`; `backend/Makefile` → `Makefile`; `backend/.env.example` → `.env.example`; `backend/.gitignore` + `.dockerignore` → root.
- Move: `ASI Documents/*` → `docs/product/`; `backend/ASI Backend Build package/*` → `docs/reference/backend-build-packages/`; `frontend/` → `docs/reference/frontend-prototype/` (its design is ported in Phase D).
- Modify: `docker-compose.yml` paths (`./apps/api`, `./pipelines`, `./db/init`), `apps/api/app/migrate.py` (`INIT_DB_DIR` env-overridable, default `/app/db/init` in container), `.github/workflows/ci.yml` paths, `Makefile`.
- Fix: `apps/api/tests/test_newsletter.py` missing `from app.main import app`.
- Delete: all `__pycache__` dirs.

**Interfaces:** Produces the layout every later task uses.

- [ ] Step 1: `git mv` everything above; delete `__pycache__`.
- [ ] Step 2: Update compose: api `build.context: ./apps/api`, volume `./apps/api/app:/app/app`, `./apps/api/tests:/app/tests`, `./apps/api/alembic:/app/alembic`, `./db/init:/app/db/init:ro`; postgres `./db/init:/docker-entrypoint-initdb.d`; airflow `build.context: ./pipelines`, `./pipelines/dags:/opt/airflow/dags`.
- [ ] Step 3: CI: `working-directory: apps/api`, `init-db` → `db/init`, compileall on `apps/api/app apps/api/tests pipelines/dags`, YAML check `docker-compose.yml`.
- [ ] Step 4: Fix the newsletter test import.
- [ ] Step 5: Start Docker; `docker compose up -d --build postgres redis mailhog minio minio-init api`; `docker compose exec api pytest` → all pass (baseline).
- [ ] Step 6: Commit `chore: reorganise repo into apps/, pipelines/, db/, docs/`.

---

## Phase B — Data model & services

### Task 2: Migration 0003 — launch platform schema + seeds

**Files:**
- Create: `apps/api/alembic/versions/0003_launch_platform.py`, `apps/api/app/core/text.py`
- Test: `apps/api/tests/test_schema_seed.py`, `apps/api/tests/test_text.py`

**Interfaces:**
- Produces `app.core.text.slugify(value: str) -> str` (NFKD → ASCII, lowercase, non-alnum → `-`, trimmed, max 120 chars) and `reading_minutes(md: str) -> int` (words/220, min 1).
- Produces tables (all in spec §6): `content.countries`, `content.regulators`, `content.article_revisions`, `content.article_reviews`, `content.slug_redirects`, `content.media`, `content.article_media_links`, `content.homepage_slots`, `content.breaking_banner`, `market_data.live_feeds`, `site.snapshot_cards`, `site.ticker_items`, `site.site_text`, `auth.password_tokens`, `audit.admin_log`, `newsletter.deliveries`; new columns on `content.articles`, `content.regulatory_entries` (`is_published BOOLEAN DEFAULT true`), `market_data.verified_annual_stats` (`label`, `badge`, `sample_note`), `auth.users`, newsletter tables. `articles_status_check` widened to include `scheduled`.

DDL essentials (exact):

```sql
CREATE SCHEMA IF NOT EXISTS site; CREATE SCHEMA IF NOT EXISTS audit;
CREATE TABLE IF NOT EXISTS content.countries (
  code TEXT PRIMARY KEY CHECK (code ~ '^[A-Z]{2}$'), name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
  currency TEXT, region TEXT NOT NULL CHECK (region IN ('North','West','Central','East','Southern')),
  status TEXT NOT NULL DEFAULT 'researching' CHECK (status IN ('in_force','developing','researching')),
  coverage TEXT NOT NULL DEFAULT 'monitoring' CHECK (coverage IN ('active','monitoring')),
  summary TEXT, compliance_md TEXT, sort_order INT NOT NULL DEFAULT 100,
  updated_by INT REFERENCES auth.users(id), updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS content.regulators (
  id SERIAL PRIMARY KEY, country_code TEXT NOT NULL REFERENCES content.countries(code) ON DELETE CASCADE,
  name TEXT NOT NULL, abbreviation TEXT, scope TEXT, website_url TEXT, register_url TEXT, sort_order INT NOT NULL DEFAULT 100);
ALTER TABLE content.articles
  ADD COLUMN IF NOT EXISTS seo_description TEXT, ADD COLUMN IF NOT EXISTS cover_media_id INT,
  ADD COLUMN IF NOT EXISTS correction_md TEXT, ADD COLUMN IF NOT EXISTS correction_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS view_count BIGINT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS search_vector tsvector GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title,'')), 'A') ||
    setweight(to_tsvector('english', coalesce(dek,'')), 'B') ||
    setweight(to_tsvector('english', coalesce(body_md,'')), 'C')) STORED;
CREATE INDEX IF NOT EXISTS articles_search_idx ON content.articles USING GIN (search_vector);
ALTER TABLE content.articles DROP CONSTRAINT IF EXISTS articles_status_check;
ALTER TABLE content.articles ADD CONSTRAINT articles_status_check
  CHECK (status IN ('draft','in_review','scheduled','published'));
CREATE TABLE IF NOT EXISTS content.media (
  id SERIAL PRIMARY KEY, object_key TEXT NOT NULL UNIQUE, original_filename TEXT,
  width INT NOT NULL, height INT NOT NULL, alt_text TEXT NOT NULL DEFAULT '', caption TEXT, credit TEXT,
  licence TEXT NOT NULL DEFAULT 'own' CHECK (licence IN ('own','licensed','creative_commons','public_domain','courtesy')),
  licence_note TEXT, focal_x REAL NOT NULL DEFAULT 0.5, focal_y REAL NOT NULL DEFAULT 0.5,
  variants JSONB NOT NULL DEFAULT '{}'::jsonb, uploaded_by INT REFERENCES auth.users(id),
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS content.article_media_links (
  article_id INT NOT NULL REFERENCES content.articles(id) ON DELETE CASCADE,
  media_id INT NOT NULL REFERENCES content.media(id), role TEXT NOT NULL CHECK (role IN ('cover','inline')),
  PRIMARY KEY (article_id, media_id, role));
CREATE TABLE IF NOT EXISTS content.homepage_slots (
  slot TEXT PRIMARY KEY CHECK (slot IN ('lead','secondary_1','secondary_2','markets_lead','regulation_lead')),
  article_id INT REFERENCES content.articles(id) ON DELETE SET NULL, expires_at TIMESTAMPTZ,
  updated_by INT REFERENCES auth.users(id), updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS content.breaking_banner (
  id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1), text TEXT, article_id INT REFERENCES content.articles(id) ON DELETE SET NULL,
  is_active BOOLEAN NOT NULL DEFAULT false, expires_at TIMESTAMPTZ, updated_by INT REFERENCES auth.users(id),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS market_data.live_feeds (
  key TEXT PRIMARY KEY, label TEXT NOT NULL, unit TEXT NOT NULL CHECK (unit IN ('usd','pct')),
  country_code TEXT, source_name TEXT NOT NULL, stale_after_minutes INT NOT NULL);
CREATE TABLE IF NOT EXISTS site.snapshot_cards (
  id SERIAL PRIMARY KEY, zone TEXT NOT NULL CHECK (zone IN ('metrics','countries')),
  kind TEXT NOT NULL CHECK (kind IN ('live','report')),
  live_feed_key TEXT REFERENCES market_data.live_feeds(key),
  report_stat_id INT REFERENCES market_data.verified_annual_stats(id) ON DELETE CASCADE,
  label_override TEXT, is_visible BOOLEAN NOT NULL DEFAULT true, is_highlighted BOOLEAN NOT NULL DEFAULT false,
  sort_order INT NOT NULL DEFAULT 100, updated_by INT REFERENCES auth.users(id), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((kind='live' AND live_feed_key IS NOT NULL) OR (kind='report' AND report_stat_id IS NOT NULL)));
CREATE TABLE IF NOT EXISTS site.ticker_items (
  id SERIAL PRIMARY KEY, live_feed_key TEXT NOT NULL REFERENCES market_data.live_feeds(key), label TEXT NOT NULL,
  is_visible BOOLEAN NOT NULL DEFAULT true, sort_order INT NOT NULL DEFAULT 100,
  updated_by INT REFERENCES auth.users(id), updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS site.site_text (
  key TEXT PRIMARY KEY, value_md TEXT NOT NULL, updated_by INT REFERENCES auth.users(id),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
```
(plus `article_revisions`, `article_reviews`, `slug_redirects`, `password_tokens`, `audit.admin_log`, `newsletter.deliveries`,
users columns `slug UNIQUE, title, bio, avatar_media_id, totp_secret, totp_enabled BOOL DEFAULT false, last_login_at`,
subscriber columns `unsubscribe_token UNIQUE, consent_text`, issue columns `slug UNIQUE, body_md, status, recipient_count,
in_archive`, issue `html_url` made nullable; migrate legacy `content.article_media` rows into `content.media` + links.)

Seeds (all `ON CONFLICT DO NOTHING`): 54 countries (code, name, slug, currency, region; NG/KE/GH/ZA `coverage='active'`;
statuses NG `in_force`, KE `in_force`, GH `developing`, ZA `in_force` — from the Data Source Reference, summary
"Verify before launch"); regulators for NG/KE/GH/ZA from the frontend prototype plus NFIU/FIC/VARO and register URLs;
live feeds `global_supply`(usd, DefiLlama, 90), `usdt_share`(pct, DefiLlama, 90), `usdc_share`(pct, DefiLlama, 90),
`premium_NG`(pct, Quidax vs CBN, 30), `premium_KE`(pct, Luno vs CBK, 30), `premium_ZA`(pct, VALR vs SARB, 30);
`verified_annual_stats` labels/badges: ssa → "Sub-Saharan Africa on-chain value"/Report, ownership → "Crypto-active
Africans holding stablecoins"/Survey/"n=4,658", NG → "Nigeria on-chain value, #1 in Africa"; snapshot cards
reproducing the mockup (metrics: live global_supply, report ssa, report NG, report ownership; countries: NG highlighted,
ZA, KE, GH); ticker: premium_NG "NGN · USDT premium", premium_KE, premium_ZA, global_supply "Global stablecoin supply"
(GH absent — no feed); site_text keys `hero_eyebrow`, `hero_headline`, `hero_intro`, `newsletter_pitch`, `about_short`,
`about_page`, `methodology_page`, `editorial_policy_page`, `corrections_page`, `privacy_page`, `terms_page`,
`contact_page`, `footer_blurb`, `disclaimer` with launch drafts.

- [ ] Step 1: Write `tests/test_text.py`:

```python
from app.core.text import slugify, reading_minutes

def test_slugify_transliterates_and_kebabs():
    assert slugify("Côte d'Ivoire") == "cote-d-ivoire"
    assert slugify("São Tomé and Príncipe") == "sao-tome-and-principe"
    assert slugify("  Naira à 1,600 — what next?  ") == "naira-a-1-600-what-next"

def test_slugify_never_empty():
    assert slugify("!!!") == "untitled"

def test_reading_minutes():
    assert reading_minutes("word " * 10) == 1
    assert reading_minutes("word " * 1100) == 5
```

- [ ] Step 2: Write `tests/test_schema_seed.py`:

```python
from sqlalchemy import text

def test_all_54_countries_seeded_with_unique_slugs(db_session):
    rows = db_session.execute(text("SELECT code, slug, coverage FROM content.countries")).all()
    assert len(rows) == 54
    assert len({r.slug for r in rows}) == 54
    assert {r.code for r in rows if r.coverage == "active"} == {"NG", "KE", "GH", "ZA"}

def test_snapshot_seed_reproduces_mockup(db_session):
    rows = db_session.execute(text(
        "SELECT zone, kind, is_highlighted FROM site.snapshot_cards ORDER BY zone, sort_order")).all()
    assert [r.kind for r in rows if r.zone == "metrics"] == ["live", "report", "report", "report"]
    assert sum(1 for r in rows if r.zone == "countries") == 4
    assert sum(1 for r in rows if r.zone == "countries" and r.is_highlighted) == 1

def test_ticker_seed_uses_only_existing_live_feeds(db_session):
    n = db_session.execute(text("""SELECT COUNT(*) FROM site.ticker_items t
        LEFT JOIN market_data.live_feeds f ON f.key = t.live_feed_key WHERE f.key IS NULL""")).scalar()
    assert n == 0

def test_scheduled_is_a_valid_article_status(db_session):
    check = db_session.execute(text("""SELECT pg_get_constraintdef(oid) FROM pg_constraint
        WHERE conname = 'articles_status_check'""")).scalar()
    assert "scheduled" in check
```

- [ ] Step 3: Run → FAIL (module/tables missing).
- [ ] Step 4: Implement `core/text.py` and migration `0003`.
- [ ] Step 5: `docker compose exec api alembic upgrade head` twice (idempotence) → then tests PASS.
- [ ] Step 6: Commit `feat(db): launch platform schema and seeds`.

### Task 3: Core package — settings, secrets guard, email, middleware

**Files:**
- Create: `apps/api/app/core/{settings,db,cache,email,middleware,audit,storage}.py` (move + extend existing `settings.py`, `db.py`, `cache.py`, `email.py`, `rate_limit.py` → `core/`), `apps/api/app/main.py` (app factory)
- Test: `apps/api/tests/test_core.py`

**Interfaces:**
- `core.settings`: existing names + `SITE_URL` (canonical public URL, default `http://localhost:8000`), `ADMIN_URL`, `SITE_NAME="Africa Stablecoin Intelligence"`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_STARTTLS`, `ALERT_EMAIL_TO`, `GOOGLE_SITE_VERIFICATION`, `BING_SITE_VERIFICATION`, `ANALYTICS_SCRIPT_URL`, `ANALYTICS_DOMAIN`, `INDEXNOW_KEY`, `MEDIA_ORIGINALS_BUCKET`, `COOKIE_SECURE`, `SENTRY_DSN`, `EDITORIAL_TZ="Africa/Lagos"`; `check_production_secrets(env: dict) -> list[str]` returning the names of unsafe settings; module raises `RuntimeError` listing them when `ENVIRONMENT=production`.
- `core.email.send_email(to: str, subject: str, text_body: str, html_body: str | None = None, headers: dict | None = None) -> None` (STARTTLS + login when configured).
- `core.audit.log_action(db, user_id: int | None, action: str, entity: str, entity_id: str | int | None, detail: dict | None = None) -> None` (inserts, no commit).
- `core.storage.Storage` protocol with `put(bucket, key, data: bytes, content_type) -> None`, `delete(bucket, key)`, `public_url(key) -> str`; `get_storage()` returns S3 implementation; tests override with in-memory fake.
- `core.middleware`: request-id (existing) + security headers: `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`, `Content-Security-Policy` (self + media origin + analytics origin; `frame-ancestors 'none'`), `Strict-Transport-Security` when `COOKIE_SECURE`.

- [ ] Step 1: Tests:

```python
import subprocess, sys, os
from app.core.settings import check_production_secrets

def test_production_guard_lists_every_default_secret():
    bad = check_production_secrets({"JWT_SECRET": "dev-only-secret-change-in-production",
        "DATABASE_URL": "postgresql://asi:asi_dev_password@db/asi", "S3_SECRET_KEY": "minioadmin"})
    assert set(bad) == {"JWT_SECRET", "DATABASE_URL", "S3_SECRET_KEY"}

def test_production_guard_passes_real_secrets():
    assert check_production_secrets({"JWT_SECRET": "x" * 48,
        "DATABASE_URL": "postgresql://asi:Str0ng@db/asi", "S3_SECRET_KEY": "s3cr3t-real"}) == []

def test_security_headers_on_every_response(client):
    r = client.get("/healthz")
    for h in ("x-content-type-options", "referrer-policy", "x-frame-options", "content-security-policy", "x-request-id"):
        assert h in r.headers

def test_send_email_uses_starttls_and_login_when_configured(monkeypatch):
    calls = []
    class FakeSMTP:
        def __init__(self, host, port, timeout): calls.append(("connect", host, port))
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def starttls(self): calls.append(("starttls",))
        def login(self, u, p): calls.append(("login", u))
        def send_message(self, msg): calls.append(("send", msg["To"], msg.get("List-Unsubscribe")))
    import app.core.email as e
    monkeypatch.setattr(e.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(e, "SMTP_USER", "u"); monkeypatch.setattr(e, "SMTP_PASSWORD", "p")
    monkeypatch.setattr(e, "SMTP_STARTTLS", True)
    e.send_email("a@b.co", "S", "text", "<p>html</p>", headers={"List-Unsubscribe": "<https://x/u>"})
    assert ("starttls",) in calls and ("login", "u") in calls
    assert calls[-1] == ("send", "a@b.co", "<https://x/u>")
```
Keep the existing `test_production_jwt_guard` (update import path).

- [ ] Step 2: Run → FAIL. Step 3: implement; update every import (`app.settings` → `app.core.settings`, etc.). Step 4: full suite PASS. Step 5: Commit `refactor(api): core package, secrets guard, security headers, SMTP TLS`.

### Task 4: Countries service + public countries API

**Files:**
- Create: `app/services/countries.py`, `app/api/public/countries.py`, `app/api/public/regulatory.py`
- Test: `tests/test_public_countries.py`

**Interfaces:**
- `countries.list_countries(db) -> list[dict]` (code, name, slug, currency, region, status, coverage, summary) ordered `coverage DESC(active first), name`.
- `countries.get_country(db, slug_or_code: str) -> dict | None` adds `regulators` (ordered), `regulatory_entries` (`is_published` only), `compliance_html` (rendered via `services.markdown.render`, Task 6 — until then plain escape), `market` (the country snapshot figure via `snapshot.country_figure(db, code)`, Task 5) and `news` (Task 6 `articles.list_public(db, country=code, page_size=6)`).
- `GET /api/v1/countries`, `GET /api/v1/countries/{slug_or_code}` (404 if unknown), `GET /api/v1/regulatory-watch?country=` (only `is_published`).

- [ ] Step 1: Tests:

```python
def test_countries_list_has_54(client):
    r = client.get("/api/v1/countries"); assert r.status_code == 200
    data = r.json(); assert len(data) == 54
    assert [c["code"] for c in data[:4]] and {c["code"] for c in data[:4]} == {"NG","KE","GH","ZA"}

def test_country_by_slug_and_code(client):
    a = client.get("/api/v1/countries/nigeria").json(); b = client.get("/api/v1/countries/NG").json()
    assert a["code"] == b["code"] == "NG"
    assert any(r["abbreviation"] == "SEC" for r in a["regulators"])

def test_monitoring_country_page_has_researching_status(client):
    r = client.get("/api/v1/countries/cote-d-ivoire").json()
    assert r["status"] == "researching" and r["regulatory_entries"] == []

def test_unknown_country_404(client):
    assert client.get("/api/v1/countries/atlantis").status_code == 404

def test_hidden_regulatory_entry_not_public(client, db_session, make_user):
    uid, _ = make_user("editor")
    from sqlalchemy import text
    db_session.execute(text("""INSERT INTO content.regulatory_entries (country_code, regulation_name, status,
        summary_md, source_url, last_verified_at, is_published) VALUES ('NG','Hidden rule','pending','x','https://x', now(), false)"""))
    db_session.commit()
    names = [e["regulation_name"] for e in client.get("/api/v1/regulatory-watch", params={"country": "NG"}).json()]
    assert "Hidden rule" not in names
```
- [ ] Steps 2–5: fail → implement → pass → commit `feat(api): 54-country directory and country detail`.

### Task 5: Live feeds, Market Snapshot, Ticker services + `/api/v1/live`

**Files:**
- Create: `app/services/live.py`, `app/services/snapshot.py`, `app/api/public/metrics.py` (replaces metrics handlers in `main.py`)
- Test: `tests/test_live_snapshot.py`; update `tests/test_public_metrics_honesty.py` for the new model.

**Interfaces:**
- `live.feed_values(db, now: datetime | None = None) -> dict[str, dict]`: per feed key → `{key, label, unit, value: float|None, display: str|None, change: float|None, change_display: str|None, direction: 'up'|'down'|None, updated_at, is_stale: bool, source_name}`. usd display: `$318.6B`/`$950.2M`; pct display `4.8%`; change for pct feeds in points vs value ≥ 24 h old, for usd feeds as % change.
- `snapshot.metric_cards(db) -> list[dict]` (visible only, ordered) each `{id, kind:'live'|'report', badge:'Live'|'Delayed'|'Report'|'Survey', label, value_display|None, pending_note|None, stamp, highlighted}`; for live cards stamp = `"{source} · updated {n} min ago"`; for report cards stamp = `"{source_name}, {source_period}"` + `" · +52% YoY"` if yoy + `" · {sample_note}"`.
- `snapshot.country_cards(db) -> list[dict]` `{code, name, slug, value_display|None, pending_note|None, stamp, highlighted}`.
- `snapshot.country_figure(db, code) -> dict | None`.
- `snapshot.ticker(db) -> list[dict]` `{key, label, code (country currency or ''), display, change_display, direction, is_stale}`; items whose feed has no value are omitted.
- `GET /api/v1/live` → `{ticker, metric_cards, generated_at}` cached 30 s under `live:`. Existing `/api/v1/metrics/global|countries|premium-tracker|headline-stats|trends|health` kept (countries/headline now from cards/stats, honesty preserved).

- [ ] Step 1: Tests (insert pipeline rows directly):

```python
from datetime import datetime, timedelta, timezone
from sqlalchemy import text

def _global(db, ts, supply):
    db.execute(text("""INSERT INTO market_data.global_metrics (ts, stablecoin_supply_usd, usdt_share_pct, usdc_share_pct, source, fetched_at)
        VALUES (:ts, :s, 61.2, 24.9, 'defillama', :ts)"""), {"ts": ts, "s": supply}); db.commit()

def test_live_card_shows_live_when_fresh(client, db_session):
    _global(db_session, datetime.now(timezone.utc) - timedelta(minutes=10), 318_600_000_000)
    cards = client.get("/api/v1/live").json()["metric_cards"]
    live = next(c for c in cards if c["kind"] == "live")
    assert live["badge"] == "Live" and live["value_display"] == "$318.6B"

def test_live_card_says_delayed_when_stale(client, db_session):
    _global(db_session, datetime.now(timezone.utc) - timedelta(hours=5), 318_600_000_000)
    live = next(c for c in client.get("/api/v1/live").json()["metric_cards"] if c["kind"] == "live")
    assert live["badge"] == "Delayed"

def test_pending_country_never_returns_number(client):
    cards = client.get("/api/v1/home").json()["snapshot"]["countries"]  # /home lands in Task 7; use service directly until then
    ke = next(c for c in cards if c["code"] == "KE")
    assert ke["value_display"] is None and ke["pending_note"]

def test_hidden_card_disappears(client, db_session):
    db_session.execute(text("UPDATE site.snapshot_cards SET is_visible=false WHERE kind='live'")); db_session.commit()
    assert all(c["kind"] != "live" for c in client.get("/api/v1/live").json()["metric_cards"])

def test_ticker_change_direction(client, db_session):
    now = datetime.now(timezone.utc)
    for ts, p2p in ((now - timedelta(hours=25), 1600), (now - timedelta(minutes=5), 1620)):
        db_session.execute(text("""INSERT INTO market_data.country_proxy_metrics (ts, country_code, pair, p2p_rate, official_rate, source)
            VALUES (:ts,'NG','USDTNGN',:p,1530,'quidax')"""), {"ts": ts, "p": p2p})
    db_session.commit()
    ng = next(t for t in client.get("/api/v1/live").json()["ticker"] if t["key"] == "premium_NG")
    assert ng["direction"] == "up" and ng["display"].endswith("%")
```
(Write `test_pending_country_never_returns_number` against `snapshot.country_cards(db_session)` in this task.)
- [ ] Steps 2–5: fail → implement → pass → commit `feat(api): live feeds, admin-driven snapshot and ticker`.

### Task 6: Articles service — Markdown, public queries, search, views, redirects

**Files:**
- Create: `app/services/markdown.py`, `app/services/articles.py`, `app/services/views.py`, `app/api/public/news.py`
- Test: `tests/test_markdown.py`, `tests/test_public_news.py`; update `tests/test_public_api.py`.

**Interfaces:**
- `markdown.render(md: str, media_lookup: Callable[[list[int]], dict[int, dict]] | None = None) -> str`: markdown-it (commonmark + tables + strikethrough), standalone `![alt](media:ID "caption")` paragraphs → `<figure class="figure"><img srcset sizes width height loading="lazy" alt><figcaption>caption <span class="credit">credit</span></figcaption></figure>`; sanitised with nh3 allow-list (p, h2–h4, ul, ol, li, blockquote, strong, em, a[href,title], code, pre, table…, figure, figcaption, img[src,srcset,sizes,alt,width,height,loading], span[class], hr, br); all `a` get `rel="nofollow noopener noreferrer"` and external ones `target="_blank"`; `javascript:`/`data:` URLs removed.
- `markdown.media_ids(md: str) -> list[int]`.
- `articles.PUBLIC_PREDICATE = "a.status IN ('published','scheduled') AND a.published_at <= now()"`.
- `articles.list_public(db, section: str | None = None, country: str | None = None, q: str | None = None, page: int = 1, page_size: int = 12, exclude_ids: list[int] | None = None) -> dict` → `{items: [card], total, page, page_size, pages}`; card = `{id, slug, url, title, dek, section, countries:[{code,name,slug}], published_at, updated_at, author:{name, slug}, cover: image|None, reading_minutes, is_featured}`; image = `{src, srcset, width, height, alt, caption, credit, social}`.
- `articles.get_public(db, slug: str) -> dict | None` (full card + `body_html`, `sources`, `correction_html`, `correction_at`, `seo_description`), or `{"redirect": new_slug}` via `slug_redirects`.
- `articles.related(db, article: dict, limit=3) -> list[card]`, `articles.most_read(db, days=7, limit=5) -> list[card]`.
- `views.record_view(slug: str, user_agent: str) -> None` (Redis `INCR views:{date}:{slug}`, bots skipped by regex `bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp`), `views.flush(db) -> int` (adds to `view_count`, and to `market_data`-independent table `content.article_daily_views(article_id, day, views)` created in 0003 — add it there).
- `GET /api/v1/news?section=markets|regulation&country=&q=&page=&page_size=` and `GET /api/v1/news/{slug}` (404 / `301`-style `{"redirect": slug}` with status 301 + `Location`).
- `views.flush` runs from the app lifespan every 5 minutes in each worker; it reads counters with `GETDEL`, so concurrent workers never double-count.
- Optional error tracking: if `SENTRY_DSN` is set and `sentry-sdk` is installed, `main.py` initialises it (no-op otherwise).

- [ ] Step 1: `tests/test_markdown.py`:

```python
from app.services.markdown import render, media_ids

def test_hostile_markdown_is_neutralised():
    html = render('<script>alert(1)</script>\n\n[x](javascript:alert(1))\n\n<img src=x onerror=alert(1)>\n\n<iframe src="https://e.vil"></iframe>')
    assert "<script" not in html and "javascript:" not in html and "onerror" not in html and "<iframe" not in html

def test_links_are_nofollow_and_external_open_new_tab():
    html = render("[CBN](https://www.cbn.gov.ng)")
    assert 'rel="nofollow noopener noreferrer"' in html and 'target="_blank"' in html

def test_media_image_becomes_figure_with_credit():
    lookup = lambda ids: {7: {"src": "/media/a-800.webp", "srcset": "/media/a-480.webp 480w", "width": 800,
                              "height": 450, "alt": "Lagos market", "caption": None, "credit": "ASI"}}
    html = render('![Lagos market](media:7 "Traders in Lagos")', media_lookup=lookup)
    assert "<figure" in html and "Traders in Lagos" in html and "ASI" in html and 'alt="Lagos market"' in html

def test_media_ids_extracted():
    assert media_ids('a ![x](media:3) b ![y](media:12 "c")') == [3, 12]
```

- [ ] Step 2: `tests/test_public_news.py` (helper `publish(client, make_user, **fields)` in `conftest.py` creating author+editor, article, source, publish; returns slug):

```python
def test_missing_article_is_404(client):
    assert client.get("/api/v1/news/does-not-exist").status_code == 404

def test_public_article_hides_internal_fields(client, make_user, publish):
    slug = publish(title="Naira premium widens", tag="Markets", countries=["NG"])
    body = client.get(f"/api/v1/news/{slug}").json()
    for k in ("author_id", "reviewed_by", "body_md", "search_vector", "view_count"):
        assert k not in body
    assert body["section"] == "Markets" and "<p>" in body["body_html"] and body["sources"]

def test_section_filter_and_pagination(client, make_user, publish):
    for i in range(3): publish(title=f"Market story {i}", tag="Markets")
    publish(title="Reg story", tag="Regulation")
    r = client.get("/api/v1/news", params={"section": "markets", "page_size": 2}).json()
    assert r["total"] >= 3 and len(r["items"]) == 2 and all(i["section"] == "Markets" for i in r["items"])

def test_search_finds_body_text(client, make_user, publish):
    publish(title="Exchange news", tag="Markets", body_md="The CBEX collapse wiped out savings.")
    items = client.get("/api/v1/news", params={"q": "CBEX"}).json()["items"]
    assert any(i["title"] == "Exchange news" for i in items)

def test_future_scheduled_article_not_public_until_time(client, db_session, make_user, publish):
    slug = publish(title="Embargoed", tag="Markets")
    from sqlalchemy import text
    db_session.execute(text("UPDATE content.articles SET status='scheduled', published_at=now()+interval '1 hour' WHERE slug=:s"), {"s": slug}); db_session.commit()
    assert client.get(f"/api/v1/news/{slug}").status_code == 404
    db_session.execute(text("UPDATE content.articles SET published_at=now()-interval '1 minute' WHERE slug=:s"), {"s": slug}); db_session.commit()
    assert client.get(f"/api/v1/news/{slug}").status_code == 200

def test_old_slug_redirects(client, db_session, make_user, publish):
    slug = publish(title="Old title", tag="Markets")
    from sqlalchemy import text
    db_session.execute(text("""INSERT INTO content.slug_redirects (old_slug, article_id)
        SELECT 'old-name', id FROM content.articles WHERE slug=:s"""), {"s": slug}); db_session.commit()
    r = client.get("/api/v1/news/old-name", follow_redirects=False)
    assert r.status_code == 301 and r.json()["redirect"] == slug

def test_non_ascii_title_gets_ascii_slug(client, make_user):
    _, h = make_user("author")
    r = client.post("/admin/articles", json={"title": "Côte d'Ivoire weighs stablecoin rules",
        "body_md": "x", "tag": "Regulation", "countries": ["CI"]}, headers=h)
    assert r.json()["slug"] == "cote-d-ivoire-weighs-stablecoin-rules"
```
(The last test needs `slug` optional in `ArticleIn` — implemented in Task 10; mark it `xfail(strict=True)` here and remove the marker in Task 10.)

- [ ] Steps 3–6: fail → implement (move news handlers out of `main.py`) → pass → commit `feat(api): article rendering, public news, search, redirects`.

### Task 7: Homepage curation service + `/api/v1/home`

**Files:**
- Create: `app/services/homepage.py`, `app/services/site_text.py`, `app/api/public/home.py`
- Test: `tests/test_homepage.py`

**Interfaces:**
- `homepage.big_story(db) -> {"lead": card|None, "secondary": [card, card?]}`: slot article used if live and (`expires_at` null or future); else fallback list = live articles ordered `is_featured DESC, published_at DESC`, skipping already-used ids.
- `homepage.section_lead(db, section: 'Markets'|'Regulation') -> card|None` (slot `markets_lead`/`regulation_lead`, fallback most recent featured in section, then most recent).
- `homepage.breaking(db) -> {"text", "url"} | None` (active and unexpired).
- `site_text.get_all(db) -> dict[str, str]` (cached `sitetext:` 5 min), `site_text.html(db, key) -> str`.
- `GET /api/v1/home` → `{breaking, site_text:{hero_eyebrow,hero_headline,hero_intro,newsletter_pitch,about_short}, ticker, snapshot:{metrics, countries}, big_story, latest:{items…excluding big story ids}, most_read}` cached 60 s under `home:`.

- [ ] Step 1: Tests:

```python
def test_home_on_empty_database_has_safe_shape(client):
    body = client.get("/api/v1/home").json()
    assert body["big_story"]["lead"] is None or isinstance(body["big_story"]["lead"], dict)
    assert isinstance(body["latest"]["items"], list) and "snapshot" in body and "ticker" in body

def test_chosen_lead_story_wins(client, db_session, make_user, publish):
    a = publish(title="First", tag="Markets"); b = publish(title="Second", tag="Markets")
    from sqlalchemy import text
    db_session.execute(text("""INSERT INTO content.homepage_slots (slot, article_id)
        SELECT 'lead', id FROM content.articles WHERE slug=:s ON CONFLICT (slot) DO UPDATE SET article_id=EXCLUDED.article_id"""), {"s": a}); db_session.commit()
    assert client.get("/api/v1/home").json()["big_story"]["lead"]["slug"] == a

def test_expired_lead_falls_back_and_big_story_not_duplicated_in_feed(client, db_session, make_user, publish):
    a = publish(title="Expired lead", tag="Markets"); b = publish(title="Newest", tag="Markets")
    from sqlalchemy import text
    db_session.execute(text("""INSERT INTO content.homepage_slots (slot, article_id, expires_at)
        SELECT 'lead', id, now()-interval '1 hour' FROM content.articles WHERE slug=:s
        ON CONFLICT (slot) DO UPDATE SET article_id=EXCLUDED.article_id, expires_at=EXCLUDED.expires_at"""), {"s": a}); db_session.commit()
    body = client.get("/api/v1/home").json()
    lead = body["big_story"]["lead"]["slug"]; assert lead == b
    big_ids = {lead} | {s["slug"] for s in body["big_story"]["secondary"]}
    assert not big_ids & {i["slug"] for i in body["latest"]["items"]}

def test_breaking_banner_expires(client, db_session):
    from sqlalchemy import text
    db_session.execute(text("""INSERT INTO content.breaking_banner (id, text, is_active, expires_at)
        VALUES (1, 'CBN issues new VASP circular', true, now()-interval '1 minute')
        ON CONFLICT (id) DO UPDATE SET text=EXCLUDED.text, is_active=true, expires_at=EXCLUDED.expires_at""")); db_session.commit()
    assert client.get("/api/v1/home").json()["breaking"] is None
```
- [ ] Steps 2–5: fail → implement → pass → commit `feat(api): big story curation and /api/v1/home`.

### Task 8: Newsletter service — JSON subscribe, confirm+welcome, unsubscribe, archive, resumable send

**Files:**
- Create: `app/services/newsletter.py`, `app/api/public/newsletter.py`, `app/site/templates/email/{confirm,welcome,issue}.{txt,html}`, `app/cli/send_issue.py`
- Test: rewrite `tests/test_newsletter.py`

**Interfaces:**
- `newsletter.normalise_email(raw: str) -> str | None` (strip, lowercase, basic RFC shape via `email_validator` from pydantic[email]).
- `newsletter.subscribe(db, email: str, source_page: str | None, consent_text: str) -> None` (pending; unsubscribed → back to pending with new token; confirmed → no-op, identical response).
- `newsletter.confirm(db, token: str) -> str | None` (email; sends welcome email; sets `unsubscribe_token`).
- `newsletter.unsubscribe(db, token: str) -> bool`.
- `newsletter.render_issue(db, issue_id: int, subscriber: dict | None) -> (subject, text, html)`.
- `newsletter.send_issue(db, issue_id: int, batch_size: int = 50, sleep_s: float = 1.0, send=send_email) -> int` — inserts `deliveries` rows (`ON CONFLICT DO NOTHING`) for all confirmed subscribers, sends only `status='queued'` rows, marks each `sent`/`failed`; issue `status` `sending` → `sent`; returns count sent. Every message has `List-Unsubscribe: <{SITE_URL}/newsletter/unsubscribe?token=…>, <mailto:…>` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click`.
- Routes: `POST /api/v1/newsletter/subscribe` JSON `{email, source_page?, consent: true}` (422 if consent false; 429 after 3/hour/address and 20/hour/IP); `GET /api/v1/newsletter/confirm?token=`; `GET|POST /api/v1/newsletter/unsubscribe?token=`; `GET /api/v1/newsletter/issues`.

- [ ] Step 1: Tests (fake sender captured via monkeypatch on `app.services.newsletter.send_email`):

```python
def test_subscribe_json_confirm_welcome_unsubscribe(client, outbox):
    r = client.post("/api/v1/newsletter/subscribe", json={"email": "  Reader@Example.COM ", "consent": True, "source_page": "home"})
    assert r.status_code == 200 and r.json()["status"] == "pending_confirmation"
    confirm = outbox.last_to("reader@example.com"); token = confirm.token("confirm")
    assert client.get("/api/v1/newsletter/confirm", params={"token": token}).json()["status"] == "confirmed"
    welcome = outbox.last_to("reader@example.com")
    assert "Welcome" in welcome.subject and welcome.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    unsub = welcome.token("unsubscribe")
    assert client.post("/api/v1/newsletter/unsubscribe", params={"token": unsub}).status_code == 200

def test_consent_required(client):
    assert client.post("/api/v1/newsletter/subscribe", json={"email": "a@b.co", "consent": False}).status_code == 422

def test_unsubscribed_can_resubscribe(client, outbox, db_session):
    from sqlalchemy import text
    db_session.execute(text("""INSERT INTO newsletter.newsletter_subscribers (email, status, unsubscribed_at)
        VALUES ('back@example.com','unsubscribed', now())""")); db_session.commit()
    client.post("/api/v1/newsletter/subscribe", json={"email": "back@example.com", "consent": True})
    assert outbox.last_to("back@example.com").token("confirm")

def test_send_issue_is_resumable_and_never_double_sends(db_session, outbox):
    from app.services import newsletter as nl
    from sqlalchemy import text
    for i in range(3):
        db_session.execute(text("""INSERT INTO newsletter.newsletter_subscribers (email, status, confirmed_at, unsubscribe_token)
            VALUES (:e,'confirmed',now(),:t)"""), {"e": f"s{i}@x.co", "t": f"tok{i}"})
    issue_id = db_session.execute(text("""INSERT INTO newsletter.newsletter_issues (issue_number, subject, slug, body_md, status)
        VALUES (1,'Issue 1','issue-1','Hello','draft') RETURNING id""")).scalar(); db_session.commit()
    outbox.fail_after(2)                        # simulate crash after 2 sends
    try: nl.send_issue(db_session, issue_id, sleep_s=0)
    except RuntimeError: pass
    outbox.fail_after(None)
    nl.send_issue(db_session, issue_id, sleep_s=0)
    assert sorted(m.to for m in outbox.messages) == ["s0@x.co", "s1@x.co", "s2@x.co"]
```
(`outbox` fixture in `conftest.py`: records messages, parses tokens from URLs, `fail_after(n)` raises `RuntimeError` on the n+1th send.)
- [ ] Steps 2–5: fail → implement → pass → commit `feat(newsletter): JSON double opt-in, welcome, one-click unsubscribe, resumable sends`.

---

## Phase C — Admin API

### Task 9: Auth — cookie sessions, CSRF header, TOTP, invites/resets, users, audit log

**Files:**
- Create: `app/core/security.py` (from `auth.py`), `app/api/admin/auth.py`, `app/api/admin/users.py`, `app/api/admin/audit.py`
- Test: `tests/test_auth.py` (extend)

**Interfaces:**
- `security.get_current_user` accepts `Authorization: Bearer` **or** cookie `asi_session`; for cookie-authenticated unsafe methods requires header `X-ASI-Admin: 1` (else 403). Returns dict incl. `id, name, email, role, totp_enabled`.
- `POST /admin/auth/login` (form: username, password, optional `otp`) → if user has TOTP and no/invalid otp → 401 `{"detail":"otp_required"}`; admin without TOTP enrolled → login succeeds with `must_enroll_totp: true` and only `/admin/auth/totp/*`, `/admin/me`, logout allowed until enrolled (token claim `enroll_only`). Sets cookie (`HttpOnly; SameSite=Strict; Secure` if `COOKIE_SECURE`; `Path=/admin`) and returns token too.
- `GET /admin/me`; `POST /admin/auth/totp/setup` → `{secret, otpauth_url}`; `POST /admin/auth/totp/verify {otp}` enables; `POST /admin/auth/logout`.
- `POST /admin/users/invite {name,email,role}` → emails a set-password link (`{ADMIN_URL}/set-password?token=`), token hashed (sha256) in `auth.password_tokens`, 72 h; `POST /admin/auth/password-reset/request {email}` (always 200); `POST /admin/auth/password/set {token, password}`.
- `PUT /admin/users/{id}` (role, name, title, bio, slug), deactivate (existing), `PUT /admin/users/{id}/reset-totp`.
- `GET /admin/audit?entity=&user_id=&page=` (admin).
- Every login, user change → `audit.log_action`.
- TOTP secret encrypted with Fernet, key = urlsafe_b64(sha256(JWT_SECRET)).

- [ ] Step 1: Tests:

```python
import pyotp

def test_cookie_session_requires_csrf_header_for_writes(client, make_user):
    make_user("editor", email="c@asi.local")
    r = client.post("/admin/auth/login", data={"username": "c@asi.local", "password": "test-password-123"})
    assert "asi_session" in r.cookies
    assert client.get("/admin/me").status_code == 200
    assert client.post("/admin/articles", json={"title": "t", "body_md": "b", "tag": "Markets"}).status_code == 403
    ok = client.post("/admin/articles", json={"title": "t", "body_md": "b", "tag": "Markets"}, headers={"X-ASI-Admin": "1"})
    assert ok.status_code == 200

def test_totp_flow(client, make_user):
    _, h = make_user("editor", email="t@asi.local")
    secret = client.post("/admin/auth/totp/setup", headers=h).json()["secret"]
    assert client.post("/admin/auth/totp/verify", json={"otp": pyotp.TOTP(secret).now()}, headers=h).status_code == 200
    r = client.post("/admin/auth/login", data={"username": "t@asi.local", "password": "test-password-123"})
    assert r.status_code == 401 and r.json()["detail"] == "otp_required"
    r = client.post("/admin/auth/login", data={"username": "t@asi.local", "password": "test-password-123", "otp": pyotp.TOTP(secret).now()})
    assert r.status_code == 200

def test_admin_without_totp_is_enroll_only(client, make_user):
    make_user("admin", email="a@asi.local")
    r = client.post("/admin/auth/login", data={"username": "a@asi.local", "password": "test-password-123"})
    assert r.json()["must_enroll_totp"] is True
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/admin/users", headers=h).status_code == 403
    assert client.post("/admin/auth/totp/setup", headers=h).status_code == 200

def test_invite_then_set_password(client, make_user, outbox):
    _, h = make_user("admin")   # make_user bypasses enroll_only for admins in tests (fixture marks totp_enabled)
    client.post("/admin/users/invite", json={"name": "New Writer", "email": "w@asi.local", "role": "author"}, headers=h)
    token = outbox.last_to("w@asi.local").token("set-password")
    assert client.post("/admin/auth/password/set", json={"token": token, "password": "a-long-new-password"}).status_code == 200
    assert client.post("/admin/auth/password/set", json={"token": token, "password": "a-long-new-password"}).status_code == 400

def test_audit_log_records_login(client, make_user, db_session):
    make_user("editor", email="l@asi.local")
    client.post("/admin/auth/login", data={"username": "l@asi.local", "password": "test-password-123"})
    from sqlalchemy import text
    assert db_session.execute(text("SELECT COUNT(*) FROM audit.admin_log WHERE action='login'")).scalar() >= 1
```
- [ ] Steps 2–5: fail → implement → pass → commit `feat(auth): cookie sessions, CSRF guard, TOTP, invites, audit log`.

### Task 10: Admin articles — revisions, review checklist, schedule, unpublish, corrections, preview

**Files:**
- Modify→Create: `app/api/admin/articles.py` (from `routers/admin_articles.py`), service functions in `app/services/articles.py`
- Test: `tests/test_articles_publish_rules.py` (keep), `tests/test_admin_articles.py`

**Interfaces:**
- `ArticleIn {title, slug?: str (auto from title), dek?, body_md, tag, countries: list[str] (validated against content.countries), is_featured?, seo_description? (≤ 160), cover_media_id?}`. POST returns `{id, slug, status}`; PUT saves + writes `article_revisions` row; changing slug of a live article inserts `slug_redirects`.
- `GET /admin/articles?status=&section=&country=&author_id=&q=&page=` → `{items,total}`; `GET /admin/articles/{id}/revisions`; `POST /admin/articles/{id}/revisions/{rev_id}/restore`.
- `POST /admin/articles/preview {body_md}` → `{html}` (same renderer as site).
- `POST /admin/articles/{id}/review {decision:'approved'|'changes_requested', note?, checklist:{own_words,sources_credited,facts_verified,image_rights,african_relevance}: bool, publish_at?: datetime}` (editor+, not author): `changes_requested` → status `draft` + note; `approved` requires all five checklist items true, ≥1 source, and every image (cover + inline) with alt text, licence, and credit (unless `own`) → status `published` (publish_at null/past) or `scheduled`; sets `reviewed_by`, `published_at`. Existing `POST /{id}/publish` kept as alias requiring the same checklist.
- `POST /admin/articles/{id}/unpublish` (editor+) → `draft`, removes from homepage slots; `PUT /admin/articles/{id}/correction {correction_md}` (editor+) sets `correction_at=now()`, `updated_at`.
- `PUT /admin/articles/{id}/feature {is_featured}`; `DELETE` (editor+, also removes media links).
- Every mutation → `audit.log_action` and `invalidate_prefix("news:")`, `("home:")`, `("live:")` where relevant; publish → `seo.indexnow_ping(url)` (Task 18; no-op until then).

- [ ] Step 1: Tests:

```python
CHECK = {"own_words": True, "sources_credited": True, "facts_verified": True, "image_rights": True, "african_relevance": True}

def test_review_requires_full_checklist(client, make_user, draft_with_source):
    art_id, _ = draft_with_source()
    _, ed = make_user("editor")
    r = client.post(f"/admin/articles/{art_id}/review", json={"decision": "approved", "checklist": {**CHECK, "own_words": False}}, headers=ed)
    assert r.status_code == 422
    assert client.post(f"/admin/articles/{art_id}/review", json={"decision": "approved", "checklist": CHECK}, headers=ed).json()["status"] == "published"

def test_request_changes_returns_to_draft_with_note(client, make_user, draft_with_source):
    art_id, author_h = draft_with_source()
    _, ed = make_user("editor")
    client.post(f"/admin/articles/{art_id}/review", json={"decision": "changes_requested", "note": "Add CBN source", "checklist": {}}, headers=ed)
    a = client.get(f"/admin/articles/{art_id}", headers=author_h).json()
    assert a["status"] == "draft" and a["reviews"][0]["note"] == "Add CBN source"

def test_schedule_in_future(client, make_user, draft_with_source):
    art_id, _ = draft_with_source(); _, ed = make_user("editor")
    r = client.post(f"/admin/articles/{art_id}/review", json={"decision": "approved", "checklist": CHECK, "publish_at": "2099-01-01T08:00:00+01:00"}, headers=ed)
    assert r.json()["status"] == "scheduled"

def test_image_without_licence_credit_blocks_publish(client, make_user, draft_with_source, db_session):
    art_id, _ = draft_with_source()
    from sqlalchemy import text
    mid = db_session.execute(text("""INSERT INTO content.media (object_key, width, height, alt_text, licence, credit)
        VALUES ('k1', 800, 450, 'alt', 'licensed', NULL) RETURNING id""")).scalar()
    db_session.execute(text("UPDATE content.articles SET cover_media_id=:m WHERE id=:a"), {"m": mid, "a": art_id}); db_session.commit()
    _, ed = make_user("editor")
    r = client.post(f"/admin/articles/{art_id}/review", json={"decision": "approved", "checklist": CHECK}, headers=ed)
    assert r.status_code == 422 and "credit" in r.json()["detail"].lower()

def test_edit_creates_revision_and_restore(client, make_user, draft_with_source):
    art_id, h = draft_with_source()
    a = client.get(f"/admin/articles/{art_id}", headers=h).json()
    client.put(f"/admin/articles/{art_id}", json={**{k: a[k] for k in ("title","body_md","tag","countries")}, "body_md": "v2"}, headers=h)
    revs = client.get(f"/admin/articles/{art_id}/revisions", headers=h).json()
    assert len(revs) >= 1
    client.post(f"/admin/articles/{art_id}/revisions/{revs[-1]['id']}/restore", headers=h)
    assert client.get(f"/admin/articles/{art_id}", headers=h).json()["body_md"] != "v2"

def test_unpublish_and_correction(client, make_user, publish, db_session):
    slug = publish(title="Correctable", tag="Markets")
    from sqlalchemy import text
    aid = db_session.execute(text("SELECT id FROM content.articles WHERE slug=:s"), {"s": slug}).scalar()
    _, ed = make_user("editor")
    client.put(f"/admin/articles/{aid}/correction", json={"correction_md": "An earlier version misstated the rate."}, headers=ed)
    assert "misstated" in client.get(f"/api/v1/news/{slug}").json()["correction_html"]
    client.post(f"/admin/articles/{aid}/unpublish", headers=ed)
    assert client.get(f"/api/v1/news/{slug}").status_code == 404

def test_unknown_country_code_rejected(client, make_user):
    _, h = make_user("author")
    assert client.post("/admin/articles", json={"title": "x", "body_md": "y", "tag": "Markets", "countries": ["XX"]}, headers=h).status_code == 422
```
(`draft_with_source` fixture: author creates article + source, returns `(id, author_headers)`.) Remove the `xfail` from Task 6's slug test.
- [ ] Steps 2–5: fail → implement → pass → commit `feat(admin): editorial workflow — review checklist, scheduling, revisions, corrections`.

### Task 11: Media pipeline & library

**Files:**
- Create: `app/services/media.py`, `app/api/admin/media.py` (replaces `routers/admin_media.py`), `app/cli/regenerate_media.py`
- Test: `tests/test_media.py` (+ `tests/fixtures/` images generated in-test with Pillow)

**Interfaces:**
- `media.process(data: bytes, focal=(0.5,0.5)) -> ProcessedImage` with `.width, .height, .original_jpeg_or_png: bytes, .variants: dict[int, bytes] (webp by width ≤ original), .social: bytes (1200×630 JPEG)`; raises `MediaError(message)` for undecodable / >40 MP / disallowed format.
- `media.save_upload(db, storage, data, filename, user_id, alt_text, caption, credit, licence, licence_note) -> dict` (object keys `media/{yyyy}/{mm}/{uuid}-{w}.webp`, `…-social.jpg`; original to `MEDIA_ORIGINALS_BUCKET`).
- `media.image_dict(row) -> {src, srcset, sizes, width, height, alt, caption, credit, social}` (used by articles service).
- `media.lookup(db, ids: list[int]) -> dict[int, dict]`.
- Routes: `POST /admin/media` (multipart: file + metadata) → media dict + id; `GET /admin/media?q=&page=`; `GET /admin/media/{id}` (+`usage: [{article_id,title,role}]`); `PUT /admin/media/{id}` (alt, caption, credit, licence, licence_note, focal_x, focal_y → regenerates social card when focal changes); `DELETE /admin/media/{id}` (409 if used); `PUT /admin/articles/{id}/cover {media_id|null}`. Inline links synced on every article save from `markdown.media_ids`.

- [ ] Step 1: Tests (storage fake via `app.dependency_overrides[get_storage]`):

```python
import io
from PIL import Image

def _img(mode="RGB", size=(2000, 1200), fmt="JPEG", exif_orientation=None):
    im = Image.new(mode, size, (200, 100, 50) if mode == "RGB" else None)
    buf = io.BytesIO(); kw = {}
    if exif_orientation:
        ex = Image.Exif(); ex[0x0112] = exif_orientation; ex[0x8825] = {2: (6, 27, 0)}; kw["exif"] = ex
    im.save(buf, fmt, **kw); return buf.getvalue()

def test_upload_creates_variants_and_strips_exif(client, make_user, fake_storage):
    _, h = make_user("author")
    r = client.post("/admin/media", files={"file": ("p.jpg", _img(exif_orientation=6), "image/jpeg")},
                    data={"alt_text": "Market", "licence": "own"}, headers=h)
    assert r.status_code == 200
    m = r.json(); assert m["width"] == 1200 and m["height"] == 2000   # rotated upright
    for key, blob in fake_storage.objects.items():
        assert not Image.open(io.BytesIO(blob)).getexif()            # no EXIF/GPS anywhere
    assert any(k.endswith("-social.jpg") for k in fake_storage.objects)

def test_cmyk_and_alpha_are_handled(client, make_user, fake_storage):
    _, h = make_user("author")
    for data, name, ctype in ((_img("CMYK"), "c.jpg", "image/jpeg"), (_img("RGBA", fmt="PNG"), "a.png", "image/png")):
        assert client.post("/admin/media", files={"file": (name, data, ctype)}, data={"alt_text": "x", "licence": "own"}, headers=h).status_code == 200

def test_fake_image_rejected(client, make_user, fake_storage):
    _, h = make_user("author")
    r = client.post("/admin/media", files={"file": ("x.jpg", b"not an image", "image/jpeg")}, data={"alt_text": "x", "licence": "own"}, headers=h)
    assert r.status_code == 422

def test_alt_text_required(client, make_user, fake_storage):
    _, h = make_user("author")
    assert client.post("/admin/media", files={"file": ("p.jpg", _img(), "image/jpeg")}, data={"licence": "own"}, headers=h).status_code == 422

def test_in_use_media_cannot_be_deleted(client, make_user, fake_storage, draft_with_source):
    art_id, h = draft_with_source()
    mid = client.post("/admin/media", files={"file": ("p.jpg", _img(), "image/jpeg")}, data={"alt_text": "x", "licence": "own"}, headers=h).json()["id"]
    client.put(f"/admin/articles/{art_id}/cover", json={"media_id": mid}, headers=h)
    _, ed = make_user("editor")
    assert client.delete(f"/admin/media/{mid}", headers=ed).status_code == 409
```
- [ ] Steps 2–5: fail → implement → pass → commit `feat(media): image processing pipeline and media library`.

### Task 12: Admin — homepage curation, snapshot, ticker, report figures, live feeds, site text

**Files:**
- Create: `app/api/admin/{homepage,snapshot,site_text}.py`; modify `app/api/admin/metrics.py` (from `routers/admin_metrics.py`, visibility endpoints removed/replaced)
- Test: `tests/test_admin_homepage_snapshot.py`; update `tests/test_public_metrics_honesty.py`

**Interfaces:**
- Homepage (editor+): `GET /admin/homepage` → slots + resolved stories + banner; `PUT /admin/homepage/slots/{slot} {article_id|null, expires_at?}` (article must be live, else 422); `PUT /admin/homepage/breaking {text, article_id?, is_active, expires_at?}`.
- Snapshot (admin): `GET /admin/snapshot/cards`; `POST /admin/snapshot/cards {zone, kind, live_feed_key|report_stat_id, label_override?, is_highlighted?}`; `PUT /admin/snapshot/cards/{id}`; `DELETE /admin/snapshot/cards/{id}`; `PUT /admin/snapshot/cards/order {zone, ids: [int]}`. Highlight is exclusive per zone.
- Ticker (admin): `GET/POST /admin/ticker`, `PUT /admin/ticker/{id}`, `DELETE`, `PUT /admin/ticker/order {ids}`.
- Live feeds (admin, read): `GET /admin/live-feeds` (with current values/staleness).
- Report figures (admin): existing `/admin/metrics/manual-stats` + `POST /admin/metrics/manual-stats {metric_key, country_code?, label, badge, display_value?, value?, yoy_change_pct?, is_verified, pending_note?, source_name, source_period?, sample_note?}`; PUT accepts the new fields; history unchanged. Validation: `is_verified=true` requires `display_value`; `false` requires `pending_note`.
- Site text (admin): `GET /admin/site-text`, `PUT /admin/site-text/{key} {value_md}` (unknown key 404).
- All writes: audit log + `invalidate_prefix` for `home:`, `live:`, `metrics:`, `sitetext:`.

- [ ] Step 1: Tests:

```python
def test_admin_adds_report_card_and_it_appears(client, make_user):
    _, h = make_user("admin")
    stat = client.post("/admin/metrics/manual-stats", json={"metric_key": "remittance_cost", "label": "Avg remittance cost into SSA",
        "badge": "Report", "display_value": "7.9%", "is_verified": True, "source_name": "World Bank RPW", "source_period": "Q2 2026"}, headers=h).json()
    client.post("/admin/snapshot/cards", json={"zone": "metrics", "kind": "report", "report_stat_id": stat["id"]}, headers=h)
    labels = [c["label"] for c in client.get("/api/v1/home").json()["snapshot"]["metrics"]]
    assert "Avg remittance cost into SSA" in labels

def test_verified_requires_value_pending_requires_note(client, make_user):
    _, h = make_user("admin")
    r = client.post("/admin/metrics/manual-stats", json={"metric_key": "k", "label": "L", "badge": "Report", "is_verified": True, "source_name": "S"}, headers=h)
    assert r.status_code == 422

def test_reorder_and_exclusive_highlight(client, make_user):
    _, h = make_user("admin")
    cards = [c for c in client.get("/admin/snapshot/cards", headers=h).json() if c["zone"] == "countries"]
    ids = [c["id"] for c in reversed(cards)]
    client.put("/admin/snapshot/cards/order", json={"zone": "countries", "ids": ids}, headers=h)
    client.put(f"/admin/snapshot/cards/{ids[0]}", json={"is_highlighted": True}, headers=h)
    after = [c for c in client.get("/admin/snapshot/cards", headers=h).json() if c["zone"] == "countries"]
    assert [c["id"] for c in after] == ids and sum(c["is_highlighted"] for c in after) == 1

def test_ticker_hide_item(client, make_user):
    _, h = make_user("admin")
    item = client.get("/admin/ticker", headers=h).json()[0]
    client.put(f"/admin/ticker/{item['id']}", json={"is_visible": False}, headers=h)
    assert all(t["key"] != item["live_feed_key"] or False for t in client.get("/api/v1/live").json()["ticker"])

def test_editor_cannot_touch_snapshot_but_can_curate(client, make_user, publish):
    _, ed = make_user("editor")
    assert client.get("/admin/snapshot/cards", headers=ed).status_code == 403
    slug = publish(title="Lead me", tag="Markets")
    aid = client.get("/api/v1/news/" + slug).json()["id"]
    assert client.put("/admin/homepage/slots/lead", json={"article_id": aid}, headers=ed).status_code == 200

def test_cannot_put_draft_in_big_story(client, make_user, draft_with_source):
    art_id, _ = draft_with_source(); _, ed = make_user("editor")
    assert client.put("/admin/homepage/slots/lead", json={"article_id": art_id}, headers=ed).status_code == 422
```
(Public article payload includes `id` — public numeric ids are fine; internal user ids are not.)
- [ ] Steps 2–5: fail → implement → pass → commit `feat(admin): homepage curation, snapshot, ticker, report figures, site text`.

### Task 13: Admin — countries/regulators/regulatory, FX, flags, newsletter, dashboard

**Files:**
- Create: `app/api/admin/{countries,regulatory,fx,flags,newsletter,dashboard}.py` (moving existing routers)
- Test: `tests/test_admin_countries_newsletter.py`

**Interfaces:**
- Countries (editor+): `GET /admin/countries`, `PUT /admin/countries/{code} {status, coverage, summary, compliance_md}`; regulators `POST /admin/countries/{code}/regulators`, `PUT /admin/regulators/{id}`, `DELETE /admin/regulators/{id}`, `PUT /admin/countries/{code}/regulators/order {ids}`.
- Regulatory: existing endpoints + `is_published` field; `country_code` must exist in `content.countries`.
- FX, flags: existing behaviour (paths unchanged).
- Newsletter (admin): `GET /admin/newsletter/stats` → `{pending, confirmed, unsubscribed, last_30_days}`; `GET /admin/newsletter/subscribers.csv` (confirmed only: email, confirmed_at, source_page); issues `GET/POST /admin/newsletter/issues`, `PUT /admin/newsletter/issues/{id}`, `POST /admin/newsletter/issues/{id}/preview` → `{html}`, `POST …/test {to?}` (to self by default), `POST …/send` (starts FastAPI BackgroundTask calling `send_issue`; 409 if already sending/sent), `PUT …/archive {in_archive}`.
- Dashboard (any staff): `GET /admin/dashboard` → `{my_drafts, awaiting_review, scheduled, open_flags, subscribers_confirmed, most_read_7d}`.

- [ ] Step 1: Tests:

```python
def test_editor_updates_country_and_regulator(client, make_user):
    _, ed = make_user("editor")
    client.put("/admin/countries/RW", json={"status": "developing", "coverage": "monitoring", "summary": "Draft VASP law", "compliance_md": "**Licensing** pending."}, headers=ed)
    client.post("/admin/countries/RW/regulators", json={"name": "National Bank of Rwanda", "abbreviation": "BNR", "scope": "Payments"}, headers=ed)
    c = client.get("/api/v1/countries/rwanda").json()
    assert c["status"] == "developing" and c["regulators"][0]["abbreviation"] == "BNR" and "<strong>" in c["compliance_html"]

def test_regulatory_entry_rejects_unknown_country(client, make_user):
    _, ed = make_user("editor")
    r = client.post("/admin/regulatory", json={"country_code": "XX", "regulation_name": "n", "status": "pending", "summary_md": "s", "source_url": "https://s"}, headers=ed)
    assert r.status_code == 422

def test_newsletter_issue_send_only_once(client, make_user, outbox, db_session):
    _, h = make_user("admin")
    from sqlalchemy import text
    db_session.execute(text("INSERT INTO newsletter.newsletter_subscribers (email,status,confirmed_at,unsubscribe_token) VALUES ('c@x.co','confirmed',now(),'u1')")); db_session.commit()
    iid = client.post("/admin/newsletter/issues", json={"subject": "ASI Briefing #1", "body_md": "Hello Africa"}, headers=h).json()["id"]
    assert client.post(f"/admin/newsletter/issues/{iid}/send", headers=h).status_code == 200
    assert client.post(f"/admin/newsletter/issues/{iid}/send", headers=h).status_code == 409
    assert [m.to for m in outbox.messages if m.subject == "ASI Briefing #1"] == ["c@x.co"]

def test_subscriber_export_is_admin_only_csv(client, make_user):
    _, ed = make_user("editor"); _, ad = make_user("admin")
    assert client.get("/admin/newsletter/subscribers.csv", headers=ed).status_code == 403
    r = client.get("/admin/newsletter/subscribers.csv", headers=ad)
    assert r.headers["content-type"].startswith("text/csv") and r.text.startswith("email,")

def test_dashboard_counts(client, make_user, draft_with_source):
    art_id, h = draft_with_source()
    d = client.get("/admin/dashboard", headers=h).json()
    assert d["my_drafts"] >= 1
```
- [ ] Steps 2–5: fail → implement → pass → commit `feat(admin): countries, regulators, newsletter management, dashboard`.

---

## Phase D — Public site (server-rendered)

### Task 14: Site foundation — templates, assets, layout, errors

**Files:**
- Create: `app/site/routes.py`, `app/site/context.py`, `app/site/templates/{base.html, partials/{masthead,footer,article_card,article_list_item,figure,pagination,share,subscribe_box,breadcrumbs,seo_head}.html, errors/{404,500}.html}`, `app/site/static/css/site.css` (ported from `docs/reference/frontend-prototype/styles.css` + new components), `app/site/static/js/site.js`, `app/site/static/fonts/*.woff2` (Fraunces, IBM Plex Sans, IBM Plex Mono — download latin subsets from Google Fonts/fontsource npm packages at build time of this task and commit), `app/site/static/img/{logo.svg,logo-512.png,og-default.jpg,favicon.svg}`, `app/site/static/site.webmanifest`
- Test: `tests/test_site_base.py`

**Interfaces:**
- `context.base(request, db, *, title, description, canonical_path, og_image=None, og_type='website', json_ld: list[dict] = [], breadcrumbs=None, noindex=False) -> dict` used by every page; includes `site_text`, `nav_active`, `breaking`, `verification` tags, `analytics`, `static_url(path)` (fingerprinted `?v={sha1[:10]}` computed at startup).
- Masthead: brand, nav (Home · Market News · Countries · Regulation News · About), search link, Subscribe; below 960 px a `<button aria-expanded>` hamburger toggling the nav (works without JS via `:target` fallback), skip link.
- 404/500 handlers render templates for HTML requests and JSON for `/api` & `/admin`.
- Static mounted at `/static` with `Cache-Control: public, max-age=31536000, immutable`.

- [ ] Step 1: Tests:

```python
def test_unknown_page_renders_branded_404(client):
    r = client.get("/no-such-page"); assert r.status_code == 404
    assert "text/html" in r.headers["content-type"] and "Africa" in r.text

def test_api_404_stays_json(client):
    assert client.get("/api/v1/nope").headers["content-type"].startswith("application/json")

def test_layout_has_skip_link_mobile_menu_and_canonical(client):
    html = client.get("/about").text
    assert 'class="skip-link"' in html and 'aria-controls="primary-nav"' in html and 'rel="canonical"' in html

def test_static_assets_are_immutable(client):
    r = client.get("/static/css/site.css"); assert r.status_code == 200
    assert "immutable" in r.headers["cache-control"]
```
(`/about` route is created minimal here and completed in Task 17.)
- [ ] Steps 2–5: fail → implement → pass → commit `feat(site): server-rendered layout, assets, self-hosted fonts, error pages`.

### Task 15: Home page

**Files:**
- Create: `app/site/templates/home.html`, `partials/{ticker,snapshot,big_story,feed_filters}.html`; extend `site.css`, `site.js`
- Test: `tests/test_site_home.py`

**Behaviour:** layout exactly as spec §2.3. Ticker: two identical sets for seamless loop (second `aria-hidden`), pause/play button (`aria-pressed`), honours reduced motion. Snapshot: badges Live/Delayed/Report/Survey; pending shows note in place of value. Big story: lead with `fetchpriority="high"` image, two secondary. Feed filters are links (`/?section=markets`, `/?country=NG` …, crawlable) progressively enhanced to fetch `/api/v1/news` without reload; "Load more" link to `?page=2`. Sidebar: subscribe form (JS posts JSON to `/api/v1/newsletter/subscribe` with consent checkbox; no-JS fallback form POST to `/newsletter` handled by site route), Most read, About. `site.js` refreshes ticker + live cards from `/api/v1/live` every 60 s (pauses when tab hidden).
- JSON-LD on home: `Organization`, `WebSite` with `SearchAction` (`/search?q={search_term_string}`).

- [ ] Step 1: Tests:

```python
def test_home_renders_on_empty_db(client):
    r = client.get("/"); assert r.status_code == 200
    assert 'class="ticker' in r.text and "Market snapshot" in r.text and "Latest intelligence" in r.text

def test_home_shows_lead_story_and_pending_note(client, make_user, publish):
    slug = publish(title="Kenya licensing window opens", tag="Regulation", countries=["KE"])
    html = client.get("/").text
    assert "Kenya licensing window opens" in html and f'/regulation/{slug}' in html
    assert "exact figure pending" in html          # Kenya/Ghana honesty rule on the page itself

def test_ticker_has_pause_control(client):
    assert 'data-ticker-toggle' in client.get("/").text

def test_home_filter_links_are_crawlable(client):
    html = client.get("/").text
    assert 'href="/?section=markets"' in html and 'href="/?section=regulation"' in html

def test_no_js_subscribe_fallback(client, outbox):
    r = client.post("/newsletter", data={"email": "nojs@example.com", "consent": "on", "source_page": "home"})
    assert r.status_code == 200 and "Check your inbox" in r.text
```
- [ ] Steps 2–5: fail → implement → pass → commit `feat(site): home page with live ticker, snapshot, big story and feed`.

### Task 16: Section pages and article page

**Files:**
- Create: `app/site/templates/{section.html, article.html}`
- Test: `tests/test_site_articles.py`

**Behaviour:** `/markets` and `/regulation`: section lead + paginated list (`?page=`, `rel=prev/next`, canonical on page 1 without `?page=1`), country filter chips. `/markets/{slug}` & `/regulation/{slug}`: spec §2.4; wrong section prefix → 301 to correct one; old slug → 301; unpublished → 404. Records a view (`views.record_view`). JSON-LD `NewsArticle` + `BreadcrumbList`; OG `article:published_time`, `article:modified_time`, `article:section`, `og:image` = social card (1200×630) or default. `robots` meta `max-image-preview:large`. Markets articles show the disclaimer from `site_text.disclaimer`.

- [ ] Step 1: Tests:

```python
import json, re

def test_article_page_full_render(client, make_user, publish):
    slug = publish(title="Why Tron carries naira USDT", tag="Markets", countries=["NG"], body_md="## Fees\n\nTron is cheap.")
    r = client.get(f"/markets/{slug}"); assert r.status_code == 200
    assert "<h2>Fees</h2>" in r.text and "Sources" in r.text and "Not financial advice" in r.text
    ld = [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.S)]
    article = next(x for x in ld if x.get("@type") == "NewsArticle")
    assert article["headline"] == "Why Tron carries naira USDT" and article["author"][0]["@type"] == "Person"
    assert 'name="robots" content="max-image-preview:large"' in r.text

def test_wrong_section_redirects(client, make_user, publish):
    slug = publish(title="Reg piece", tag="Regulation")
    r = client.get(f"/markets/{slug}", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == f"/regulation/{slug}"

def test_section_pagination_canonical(client, make_user, publish):
    for i in range(14): publish(title=f"M{i}", tag="Markets")
    p2 = client.get("/markets?page=2").text
    assert 'rel="canonical" href="http://testserver/markets?page=2"' in p2 or 'href="' in p2
    assert 'rel="prev"' in p2

def test_unpublished_article_404_page(client):
    assert client.get("/markets/not-real").status_code == 404
```
(Canonical uses `SITE_URL`; in tests `SITE_URL=http://testserver` set in `conftest.py` env.) Tighten the canonical assertion to the exact `http://testserver/markets?page=2`.
- [ ] Steps 2–5: fail → implement → pass → commit `feat(site): section pages and article page with structured data`.

### Task 17: Countries, authors, search, newsletter and policy pages

**Files:**
- Create: templates `countries.html`, `country.html`, `author.html`, `search.html`, `newsletter.html`, `newsletter_issue.html`, `newsletter_result.html`, `page.html` (generic Markdown page from `site_text`), `about.html`
- Test: `tests/test_site_pages.py`

**Behaviour:** `/countries` grouped by region with status chips and a client-side filter box; `/countries/{slug}` = status, summary, plain-language compliance panel, regulators (links + register links), regulatory entries (dated, sourced), market figure or pending note, related news with "More {country} news" link to `/?country=XX`. `/authors/{slug}`. `/search?q=` (noindex). `/newsletter` signup + archive list; `/newsletter/issues/{slug}`; `/newsletter/confirm?token=` and `/newsletter/unsubscribe?token=` (GET shows confirm button for unsubscribe → POST, preventing link-scanner unsubscribes; one-click POST header path served by API). `/about`, `/methodology`, `/editorial-policy`, `/corrections`, `/privacy`, `/terms`, `/contact` from `site_text`.

- [ ] Step 1: Tests:

```python
import pytest

@pytest.mark.parametrize("path", ["/countries", "/countries/nigeria", "/countries/cote-d-ivoire", "/about", "/methodology",
    "/editorial-policy", "/corrections", "/privacy", "/terms", "/contact", "/newsletter", "/search?q=naira"])
def test_pages_render(client, path):
    assert client.get(path).status_code == 200

def test_country_page_lists_regulators_and_honest_figure(client):
    html = client.get("/countries/kenya").text
    assert "Capital Markets Authority" in html and "exact figure pending" in html

def test_search_page_is_noindex(client):
    assert 'content="noindex' in client.get("/search?q=x").text

def test_unsubscribe_get_does_not_unsubscribe(client, db_session):
    from sqlalchemy import text
    db_session.execute(text("INSERT INTO newsletter.newsletter_subscribers (email,status,confirmed_at,unsubscribe_token) VALUES ('k@x.co','confirmed',now(),'tok-k')")); db_session.commit()
    client.get("/newsletter/unsubscribe", params={"token": "tok-k"})
    assert db_session.execute(text("SELECT status FROM newsletter.newsletter_subscribers WHERE email='k@x.co'")).scalar() == "confirmed"
    client.post("/newsletter/unsubscribe", data={"token": "tok-k"})
    assert db_session.execute(text("SELECT status FROM newsletter.newsletter_subscribers WHERE email='k@x.co'")).scalar() == "unsubscribed"

def test_author_page(client, make_user, publish, db_session):
    slug = publish(title="By an author", tag="Markets")
    from sqlalchemy import text
    aslug = db_session.execute(text("SELECT u.slug FROM auth.users u JOIN content.articles a ON a.author_id=u.id WHERE a.slug=:s"), {"s": slug}).scalar()
    assert "By an author" in client.get(f"/authors/{aslug}").text
```
(Users get a `slug` from their name on creation — implement in `make_user`/user creation path; 0003 backfills existing users.)
- [ ] Steps 2–5: fail → implement → pass → commit `feat(site): countries, authors, search, newsletter and policy pages`.

### Task 18: SEO machine endpoints + IndexNow + analytics/verification

**Files:**
- Create: `app/services/seo.py`, `app/seo/routes.py`
- Test: `tests/test_seo.py`

**Interfaces:**
- `/robots.txt` (allow all; disallow `/search`, `/admin`, `/api/`; `Sitemap:` lines; production only — non-production returns `Disallow: /`).
- `/sitemap.xml` (index → `/sitemap-pages.xml`, `/sitemap-articles.xml`, `/news-sitemap.xml`); articles sitemap includes `<image:image>`; news sitemap only last 48 h with `<news:publication><news:name>Africa Stablecoin Intelligence</news:name><news:language>en</news:language>`.
- `/feed.xml`, `/markets/feed.xml`, `/regulation/feed.xml` (RSS 2.0, 30 items, `<enclosure>`/`media:content` for cover).
- `/{INDEXNOW_KEY}.txt` serves the key; `seo.indexnow_ping(urls: list[str]) -> None` (POST `https://api.indexnow.org/indexnow`, only in production, best-effort, background).
- Verification meta tags + analytics `<script defer data-domain src>` rendered from settings in `base.html`.

- [ ] Step 1: Tests:

```python
import xml.etree.ElementTree as ET

def test_sitemaps_and_feeds_are_valid_xml_on_empty_db(client):
    for p in ("/sitemap.xml", "/sitemap-pages.xml", "/sitemap-articles.xml", "/news-sitemap.xml", "/feed.xml", "/markets/feed.xml", "/regulation/feed.xml"):
        r = client.get(p); assert r.status_code == 200, p; ET.fromstring(r.content)

def test_article_in_news_sitemap_and_feed(client, make_user, publish):
    slug = publish(title="Fresh story", tag="Markets")
    assert f"/markets/{slug}" in client.get("/news-sitemap.xml").text
    assert "Fresh story" in client.get("/feed.xml").text

def test_pages_sitemap_covers_all_countries(client):
    assert client.get("/sitemap-pages.xml").text.count("/countries/") == 54

def test_robots_blocks_everything_outside_production(client):
    assert "Disallow: /" in client.get("/robots.txt").text

def test_robots_in_production(client, monkeypatch):
    import app.seo.routes as r; monkeypatch.setattr(r, "ENVIRONMENT", "production")
    body = client.get("/robots.txt").text
    assert "Sitemap:" in body and "Disallow: /admin" in body and "Disallow: /\n" not in body
```
- [ ] Steps 2–5: fail → implement (call `indexnow_ping` from Task 10 publish path) → pass → commit `feat(seo): sitemaps, news sitemap, RSS, robots, IndexNow, verification`.

---

## Phase E — Admin panel (React SPA)

All admin tasks: `apps/admin`, React 18, Vite 5, react-router 6, no UI kit; CSS uses ASI tokens; fetch wrapper `api(path, {method, body})` sends `credentials: 'same-origin'` and `X-ASI-Admin: 1`; 401 → `/login`. Component tests with Vitest + Testing Library for logic-bearing components. `npm run build` must pass with zero warnings treated as errors in CI (`vite build`).

### Task 19: Admin scaffold — auth flows, layout, dashboard

**Files:** `apps/admin/{package.json, vite.config.js (proxy /admin,/media,/api,/static → :8000), index.html, Dockerfile (multi-stage build → static files), src/{main.jsx, App.jsx, api.js, auth.jsx, styles.css, components/{Layout,Nav,RequireRole,Toast,ConfirmDialog,Field,Table,Pagination,EmptyState}.jsx, pages/{Login,TotpSetup,SetPassword,ResetRequest,Dashboard}.jsx}}`, tests `src/__tests__/auth.test.jsx`.

- [ ] Step 1: Test: login form posts form-encoded credentials; on `otp_required` shows the code field; on `must_enroll_totp` routes to `/totp-setup`; nav hides admin-only items for writers.
- [ ] Step 2: Implement; `npm ci && npm test && npm run build` pass.
- [ ] Step 3: Commit `feat(admin-web): scaffold, auth flows, dashboard`.

### Task 20: Articles list, editor, review

**Files:** `src/pages/{Articles,ArticleEditor,Review}.jsx`, `src/components/{MarkdownEditor,MarkdownToolbar,SourcesEditor,CountryPicker,ImagePicker,RevisionsPanel,Checklist,StatusBadge}.jsx`, tests `src/__tests__/{editor,review}.test.jsx`.

Behaviour: list with status tabs + filters; editor with title → auto slug (editable), dek, section radio, countries multi-select (54, active first), cover picker, SEO description counter (160), Markdown toolbar (bold, italic, H2, H3, link, quote, list, image → ImagePicker inserts `![alt](media:ID "caption")`), live preview via `/admin/articles/preview` (debounced 600 ms), autosave every 10 s when dirty (shows "Saved hh:mm"), sources editor, revisions panel with restore, Submit for review. Review page: full preview, checklist (five boxes; image-rights box auto-reflects server validation), Publish now / Schedule (datetime in Africa/Lagos) / Request changes (note). Editor actions on published: Feature toggle, Correction, Unpublish, Delete (confirm dialog).

- [ ] Step 1: Tests: autosave fires after edits; Publish button disabled until all five checklist items ticked; image insert writes `media:` syntax at cursor.
- [ ] Step 2: Implement; tests + build pass. Step 3: Commit `feat(admin-web): article editor and review workflow`.

### Task 21: Media library, Homepage curation, Snapshot, Ticker, Report figures, FX

**Files:** `src/pages/{Media,Homepage,Snapshot,Ticker,ReportFigures,FxRates}.jsx`, `src/components/{FocalPointPicker,UploadDropzone,OrderList,ArticleSearchSelect,LivePreviewCard}.jsx`, tests `src/__tests__/{orderlist,focal}.test.jsx`.

Behaviour: media grid with search, upload dropzone (shows alt/credit/licence form before upload completes), detail drawer with focal point click, usage list, delete (disabled when used). Homepage: Lead + 2 secondary + section leads with article search-select (live only) and "feature until"; breaking banner form; live preview of resolved Big Story. Snapshot: two zones, OrderList with ↑/↓ buttons (keyboard-accessible), add card (live feed or report figure), highlight radio, show/hide, preview tile styled like the public card. Ticker: OrderList of live feeds with label + show/hide + current value/staleness. Report figures: table + form (pending toggle switches value field ↔ note), history drawer. FX: existing.

- [ ] Step 1: Tests: OrderList ↑/↓ emits new id order; FocalPointPicker reports click position as 0–1 fractions.
- [ ] Step 2: Implement; tests + build pass. Step 3: Commit `feat(admin-web): media library, homepage curation, snapshot and ticker control`.

### Task 22: Countries & regulators, regulatory, newsletter, site text, alerts, users, audit

**Files:** `src/pages/{Countries,CountryEdit,Regulatory,Newsletter,IssueEditor,SiteText,DataAlerts,Users,AuditLog}.jsx`, tests `src/__tests__/newsletter.test.jsx`.

Behaviour: countries table (filter by region/status/coverage) → edit page (status, coverage, summary, compliance Markdown with preview, regulators OrderList + form); regulatory entries list/edit with history + publish toggle; newsletter stats cards, CSV export button, issues list, issue editor (Markdown + preview, Send test, Send to all with confirm dialog showing confirmed count, archive toggle; disabled once sent); site text list grouped (Home, About & policies, Footer) with Markdown editor + preview; data alerts (open/resolved tabs, JSON detail, resolve with note); users (invite, role change, deactivate, reset 2FA); audit log (filters, paging).

- [ ] Step 1: Test: "Send to all" requires typing the confirmed count into the dialog before enabling.
- [ ] Step 2: Implement; tests + build pass. Step 3: Commit `feat(admin-web): countries, newsletter, site text, alerts, users, audit log`.

---

## Phase F — Pipelines, production, docs

### Task 23: Pipelines — restore cross-check alerting

**Files:** `pipelines/dags/dag_cross_check.py`, `pipelines/dags/_common.py` (shared `db_url()`, `flag()`, `send_alert()`), `apps/api/tests/test_dags_import.py`

- Staleness per `market_data.live_feeds` (`global_*` from `global_metrics.fetched_at`, `premium_XX` from latest `country_proxy_metrics` for country); stale `global_supply` is **critical** → `send_alert` to `ALERT_EMAIL_TO`; premium outlier `> 30` → flag; existing proxy-jump, missing-official-rate, global-jump checks and hourly trend snapshots kept. Duplicate open flags for the same `metric_key` within 6 h are not re-inserted (no alert storms).
- Test: `test_dags_import.py` compiles each DAG file with `py_compile` and asserts `_common.flag` de-dup SQL contains `NOT EXISTS`.
- [ ] Steps: test → implement → `python -m py_compile pipelines/dags/*.py` → commit `fix(pipelines): restore staleness/outlier checks and alerting`.

### Task 24: Production stack — Dockerfiles, compose, Caddy, backups

**Files:**
- `apps/api/Dockerfile` (python:3.12-slim, non-root user, `pip install --no-cache-dir`, healthcheck, `CMD gunicorn -c gunicorn.conf.py app.main:app`), `apps/api/gunicorn.conf.py` (`worker_class=uvicorn.workers.UvicornWorker`, `workers = 2*cpu+1` capped 5, `timeout 60`, access log JSON), `apps/api/docker-entrypoint.sh` (`alembic upgrade head` then exec).
- `apps/admin/Dockerfile` (node:20-alpine build → `/srv/admin` artefact copied into caddy image).
- `infra/Caddyfile`:
  - `{$SITE_DOMAIN}`: `encode zstd gzip`; `handle /media/*` → `reverse_proxy minio:9000` with `uri strip_prefix` + bucket rewrite, `Cache-Control "public, max-age=31536000, immutable"`; everything else → `reverse_proxy api:8000`; security headers (HSTS 1y includeSubDomains preload).
  - `www.{$SITE_DOMAIN}` → `redir https://{$SITE_DOMAIN}{uri} permanent`.
  - `admin.{$SITE_DOMAIN}`: `handle /admin/*` → api; `handle /media/*` → minio; else `root * /srv/admin` + `try_files {path} /index.html` + `file_server`; `X-Robots-Tag: noindex`.
- `infra/docker-compose.prod.yml`: caddy (80/443 published, `caddy_data` volume), api (env from `.env`, no ports), postgres (no ports, password from env), redis (`--appendonly yes`, no ports), minio (no ports), minio-init (public bucket + private originals bucket), airflow-init/webserver(127.0.0.1:8080 only)/scheduler with `AIRFLOW__WEBSERVER__SECRET_KEY` and admin password from env, backup; all `restart: unless-stopped`, healthchecks, `logging: json-file max-size 10m max-file 5`.
- `infra/backup/{Dockerfile,backup.sh,restore.sh}`: nightly 02:30 UTC `pg_dump -Fc` + `mc mirror` of media into `/backups/{daily,weekly}`, retention 14 daily / 8 weekly, optional `rclone`/`mc` copy to `OFFSITE_S3_*`; `restore.sh <dump>`.
- `infra/.env.prod.example` documenting every variable; root `Makefile` gains `prod-up`, `prod-logs`, `prod-backup`, `prod-restore`, `prod-shell`.
- Test: CI step `docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod.example config -q`; `caddy validate` via `docker run caddy:2 caddy validate --config /etc/caddy/Caddyfile`.
- [ ] Steps: implement → validate both → `docker compose -f infra/docker-compose.prod.yml build` succeeds → commit `feat(infra): production compose, Caddy HTTPS, backups`.

### Task 25: Docs, seed demo, CI, dependabot

**Files:** `README.md` (what ASI is, repo map, quick start, common commands), `docs/ARCHITECTURE.md` (diagram, rules, data flow, caching), `docs/DEPLOYMENT.md` (DNS A/AAAA for apex/www/admin, VM setup, Docker install, `.env`, first boot, bootstrap admin + TOTP, SMTP provider + SPF/DKIM/DMARC records, Search Console/Bing/Google News Publisher Center, IndexNow key, uptime monitor, backups + restore drill, updating), `docs/LAUNCH_CHECKLIST.md` (go/no-go list mapped to plan Phase 4), `docs/EDITORIAL_GUIDE.md` (how to write, images & licences, review checklist, Big Story, snapshot updates when a report lands, corrections), `apps/api/app/cli/seed_demo.py` (updated: uses new schema, demo images generated with Pillow, refuses on real content, clearly "DEMO"), `.github/workflows/ci.yml` (jobs: api-tests (Timescale+Redis services, `alembic upgrade head` twice, `pytest`), lint (`ruff check apps/api pipelines`), admin (`npm ci`, `npm test`, `npm run build`), infra (compose config dev+prod, caddy validate), dags (py_compile)), `.github/dependabot.yml` (pip `/apps/api`, npm `/apps/admin`, docker, github-actions; weekly), `.editorconfig`, `.env.example` (dev).
- [ ] Steps: write → CI-equivalent commands locally → commit `docs: architecture, deployment, launch checklist, editorial guide; CI`.

### Task 26: Final verification

- [ ] Fresh volume: `docker compose down -v && docker compose up -d --build`; `make bootstrap-admin`; `make seed-demo`.
- [ ] `docker compose exec api pytest -q` → all pass; `cd apps/admin && npm test && npm run build`.
- [ ] Smoke every public URL (script `infra/scripts/smoke.sh` hitting the list in spec §2.2 expecting 200/404 as appropriate) and every sitemap/feed.
- [ ] Manual walkthrough in browser: write → upload image → submit → review → publish → appears in Big Story; edit snapshot card & ticker; subscribe → Mailhog confirm → welcome → unsubscribe.
- [ ] Lighthouse (mobile) on Home and an article ≥ 90 performance/accessibility/SEO/best-practices; fix regressions.
- [ ] Security pass: `/security-review` skill over the branch; confirm no secrets committed; CSP has no `unsafe-inline` for scripts.
- [ ] Commit fixes; summarise to the owner with remaining launch actions (DNS, VM, SMTP provider, legal review of policy texts, verify regulatory seed facts, write seed articles).
