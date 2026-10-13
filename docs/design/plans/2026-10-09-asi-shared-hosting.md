# ASI on WhoGoHost Shared Hosting — Implementation Plan

**Goal:** Run the complete ASI platform (public site, public API, admin panel, data pipelines, newsletter) on
WhoGoHost DirectAdmin shared hosting: Passenger + Python 3.11 + MariaDB 11.4 + cron, inside 1 GB of memory
and one CPU core.

**Architecture:** One FastAPI app runs under Passenger through `a2wsgi` and answers both host names. Every
Postgres feature is ported to MariaDB 11.4. Redis becomes small MariaDB tables. Public pages are written to a
disk cache that Apache serves without starting Python. Airflow DAGs and the in-process background loops become
plain Python jobs run by cron through one runner. GitHub Actions tests everything and publishes a `release` branch,
which the server deploys with `deploy.sh`.

**Tech Stack:**
- Python 3.11, FastAPI, SQLAlchemy 2 (Core, `text()` SQL), PyMySQL, Alembic, a2wsgi, Jinja2, Pillow, pytest
- MariaDB 11.4
- React 18 + Vite 5 + vitest (admin)
- Apache `.htaccess` + Phusion Passenger (CloudLinux "Setup Python App")
- GitHub Actions

**Spec:** `docs/design/specs/2026-10-09-asi-shared-hosting-design.md` (read it first; this plan argues from it).

## Global Constraints

- **Python:** 3.11 exactly (host offers 3.11.16). Local Docker images use `python:3.11-slim`.
- **Database:** MariaDB **11.4** only, with one database. Tables are prefixed `auth_`, `content_`, `market_`,
  `newsletter_`, `site_`, `audit_` and `ops_` (mapping in "Table mapping" below).
- **Charset:** `utf8mb4`. Default collation `utf8mb4_uca1400_ai_ci` on every table (`TABLE_OPTS` constant).
- **Times:** stored as UTC in `DATETIME(6)`. Every connection runs `SET time_zone = '+00:00'`. SQL uses
  `UTC_TIMESTAMP(6)` and `UTC_DATE()`. The driver converts aware datetimes to UTC on write and returns aware UTC
  datetimes on read (Task 1). The server clock is SAST (UTC+2) and must never leak into data.
- **Booleans:** `TINYINT(1)`. `TINYINT` is used for booleans only, never for numbers (the driver maps every TINYINT
  to `bool`).
- **Reserved word:** the column name `key` is always written as `` `key` `` in SQL.
- **Server-wide locks:** `GET_LOCK` names are namespaced as `CONCAT(DATABASE(), ':', <name>)`. The MariaDB server
  is shared with other customers.
- **Runtime dependencies** must install from wheels only (`pip install --only-binary=:all:`). No gunicorn, uvicorn,
  psycopg2 or redis in `requirements.txt`; uvicorn lives in `requirements-dev.txt`.
- **Memory:** Passenger `PassengerMaxPoolSize 3`; database pool `pool_size=3, max_overflow=2, pool_recycle=280`;
  image uploads max **10 MB** and **24 megapixels**.
- **No background threads or loops** inside the web app. Periodic work runs only through `python -m app.jobs <name>`.
- **Page cache:** only GET, status 200, empty query string, public host, content types HTML/JSON/XML/plain text,
  and no `Set-Cookie` or `Cache-Control: no-store`.
- **Brand colour:**
  - `--brand: #ff914d`, `--brand-ink: #a84d12`, `--brand-pale: #ffd2b3`
  - never white text on `--brand`
  - never `--brand` as text on the cream page
- **Hosts:**
  - public: `africastablecoinintelligence.com`
  - admin: `admin.africastablecoinintelligence.com`
  - host routing is on in production, off in development and tests (one host)
- **Commits:** every task ends with a commit on branch `shared-hosting`.
- **Prerequisite:** Docker Desktop running (MariaDB 11.4 + MailHog for tests).

## Review Focus

1. **Search on freshly committed articles.** InnoDB indexes FULLTEXT rows only at COMMIT, so a story is not
   searchable until its transaction commits. The search tests use a `committed` fixture (Task 3) rather than the
   rolled-back test transaction. A reader searching "cote" must find "Côte d'Ivoire" right after publication.
2. **A story scheduled in Lagos time on a server running SAST.** An editor schedules 09:00 Africa/Lagos. It must be
   stored as 08:00 UTC, go live at 08:00 UTC and show as 09:00 Lagos time. Pinned by `test_aware_times_round_trip_as_utc` (Task 1) and `test_scheduled_in_lagos_time_goes_live_on_time` (Task 3).
3. **Renaming a live story.** The old address must stop serving the cached old page and answer the 301 redirect
   immediately. Pinned by `test_renaming_a_live_article_purges_the_old_address` (Task 8).
4. **An edit landing while a page renders.** A page rendered from old data must not be written to the cache
   after the purge that the edit triggered (generation check). Pinned by `test_render_that_raced_a_purge_is_not_stored` (Task 8).
5. **Requests that must never be cached:** query strings, the admin host, unknown hosts, non-200 responses,
   path-traversal paths. Pinned by `test_never_cached_requests` and `test_path_traversal_is_never_cached` (Task 8).

---

## File Structure

| Path | Responsibility | Task |
|---|---|---|
| `docker-compose.yml` | Dev stack: MariaDB 11.4, MailHog, API (uvicorn --reload) | 1 |
| `docker/mariadb-init.sql` | Creates `asi_test` and grants the dev user | 1 |
| `apps/api/requirements.txt` / `requirements-dev.txt` | Runtime (wheel-only) / dev + test deps | 1 |
| `apps/api/Dockerfile` | Dev image only (python:3.11-slim, uvicorn) | 1 |
| `apps/api/app/core/settings.py` | New settings (DB URL, cache root, live.json, hosts, mail cap, data dirs) | 1, 7, 8, 9 |
| `apps/api/app/core/envfile.py` | Loads `~/asi/.env` into `os.environ` without overriding | 1 |
| `apps/api/app/core/db.py` | Engine factory, PyMySQL converters (UTC, bool), `db_json`, `named_lock` | 1 |
| `apps/api/alembic/env.py` | Uses `db.make_engine` (same session settings) | 1 |
| `apps/api/alembic/versions/0001_mariadb_baseline.py` | Whole schema + seed data | 1 |
| `apps/api/alembic/seed/seed_0003.py` → `seed/seed_data.py` | Seed constants (countries, regulators, feeds, texts) | 1 |
| `apps/api/tests/conftest.py` | MariaDB fixtures, migrations, READ COMMITTED, `committed` | 1, 3 |
| `apps/api/tests/test_dialect.py` | AST lint: no Postgres SQL left in `app/` | 1–6 |
| `apps/api/app/core/rate_limit.py` | `hit()` fixed-window limits in `ops_rate_limits` | 2 |
| `apps/api/app/core/security.py` | Revocation + TOTP replay in MariaDB | 2 |
| `apps/api/app/core/cache.py` | **Deleted** | 2 |
| `apps/api/app/services/search.py` | Folding, boolean query builder, search columns | 3 |
| `apps/api/app/services/{articles,editorial,authors}.py` etc. | Ported SQL | 3–5 |
| `apps/api/app/api/public/views.py` | `POST /api/v1/views` beacon | 6 |
| `apps/api/app/core/hosts.py` | Host classification + routing middleware + admin SPA | 7 |
| `apps/api/app/core/page_cache.py` | Disk page cache: store, lookup, purge map, expiry, generation | 8 |
| `apps/api/app/jobs/{__init__,__main__,runner,tasks,selfcheck}.py` | Cron job runner and jobs | 9 |
| `apps/api/app/pipelines/{common,global_metrics,country_proxy,cross_check,ng_official_rate}.py` | Former DAGs | 10 |
| `apps/api/app/api/admin/system.py` + `apps/admin/src/pages/SystemHealth.jsx` | System health | 11 |
| `apps/api/app/site/static/css/site.css`, `apps/admin/src/styles.css` | Brand tokens | 12 |
| `apps/api/passenger_wsgi.py` | Passenger entry point | 13 |
| `deploy/{htaccess.public,htaccess.admin,deploy.sh,crontab.txt,env.example,check_env.py,test_check_env.py,test_htaccess.sh}` | Server kit | 13 |
| `.github/workflows/ci.yml` | Tests (MariaDB), wheel check, admin build, `release` branch | 14 |
| `infra/`, `pipelines/`, `db/init/`, old migrations, `app/cli/migrate.py` | **Deleted** | 14 |
| `docs/*.md`, `README.md`, `Makefile` | Rewritten for shared hosting | 14 |

## Table mapping

`schema.table` becomes `schema_table`, except that `market_data` becomes `market`, and a table already starting with
its schema name keeps its own name.

| Postgres | MariaDB |
|---|---|
| `auth.users`, `auth.password_tokens` | `auth_users`, `auth_password_tokens` |
| — (Redis) | `auth_revoked_tokens`, `auth_totp_used` |
| `content.articles`, `.article_sources`, `.article_media_links`, `.article_revisions`, `.article_reviews`, `.slug_redirects`, `.article_daily_views`, `.homepage_slots`, `.breaking_banner`, `.media`, `.countries`, `.regulators`, `.regulatory_entries`, `.regulatory_edit_history` | `content_articles`, `content_article_sources`, `content_article_media_links`, `content_article_revisions`, `content_article_reviews`, `content_slug_redirects`, `content_article_daily_views`, `content_homepage_slots`, `content_breaking_banner`, `content_media`, `content_countries`, `content_regulators`, `content_regulatory_entries`, `content_regulatory_edit_history` |
| `content.articles.countries TEXT[]` | `content_article_countries(article_id, country_code)` |
| `market_data.global_metrics`, `.country_proxy_metrics`, `.verified_annual_stats`, `.metric_edit_history`, `.data_quality_flags`, `.official_rates`, `.metric_trend_snapshots`, `.live_feeds` | `market_global_metrics`, `market_country_proxy_metrics`, `market_verified_annual_stats`, `market_metric_edit_history`, `market_data_quality_flags`, `market_official_rates`, `market_metric_trend_snapshots`, `market_live_feeds` |
| `site.snapshot_cards`, `site.ticker_items`, `site.site_text` | `site_snapshot_cards`, `site_ticker_items`, `site_text` |
| `audit.admin_log` | `audit_admin_log` |
| `newsletter.newsletter_subscribers`, `.newsletter_issues`, `.deliveries` | `newsletter_subscribers`, `newsletter_issues`, `newsletter_deliveries` |
| — (new) | `ops_rate_limits`, `ops_job_runs`, `ops_alert_state` |
| `content.article_media`, `market_data.metric_visibility`, `public.schema_migrations`, `newsletter_issues.html_url` | dropped (unused) |

## Porting rules (P1–P20)

Tasks 2–6 and 10 apply these to every SQL string they touch. `tests/test_dialect.py` enforces the mechanical ones.

| # | Postgres | MariaDB |
|---|---|---|
| P1 | `content.articles` (schema-qualified) | `content_articles` (table mapping above) |
| P2 | `now()`, `clock_timestamp()` | `UTC_TIMESTAMP(6)` (per statement in MariaDB, so it also replaces `clock_timestamp()`) |
| P3 | `CURRENT_DATE` | `UTC_DATE()` |
| P4 | `now() - interval '7 days'`, `interval '{n} hours'` | `UTC_TIMESTAMP(6) - INTERVAL 7 DAY`, `INTERVAL {n} HOUR` |
| P5 | `INSERT … ON CONFLICT (k) DO UPDATE SET c = EXCLUDED.c` | `INSERT … ON DUPLICATE KEY UPDATE c = VALUES(c)` |
| P6 | `INSERT … ON CONFLICT DO NOTHING` | `INSERT IGNORE …` |
| P7 | `INSERT … RETURNING …` | unchanged (MariaDB ≥10.5 supports it) |
| P8 | `UPDATE … RETURNING x` | `UPDATE …` then `SELECT x … WHERE <same key>` in the same transaction; for "update many and return them" use `SELECT … FOR UPDATE` first, then `UPDATE … WHERE id IN :ids` |
| P9 | `x = ANY(:list)`, `NOT (x = ANY(:list))` | `x IN :list` / `x NOT IN :list` with `text(...).bindparams(bindparam("list", expanding=True))` |
| P10 | `a IS DISTINCT FROM b` / `IS NOT DISTINCT FROM` | `NOT (a <=> b)` / `a <=> b` |
| P11 | `ORDER BY x DESC NULLS LAST` / `ASC NULLS FIRST` | `ORDER BY x IS NULL, x DESC` / `ORDER BY x IS NOT NULL, x ASC` |
| P12 | `SELECT DISTINCT ON (k) … ORDER BY k, ts DESC` | `SELECT … FROM (SELECT …, ROW_NUMBER() OVER (PARTITION BY k ORDER BY ts DESC) AS rn FROM t …) x WHERE rn = 1` |
| P13 | `ILIKE` | `LIKE` (collation is case- and accent-insensitive) |
| P14 | `CAST(:x AS jsonb)`, `'{}'::jsonb` | `:x` (a JSON string from `json.dumps`), `'{}'` |
| P15 | `json_agg(json_build_object(...) ORDER BY y)`, `COALESCE(…, '[]'::json)` | `JSON_ARRAYAGG(JSON_OBJECT(...) ORDER BY y)`, `COALESCE(…, JSON_ARRAY())`; parse in Python with `db_json()` |
| P16 | `to_jsonb(m)` (whole row) | `JSON_OBJECT('id', m.id, …every column…)`; parse with `db_json()` |
| P17 | `x ~ :pattern` | `x REGEXP :pattern` |
| P18 | `UPDATE t … WHERE ts = (SELECT MAX(ts) FROM t …)` (same table) | wrap: `WHERE ts = (SELECT m FROM (SELECT MAX(ts) AS m FROM t …) x)` |
| P19 | `date_trunc('hour', ts)` | `DATE_FORMAT(ts, '%Y-%m-%d %H:00:00')` |
| P20 | column `key` | `` `key` `` |

Reading JSON columns: MariaDB returns JSON as `str`. Wrap every read of `variants`, `checklist`, `detail`,
`countries` (revisions) and any `JSON_*` aggregate in `db_json(value, default)` from `app.core.db`.

---

### Task 1: MariaDB foundation (dev stack, driver, baseline schema, test harness)

**Files:**
- Modify: `docker-compose.yml` (replace whole file)
- Create: `docker/mariadb-init.sql`
- Modify: `apps/api/requirements.txt`; Create: `apps/api/requirements-dev.txt`
- Modify: `apps/api/Dockerfile`
- Modify: `apps/api/app/core/settings.py`, `apps/api/app/core/db.py`
- Create: `apps/api/app/core/envfile.py`
- Modify: `apps/api/alembic/env.py`
- Delete: `apps/api/alembic/versions/0001_baseline.py`, `0002_metric_visibility_unique_inserts.py`, `0003_launch_platform.py`, `0004_search_unaccent_sessions.py`, `db/init/001_schemas.sql`
- Move: `apps/api/alembic/seed/seed_0003.py` → `apps/api/alembic/seed/seed_data.py`
- Create: `apps/api/alembic/versions/0001_mariadb_baseline.py`
- Modify: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_db_mariadb.py`, `apps/api/tests/test_dialect.py`
- Modify: `apps/api/tests/test_schema_seed.py`

**Interfaces:**
- Produces:
  - `app.core.db.make_engine(url: str) -> Engine`
  - `app.core.db.engine`, `SessionLocal`, `get_db()`, `get_session_factory()`
  - `app.core.db.db_json(value, default=None)`
  - `app.core.db.named_lock(conn, name: str) -> bool` and `release_lock(conn, name: str) -> None`
  - `app.core.db.TABLE_OPTS: str`
  - `app.core.envfile.load_env(path: str) -> None`
  - settings `DATABASE_URL`, `DATA_DIR`
  - fixture `db_session` (READ COMMITTED, savepoints); `tests.test_dialect.NOT_YET_PORTED: set[str]`

- [ ] **Step 1: Replace the dev stack**

`docker-compose.yml`:

```yaml
# Local development only. Production is WhoGoHost shared hosting (see docs/DEPLOYMENT.md).
services:
  mariadb:
    image: mariadb:11.4
    command: ["--character-set-server=utf8mb4", "--collation-server=utf8mb4_uca1400_ai_ci",
              "--default-time-zone=+02:00"]   # like the host's SAST clock, so UTC handling is really tested
    environment:
      MARIADB_ROOT_PASSWORD: root_dev_password
      MARIADB_DATABASE: asi
      MARIADB_USER: asi
      MARIADB_PASSWORD: asi_dev_password
    ports: ["3306:3306"]
    volumes:
      - mariadb_data:/var/lib/mysql
      - ./docker/mariadb-init.sql:/docker-entrypoint-initdb.d/10-test-db.sql:ro
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 5s
      retries: 30

  mailhog:
    image: mailhog/mailhog:v1.0.1
    ports: ["1025:1025", "8025:8025"]

  api:
    build: ./apps/api
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    environment:
      DATABASE_URL: mysql+pymysql://asi:asi_dev_password@mariadb:3306/asi?charset=utf8mb4
      TEST_DATABASE_URL: mysql+pymysql://asi:asi_dev_password@mariadb:3306/asi_test?charset=utf8mb4
      SMTP_HOST: mailhog
      SMTP_PORT: "1025"
      SITE_URL: http://localhost:8000
      ADMIN_URL: http://localhost:5173
      MEDIA_ROOT: /app/media
      MEDIA_ORIGINALS_ROOT: /app/media-originals
      ASI_REPO: /repo                 # tests that read files outside apps/api (deploy kit, admin CSS)
    volumes: ["./apps/api:/app", ".:/repo:ro"]
    ports: ["8000:8000"]
    depends_on:
      mariadb: {condition: service_healthy}
      mailhog: {condition: service_started}

volumes:
  mariadb_data:
```

`docker/mariadb-init.sql`:

```sql
CREATE DATABASE IF NOT EXISTS asi_test CHARACTER SET utf8mb4 COLLATE utf8mb4_uca1400_ai_ci;
GRANT ALL PRIVILEGES ON asi_test.* TO 'asi'@'%';
FLUSH PRIVILEGES;
```

`apps/api/Dockerfile` (dev image only):

```dockerfile
# Development image. Production runs under Passenger on the shared host (no Docker there).
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Edit `apps/api/requirements.txt`:
- Remove: `psycopg2-binary`, `redis`, `gunicorn`, `uvicorn[standard]` / `uvicorn`, `boto3` (S3 backend unused on the host).
- Add: `PyMySQL==1.1.1`, `a2wsgi==1.10.7`.
- Keep the other pins as they are (`nh3==0.3.0` stays).

Create `apps/api/requirements-dev.txt`:

```
-r requirements.txt
uvicorn==0.30.6
pytest==8.3.3
httpx==0.27.2
```

(If `requirements.txt` already pins pytest or httpx, move those pins here.)

Remove `S3Storage` and the S3 settings from `app/core/storage.py` and `app/core/settings.py`. `get_storage()` always
returns `LocalStorage(MEDIA_ROOT, MEDIA_ORIGINALS_ROOT)`. Remove the `S3_SECRET_KEY` check from
`check_production_secrets`.

- [ ] **Step 2: Write the failing driver and schema tests**

`apps/api/tests/test_db_mariadb.py`:

```python
"""The MariaDB boundary: UTC everywhere, real booleans, utf8mb4, JSON helper, named locks."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.db import db_json, engine, named_lock, release_lock


def test_session_runs_in_utc(db_session):
    assert db_session.execute(text("SELECT @@session.time_zone")).scalar() == "+00:00"


def test_aware_times_round_trip_as_utc(db_session):
    lagos_nine = datetime(2026, 11, 2, 9, 0, tzinfo=ZoneInfo("Africa/Lagos"))
    db_session.execute(text("CREATE TEMPORARY TABLE tz_probe (t DATETIME(6))"))
    db_session.execute(text("INSERT INTO tz_probe VALUES (:t)"), {"t": lagos_nine})
    stored_text = db_session.execute(text("SELECT CAST(t AS CHAR) FROM tz_probe")).scalar()
    read_back = db_session.execute(text("SELECT t FROM tz_probe")).scalar()
    assert stored_text.startswith("2026-11-02 08:00:00")      # stored as UTC wall time
    assert read_back == lagos_nine and read_back.tzinfo == timezone.utc


def test_utc_timestamp_is_close_to_real_utc(db_session):
    db_now = db_session.execute(text("SELECT UTC_TIMESTAMP(6)")).scalar()
    assert abs(db_now - datetime.now(timezone.utc)) < timedelta(seconds=5)


def test_tinyint_columns_read_as_bool(db_session):
    db_session.execute(text("CREATE TEMPORARY TABLE b_probe (flag TINYINT(1))"))
    db_session.execute(text("INSERT INTO b_probe VALUES (1), (0)"))
    assert db_session.execute(text("SELECT flag FROM b_probe ORDER BY flag DESC")).scalars().all() == [True, False]


def test_emoji_and_accents_survive(db_session):
    db_session.execute(text("CREATE TEMPORARY TABLE s_probe (s VARCHAR(50)) CHARACTER SET utf8mb4"))
    db_session.execute(text("INSERT INTO s_probe VALUES (:s)"), {"s": "Côte d’Ivoire 🚀"})
    assert db_session.execute(text("SELECT s FROM s_probe")).scalar() == "Côte d’Ivoire 🚀"


def test_db_json_parses_strings_and_passes_objects():
    assert db_json('{"a": 1}') == {"a": 1}
    assert db_json({"a": 1}) == {"a": 1}
    assert db_json(None, []) == []


def test_named_lock_is_exclusive_and_released_when_connection_closes():
    first, second = engine.connect(), engine.connect()
    try:
        assert named_lock(first, "probe") is True
        assert named_lock(second, "probe") is False
        first.close()                                   # a crashed job's connection dies
        assert named_lock(second, "probe") is True
        release_lock(second, "probe")
    finally:
        second.close()
```

Rewrite `apps/api/tests/test_schema_seed.py` so it asserts on the MariaDB schema:

```python
from sqlalchemy import text


def _count(db, table):
    return db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def test_all_54_countries_with_regions(db_session):
    assert _count(db_session, "content_countries") == 54
    regions = {r[0] for r in db_session.execute(text("SELECT DISTINCT region FROM content_countries"))}
    assert regions == {"North", "West", "Central", "East", "Southern"}


def test_seeded_regulators_feeds_text_and_slots(db_session):
    assert _count(db_session, "content_regulators") >= 10
    assert _count(db_session, "market_live_feeds") >= 4
    assert _count(db_session, "site_text") >= 5
    assert _count(db_session, "content_homepage_slots") == 5
    assert _count(db_session, "content_breaking_banner") == 1
    assert _count(db_session, "site_snapshot_cards") >= 4
    assert _count(db_session, "site_ticker_items") >= 1


def test_honesty_rows_are_seeded(db_session):
    pending = db_session.execute(text(
        "SELECT is_verified, value FROM market_verified_annual_stats WHERE metric_key='country_onchain_value' AND country_code='KE'"
    )).first()
    assert pending == (False, None)


def test_every_table_uses_the_accent_insensitive_collation(db_session):
    wrong = db_session.execute(text(
        "SELECT table_name, table_collation FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name <> 'alembic_version' "
        "AND table_collation <> 'utf8mb4_uca1400_ai_ci'"
    )).all()
    assert wrong == []


def test_premium_is_computed_by_the_database(db_session):
    db_session.execute(text(
        "INSERT INTO market_country_proxy_metrics (ts, country_code, pair, p2p_rate, official_rate, source) "
        "VALUES (UTC_TIMESTAMP(6), 'NG', 'USDTNGN', 1600, 1500, 'test')"
    ))
    premium = db_session.execute(text(
        "SELECT premium_pct FROM market_country_proxy_metrics WHERE source='test'")).scalar()
    assert round(float(premium), 2) == 6.67


def test_lowercase_country_code_is_rejected(db_session):
    import pytest
    from sqlalchemy.exc import OperationalError, IntegrityError
    with pytest.raises((OperationalError, IntegrityError)):
        db_session.execute(text(
            "INSERT INTO content_countries (code, name, slug, region) VALUES ('zz', 'Zed', 'zed', 'West')"))
```

`apps/api/tests/test_dialect.py`:

```python
"""Static check: SQL inside app/ must be MariaDB SQL. Each porting task removes
its modules from NOT_YET_PORTED; Task 6 leaves the set empty."""

import ast
import pathlib
import re

import pytest

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
SQL_HINT = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", re.IGNORECASE)
FORBIDDEN = {
    "postgres cast ::": re.compile(r"\w::\w"),
    "schema-qualified table": re.compile(r"\b(auth|content|market_data|newsletter|site|audit)\.[a-z_]+\b(?!\()"),
    "ON CONFLICT": re.compile(r"\bON CONFLICT\b", re.I),
    "ILIKE": re.compile(r"\bILIKE\b", re.I),
    "NULLS FIRST/LAST": re.compile(r"\bNULLS (FIRST|LAST)\b", re.I),
    "DISTINCT FROM": re.compile(r"\bIS (NOT )?DISTINCT FROM\b", re.I),
    "DISTINCT ON": re.compile(r"\bDISTINCT ON\b", re.I),
    "ANY(": re.compile(r"\bANY\s*\(", re.I),
    "now()/clock_timestamp()": re.compile(r"\b(now|clock_timestamp)\(\)", re.I),
    "CURRENT_DATE": re.compile(r"\bCURRENT_DATE\b"),
    "interval literal": re.compile(r"interval '", re.I),
    "postgres json functions": re.compile(r"\b(jsonb|json_agg|json_build_object|to_jsonb|string_agg|array_agg)\b", re.I),
    "pg_ functions": re.compile(r"\bpg_\w+\(", re.I),
    "date_trunc / EXTRACT(EPOCH": re.compile(r"\bdate_trunc\b|EXTRACT\(EPOCH", re.I),
    "full-text (postgres)": re.compile(r"websearch_to_tsquery|ts_rank|tsvector|f_unaccent", re.I),
    "UPDATE … RETURNING": re.compile(r"\bUPDATE\b[^;]*?\bRETURNING\b", re.I | re.S),
    "array overlap &&": re.compile(r"&&"),
    "regex ~": re.compile(r"\s~\s"),
    "unquoted key column": re.compile(r"(?<!PRIMARY )(?<!FOREIGN )(?<!UNIQUE )(?<!DUPLICATE )(?<![`\w])key(?![`\w])", re.I),
}

# Removed task by task (Tasks 2–6). Must be empty by the end of Task 6.
NOT_YET_PORTED = {
    "api/admin/articles.py", "api/admin/audit.py", "api/admin/auth.py", "api/admin/countries.py",
    "api/admin/dashboard.py", "api/admin/flags.py", "api/admin/fx.py", "api/admin/homepage.py",
    "api/admin/media.py", "api/admin/metrics.py", "api/admin/newsletter.py", "api/admin/regulatory.py",
    "api/admin/site_text.py", "api/admin/snapshot.py", "api/admin/users.py", "api/public/countries.py",
    "api/public/home.py", "api/public/metrics.py", "api/public/news.py", "api/public/newsletter.py",
    "api/health.py", "cli/bootstrap_admin.py", "cli/migrate.py", "cli/regenerate_media.py", "cli/seed_demo.py",
    "core/audit.py", "core/security.py", "seo/routes.py", "services/articles.py", "services/authors.py",
    "services/countries.py", "services/editorial.py", "services/homepage.py", "services/images.py",
    "services/live.py", "services/media.py", "services/newsletter.py", "services/site_text.py",
    "services/snapshot.py", "services/views.py", "site/routes.py",
}


def _sql_strings(path: pathlib.Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and SQL_HINT.search(node.value):
            yield node.lineno, node.value


FILES = sorted(p for p in APP.rglob("*.py"))


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.relative_to(APP).as_posix())
def test_sql_is_mariadb(path):
    rel = path.relative_to(APP).as_posix()
    if rel in NOT_YET_PORTED:
        pytest.skip("not ported yet")
    problems = [f"line {line}: {name}" for line, sql in _sql_strings(path)
                for name, rx in FORBIDDEN.items() if rx.search(sql)]
    assert problems == []
```

Note: the "unquoted key column" rule ignores `metric_key`, `PRIMARY KEY` etc. If a legitimate English "key"
appears in a SQL string, write it as `` `key` `` anyway.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `docker compose up -d mariadb mailhog && docker compose run --rm api pytest tests/test_db_mariadb.py tests/test_schema_seed.py tests/test_dialect.py -q`
Expected: errors on import (`psycopg2` URL / `make_engine` missing) or failures. Not a pass.

- [ ] **Step 4: Settings, env file loader, engine and converters**

In `app/core/settings.py`:
- Replace the `DATABASE_URL` default with `"mysql+pymysql://asi:asi_dev_password@localhost:3306/asi?charset=utf8mb4"`.
- Delete `REDIS_URL`.
- Update `_db_password` so it handles `mysql+pymysql://user:pw@host/db` (same parsing works; keep).
- Add:

```python
# Persistent private data on the server: originals, backups, job logs.
DATA_DIR = os.environ.get("DATA_DIR", os.path.expanduser("~/asi-data"))
```

`app/core/envfile.py`:

```python
"""Loads KEY=VALUE lines from the server's .env into os.environ (never
overriding what is already set). Passenger and cron start Python without our
environment, so passenger_wsgi.py and the job runner call this first."""

import os


def load_env(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
```

`app/core/db.py` (replace whole file):

```python
"""Database access for MariaDB 11.4.

The driver boundary does the UTC work once, for everyone:
- every connection runs in UTC (`SET time_zone = '+00:00'`), whatever the
  server's own clock says (the host runs SAST);
- aware datetimes are converted to UTC before they are written;
- DATETIME values come back as aware UTC datetimes;
- TINYINT columns (used only for booleans) come back as bool.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from pymysql import converters
from pymysql.constants import FIELD_TYPE
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import DATABASE_URL

TABLE_OPTS = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci"
SESSION_INIT = ("SET time_zone = '+00:00', collation_connection = 'utf8mb4_uca1400_ai_ci', "
                "sql_mode = 'STRICT_ALL_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,"
                "NO_ENGINE_SUBSTITUTION'")


def _escape_datetime(value: datetime, mapping=None) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return converters.escape_datetime(value, mapping)


def _read_datetime(raw):
    value = converters.convert_datetime(raw)
    return value.replace(tzinfo=timezone.utc) if isinstance(value, datetime) else value


def _read_bool(raw) -> bool:
    return int(raw) != 0


CONVERSIONS = dict(converters.conversions)
CONVERSIONS[datetime] = _escape_datetime
CONVERSIONS[FIELD_TYPE.DATETIME] = _read_datetime
CONVERSIONS[FIELD_TYPE.TIMESTAMP] = _read_datetime
CONVERSIONS[FIELD_TYPE.TINY] = _read_bool


def make_engine(url: str = DATABASE_URL, **overrides) -> Engine:
    options = dict(
        pool_pre_ping=True, pool_size=3, max_overflow=2, pool_recycle=280,
        isolation_level="READ COMMITTED",
        connect_args={"conv": CONVERSIONS, "init_command": SESSION_INIT, "charset": "utf8mb4"},
    )
    options.update(overrides)
    return create_engine(url, **options)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_factory():
    """For work that outlives the request. Tests override this."""
    return SessionLocal


def db_json(value, default=None):
    """MariaDB returns JSON columns and JSON_* results as text; parse them."""
    if value is None:
        return default
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf8")
    if isinstance(value, str):
        return json.loads(value)
    return value


def named_lock(conn: Connection, name: str) -> bool:
    """A server-wide lock namespaced by database (the server is shared). Held
    by this connection until release_lock() or until the connection dies."""
    got = conn.execute(text("SELECT GET_LOCK(CONCAT(DATABASE(), ':', :n), 0)"), {"n": name}).scalar()
    return bool(got)


def release_lock(conn: Connection, name: str) -> None:
    conn.execute(text("SELECT RELEASE_LOCK(CONCAT(DATABASE(), ':', :n))"), {"n": name})
```

Note: `GET_LOCK` returns an integer column (type LONGLONG, not TINY), so `bool()` is applied explicitly.

`apps/api/alembic/env.py`: replace `engine_from_config(...)` with the shared factory so migrations run with the
same session settings:

```python
from app.core.db import make_engine  # noqa: E402
...
def run_migrations_online() -> None:
    connectable = make_engine(DATABASE_URL, poolclass=pool.NullPool, pool_size=None, max_overflow=None,
                              pool_recycle=-1)
```

`create_engine` rejects `pool_size`/`max_overflow` together with `NullPool`. So `make_engine` must drop any
override whose value is `None`: change `options.update(overrides)` to
`options.update(overrides); options = {k: v for k, v in options.items() if v is not None}`. With `NullPool`, also
remove `pool_size`, `max_overflow` and `pool_recycle`; passing `None` for each does exactly that.

- [ ] **Step 5: Write the baseline migration**

`git mv apps/api/alembic/seed/seed_0003.py apps/api/alembic/seed/seed_data.py`. Delete the four old versions and
`db/init/001_schemas.sql`.

`apps/api/alembic/versions/0001_mariadb_baseline.py`:

```python
"""MariaDB baseline: the whole ASI schema plus seed data (54 countries,
regulators, regulatory entries, live feeds, report figures, snapshot cards,
ticker, site text, homepage slots). Replaces the four Postgres migrations;
there is no production data to carry over.

Revision ID: 0001
Revises:
Create Date: 2026-10-09
"""
import os
import sys
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed"))
import seed_data as seed  # noqa: E402

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OPTS = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci"
NOW = "DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)"   # session time_zone is +00:00, so this is UTC

TABLES = [
    f"""CREATE TABLE auth_users (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      name VARCHAR(200) NOT NULL,
      email VARCHAR(254) NOT NULL,
      password_hash VARCHAR(255) NOT NULL,
      role VARCHAR(10) NOT NULL,
      is_active TINYINT(1) NOT NULL DEFAULT 1,
      slug VARCHAR(200) NULL,
      title VARCHAR(200) NULL,
      bio TEXT NULL,
      avatar_media_id INT UNSIGNED NULL,
      totp_secret VARCHAR(500) NULL,
      totp_enabled TINYINT(1) NOT NULL DEFAULT 0,
      last_login_at DATETIME(6) NULL,
      sessions_valid_after DATETIME(6) NULL,
      created_at {NOW},
      UNIQUE KEY users_email_uq (email),
      UNIQUE KEY users_slug_uq (slug),
      CONSTRAINT users_role_ck CHECK (role IN ('author','editor','admin'))
    ) {OPTS}""",
    f"""CREATE TABLE auth_password_tokens (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      user_id INT UNSIGNED NOT NULL,
      token_hash VARCHAR(128) NOT NULL,
      purpose VARCHAR(10) NOT NULL,
      expires_at DATETIME(6) NOT NULL,
      used_at DATETIME(6) NULL,
      created_at {NOW},
      UNIQUE KEY password_tokens_hash_uq (token_hash),
      CONSTRAINT password_tokens_purpose_ck CHECK (purpose IN ('invite','reset')),
      CONSTRAINT password_tokens_user_fk FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE
    ) {OPTS}""",
    f"""CREATE TABLE auth_revoked_tokens (
      jti VARCHAR(64) PRIMARY KEY,
      expires_at DATETIME(6) NOT NULL,
      KEY revoked_expires_idx (expires_at)
    ) {OPTS}""",
    f"""CREATE TABLE auth_totp_used (
      user_id INT UNSIGNED NOT NULL,
      code VARCHAR(10) NOT NULL,
      used_at {NOW},
      PRIMARY KEY (user_id, code),
      KEY totp_used_at_idx (used_at)
    ) {OPTS}""",
    f"""CREATE TABLE content_media (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      object_key VARCHAR(255) NOT NULL,
      original_filename VARCHAR(255) NULL,
      width INT NOT NULL,
      height INT NOT NULL,
      alt_text VARCHAR(500) NOT NULL DEFAULT '',
      caption TEXT NULL,
      credit VARCHAR(300) NULL,
      licence VARCHAR(20) NOT NULL DEFAULT 'own',
      licence_note TEXT NULL,
      focal_x DOUBLE NOT NULL DEFAULT 0.5,
      focal_y DOUBLE NOT NULL DEFAULT 0.5,
      variants JSON NOT NULL DEFAULT '{{}}',
      uploaded_by INT UNSIGNED NULL,
      uploaded_at {NOW},
      UNIQUE KEY media_object_key_uq (object_key),
      KEY media_uploaded_idx (uploaded_at),
      CONSTRAINT media_licence_ck CHECK (licence IN ('own','licensed','creative_commons','public_domain','courtesy')),
      CONSTRAINT media_focal_ck CHECK (focal_x BETWEEN 0 AND 1 AND focal_y BETWEEN 0 AND 1),
      CONSTRAINT media_uploaded_by_fk FOREIGN KEY (uploaded_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    """ALTER TABLE auth_users ADD CONSTRAINT users_avatar_fk
         FOREIGN KEY (avatar_media_id) REFERENCES content_media(id) ON DELETE SET NULL""",
    f"""CREATE TABLE content_countries (
      code CHAR(2) PRIMARY KEY,
      name VARCHAR(100) NOT NULL,
      slug VARCHAR(100) NOT NULL,
      currency VARCHAR(10) NULL,
      region VARCHAR(10) NOT NULL,
      status VARCHAR(12) NOT NULL DEFAULT 'researching',
      coverage VARCHAR(12) NOT NULL DEFAULT 'monitoring',
      summary TEXT NULL,
      compliance_md MEDIUMTEXT NULL,
      sort_order INT NOT NULL DEFAULT 100,
      updated_by INT UNSIGNED NULL,
      updated_at {NOW},
      UNIQUE KEY countries_slug_uq (slug),
      CONSTRAINT countries_code_ck CHECK (CAST(code AS BINARY) REGEXP '^[A-Z]{{2}}$'),
      CONSTRAINT countries_region_ck CHECK (region IN ('North','West','Central','East','Southern')),
      CONSTRAINT countries_status_ck CHECK (status IN ('in_force','developing','researching')),
      CONSTRAINT countries_coverage_ck CHECK (coverage IN ('active','monitoring')),
      CONSTRAINT countries_updated_by_fk FOREIGN KEY (updated_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE content_regulators (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      country_code CHAR(2) NOT NULL,
      name VARCHAR(300) NOT NULL,
      abbreviation VARCHAR(50) NULL,
      scope TEXT NULL,
      website_url VARCHAR(2048) NULL,
      register_url VARCHAR(2048) NULL,
      sort_order INT NOT NULL DEFAULT 100,
      UNIQUE KEY regulators_country_name_uq (country_code, name),
      CONSTRAINT regulators_country_fk FOREIGN KEY (country_code) REFERENCES content_countries(code) ON DELETE CASCADE
    ) {OPTS}""",
    f"""CREATE TABLE content_regulatory_entries (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      country_code CHAR(2) NOT NULL,
      regulation_name VARCHAR(300) NOT NULL,
      status VARCHAR(12) NOT NULL,
      summary_md MEDIUMTEXT NOT NULL,
      source_url VARCHAR(2048) NOT NULL,
      effective_date DATE NULL,
      last_verified_at DATETIME(6) NOT NULL,
      is_published TINYINT(1) NOT NULL DEFAULT 1,
      updated_by INT UNSIGNED NULL,
      updated_at {NOW},
      KEY regulatory_entries_country_idx (country_code),
      CONSTRAINT regulatory_status_ck CHECK (status IN ('in_force','developing','pending')),
      CONSTRAINT regulatory_updated_by_fk FOREIGN KEY (updated_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE content_regulatory_edit_history (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      entry_id INT UNSIGNED NOT NULL,
      field_name VARCHAR(100) NOT NULL,
      old_value TEXT NULL,
      new_value TEXT NULL,
      changed_by INT UNSIGNED NOT NULL,
      changed_at {NOW},
      CONSTRAINT reg_history_entry_fk FOREIGN KEY (entry_id) REFERENCES content_regulatory_entries(id) ON DELETE CASCADE,
      CONSTRAINT reg_history_user_fk FOREIGN KEY (changed_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE content_articles (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      slug VARCHAR(200) NOT NULL,
      title VARCHAR(300) NOT NULL,
      dek TEXT NULL,
      body_md MEDIUMTEXT NOT NULL,
      tag VARCHAR(20) NOT NULL,
      status VARCHAR(20) NOT NULL DEFAULT 'draft',
      author_id INT UNSIGNED NOT NULL,
      reviewed_by INT UNSIGNED NULL,
      is_featured TINYINT(1) NOT NULL DEFAULT 0,
      published_at DATETIME(6) NULL,
      created_at {NOW},
      updated_at {NOW},
      seo_description VARCHAR(300) NULL,
      cover_media_id INT UNSIGNED NULL,
      correction_md TEXT NULL,
      correction_at DATETIME(6) NULL,
      view_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
      word_count INT UNSIGNED NOT NULL DEFAULT 0,
      search_title VARCHAR(300) NOT NULL DEFAULT '',
      search_body MEDIUMTEXT NULL,
      UNIQUE KEY articles_slug_uq (slug),
      KEY articles_status_published_idx (status, published_at),
      FULLTEXT KEY articles_ft_title (search_title),
      FULLTEXT KEY articles_ft_all (search_title, search_body),
      CONSTRAINT articles_tag_ck CHECK (tag IN ('Regulation','Markets')),
      CONSTRAINT articles_status_ck CHECK (status IN ('draft','in_review','scheduled','published')),
      CONSTRAINT articles_no_self_review_ck CHECK (reviewed_by IS NULL OR reviewed_by <> author_id),
      CONSTRAINT articles_slug_format_ck CHECK (CAST(slug AS BINARY) REGEXP '^[a-z0-9]+(-[a-z0-9]+)*$'),
      CONSTRAINT articles_author_fk FOREIGN KEY (author_id) REFERENCES auth_users(id),
      CONSTRAINT articles_reviewer_fk FOREIGN KEY (reviewed_by) REFERENCES auth_users(id),
      CONSTRAINT articles_cover_fk FOREIGN KEY (cover_media_id) REFERENCES content_media(id) ON DELETE SET NULL
    ) {OPTS}""",
    f"""CREATE TABLE content_article_countries (
      article_id INT UNSIGNED NOT NULL,
      country_code CHAR(2) NOT NULL,
      PRIMARY KEY (article_id, country_code),
      KEY article_countries_country_idx (country_code, article_id),
      CONSTRAINT article_countries_article_fk FOREIGN KEY (article_id) REFERENCES content_articles(id) ON DELETE CASCADE,
      CONSTRAINT article_countries_country_fk FOREIGN KEY (country_code) REFERENCES content_countries(code)
    ) {OPTS}""",
    f"""CREATE TABLE content_article_sources (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      article_id INT UNSIGNED NOT NULL,
      source_name VARCHAR(300) NOT NULL,
      source_url VARCHAR(2048) NOT NULL,
      CONSTRAINT article_sources_article_fk FOREIGN KEY (article_id) REFERENCES content_articles(id) ON DELETE CASCADE
    ) {OPTS}""",
    f"""CREATE TABLE content_article_media_links (
      article_id INT UNSIGNED NOT NULL,
      media_id INT UNSIGNED NOT NULL,
      role VARCHAR(10) NOT NULL,
      PRIMARY KEY (article_id, media_id, role),
      CONSTRAINT media_links_role_ck CHECK (role IN ('cover','inline')),
      CONSTRAINT media_links_article_fk FOREIGN KEY (article_id) REFERENCES content_articles(id) ON DELETE CASCADE,
      CONSTRAINT media_links_media_fk FOREIGN KEY (media_id) REFERENCES content_media(id)
    ) {OPTS}""",
    f"""CREATE TABLE content_article_revisions (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      article_id INT UNSIGNED NOT NULL,
      title VARCHAR(300) NOT NULL,
      dek TEXT NULL,
      body_md MEDIUMTEXT NOT NULL,
      tag VARCHAR(20) NOT NULL,
      countries JSON NULL,
      edited_by INT UNSIGNED NULL,
      edited_at {NOW},
      KEY article_revisions_article_idx (article_id, edited_at),
      CONSTRAINT revisions_article_fk FOREIGN KEY (article_id) REFERENCES content_articles(id) ON DELETE CASCADE,
      CONSTRAINT revisions_user_fk FOREIGN KEY (edited_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE content_article_reviews (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      article_id INT UNSIGNED NOT NULL,
      reviewer_id INT UNSIGNED NOT NULL,
      decision VARCHAR(20) NOT NULL,
      note TEXT NULL,
      checklist JSON NOT NULL DEFAULT '{{}}',
      created_at {NOW},
      CONSTRAINT reviews_decision_ck CHECK (decision IN ('approved','changes_requested')),
      CONSTRAINT reviews_article_fk FOREIGN KEY (article_id) REFERENCES content_articles(id) ON DELETE CASCADE,
      CONSTRAINT reviews_user_fk FOREIGN KEY (reviewer_id) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE content_slug_redirects (
      old_slug VARCHAR(200) PRIMARY KEY,
      article_id INT UNSIGNED NOT NULL,
      created_at {NOW},
      CONSTRAINT redirects_article_fk FOREIGN KEY (article_id) REFERENCES content_articles(id) ON DELETE CASCADE
    ) {OPTS}""",
    f"""CREATE TABLE content_article_daily_views (
      article_id INT UNSIGNED NOT NULL,
      day DATE NOT NULL,
      views INT UNSIGNED NOT NULL DEFAULT 0,
      PRIMARY KEY (article_id, day),
      KEY daily_views_day_idx (day),
      CONSTRAINT daily_views_article_fk FOREIGN KEY (article_id) REFERENCES content_articles(id) ON DELETE CASCADE
    ) {OPTS}""",
    f"""CREATE TABLE content_homepage_slots (
      slot VARCHAR(20) PRIMARY KEY,
      article_id INT UNSIGNED NULL,
      expires_at DATETIME(6) NULL,
      updated_by INT UNSIGNED NULL,
      updated_at {NOW},
      CONSTRAINT slots_slot_ck CHECK (slot IN ('lead','secondary_1','secondary_2','markets_lead','regulation_lead')),
      CONSTRAINT slots_article_fk FOREIGN KEY (article_id) REFERENCES content_articles(id) ON DELETE SET NULL,
      CONSTRAINT slots_user_fk FOREIGN KEY (updated_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE content_breaking_banner (
      id SMALLINT UNSIGNED PRIMARY KEY DEFAULT 1,
      text TEXT NULL,
      article_id INT UNSIGNED NULL,
      is_active TINYINT(1) NOT NULL DEFAULT 0,
      expires_at DATETIME(6) NULL,
      updated_by INT UNSIGNED NULL,
      updated_at {NOW},
      CONSTRAINT banner_single_row_ck CHECK (id = 1),
      CONSTRAINT banner_article_fk FOREIGN KEY (article_id) REFERENCES content_articles(id) ON DELETE SET NULL,
      CONSTRAINT banner_user_fk FOREIGN KEY (updated_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE market_live_feeds (
      `key` VARCHAR(100) PRIMARY KEY,
      label VARCHAR(200) NOT NULL,
      unit VARCHAR(5) NOT NULL,
      country_code CHAR(2) NULL,
      source_name VARCHAR(200) NOT NULL,
      stale_after_minutes INT NOT NULL,
      CONSTRAINT live_feeds_unit_ck CHECK (unit IN ('usd','pct')),
      CONSTRAINT live_feeds_stale_ck CHECK (stale_after_minutes > 0)
    ) {OPTS}""",
    f"""CREATE TABLE market_global_metrics (
      id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      ts DATETIME(6) NOT NULL,
      stablecoin_supply_usd DECIMAL(30,10) NULL,
      usdt_share_pct DECIMAL(30,10) NULL,
      usdc_share_pct DECIMAL(30,10) NULL,
      source VARCHAR(50) NOT NULL,
      fetched_at {NOW},
      KEY global_metrics_ts_idx (ts)
    ) {OPTS}""",
    f"""CREATE TABLE market_country_proxy_metrics (
      id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      ts DATETIME(6) NOT NULL,
      country_code CHAR(2) NOT NULL,
      pair VARCHAR(20) NOT NULL,
      p2p_rate DECIMAL(30,10) NULL,
      official_rate DECIMAL(30,10) NULL,
      premium_pct DECIMAL(30,10) AS (CASE WHEN official_rate > 0
                                     THEN (p2p_rate - official_rate) / official_rate * 100 ELSE NULL END) PERSISTENT,
      source VARCHAR(50) NOT NULL,
      fetched_at {NOW},
      KEY country_proxy_country_ts_idx (country_code, ts),
      KEY country_proxy_ts_idx (ts)
    ) {OPTS}""",
    f"""CREATE TABLE market_verified_annual_stats (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      metric_key VARCHAR(100) NOT NULL,
      country_code CHAR(2) NULL,
      country_key CHAR(2) AS (COALESCE(country_code, '')) PERSISTENT,
      value DECIMAL(30,4) NULL,
      display_value VARCHAR(100) NULL,
      yoy_change_pct DECIMAL(12,4) NULL,
      is_verified TINYINT(1) NOT NULL DEFAULT 1,
      pending_note TEXT NULL,
      source_name VARCHAR(300) NOT NULL,
      source_period VARCHAR(100) NULL,
      label VARCHAR(200) NULL,
      badge VARCHAR(10) NOT NULL DEFAULT 'Report',
      sample_note TEXT NULL,
      updated_by INT UNSIGNED NULL,
      updated_at {NOW},
      UNIQUE KEY verified_stats_key_country_uq (metric_key, country_key),
      CONSTRAINT verified_stats_badge_ck CHECK (badge IN ('Report','Survey')),
      CONSTRAINT verified_stats_user_fk FOREIGN KEY (updated_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE market_metric_edit_history (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      record_id INT UNSIGNED NOT NULL,
      field_name VARCHAR(100) NOT NULL,
      old_value TEXT NULL,
      new_value TEXT NULL,
      changed_by INT UNSIGNED NOT NULL,
      changed_at {NOW},
      CONSTRAINT metric_history_record_fk FOREIGN KEY (record_id) REFERENCES market_verified_annual_stats(id),
      CONSTRAINT metric_history_user_fk FOREIGN KEY (changed_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE market_data_quality_flags (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      flagged_at {NOW},
      metric_key VARCHAR(100) NOT NULL,
      variance_pct DECIMAL(30,4) NULL,
      detail JSON NULL,
      resolved TINYINT(1) NOT NULL DEFAULT 0,
      resolved_by INT UNSIGNED NULL,
      resolved_at DATETIME(6) NULL,
      KEY flags_open_idx (metric_key, resolved, flagged_at),
      CONSTRAINT flags_user_fk FOREIGN KEY (resolved_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE market_official_rates (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      country_code CHAR(2) NOT NULL,
      pair VARCHAR(20) NOT NULL,
      rate DECIMAL(30,10) NOT NULL,
      source_name VARCHAR(300) NOT NULL,
      effective_date DATE NOT NULL,
      updated_by INT UNSIGNED NULL,
      updated_at {NOW},
      UNIQUE KEY official_rates_country_pair_uq (country_code, pair),
      CONSTRAINT official_rates_user_fk FOREIGN KEY (updated_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE market_metric_trend_snapshots (
      metric_key VARCHAR(100) NOT NULL,
      ts DATETIME(6) NOT NULL,
      value DECIMAL(30,10) NOT NULL,
      PRIMARY KEY (metric_key, ts)
    ) {OPTS}""",
    f"""CREATE TABLE site_snapshot_cards (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      zone VARCHAR(10) NOT NULL,
      kind VARCHAR(10) NOT NULL,
      live_feed_key VARCHAR(100) NULL,
      report_stat_id INT UNSIGNED NULL,
      label_override VARCHAR(200) NULL,
      is_visible TINYINT(1) NOT NULL DEFAULT 1,
      is_highlighted TINYINT(1) NOT NULL DEFAULT 0,
      sort_order INT NOT NULL DEFAULT 100,
      updated_by INT UNSIGNED NULL,
      updated_at {NOW},
      CONSTRAINT cards_zone_ck CHECK (zone IN ('metrics','countries')),
      CONSTRAINT cards_kind_ck CHECK (kind IN ('live','report')),
      CONSTRAINT cards_source_ck CHECK ((kind = 'live' AND live_feed_key IS NOT NULL)
                                        OR (kind = 'report' AND report_stat_id IS NOT NULL)),
      CONSTRAINT cards_feed_fk FOREIGN KEY (live_feed_key) REFERENCES market_live_feeds(`key`),
      CONSTRAINT cards_stat_fk FOREIGN KEY (report_stat_id) REFERENCES market_verified_annual_stats(id) ON DELETE CASCADE,
      CONSTRAINT cards_user_fk FOREIGN KEY (updated_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE site_ticker_items (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      live_feed_key VARCHAR(100) NOT NULL,
      label VARCHAR(200) NOT NULL,
      is_visible TINYINT(1) NOT NULL DEFAULT 1,
      sort_order INT NOT NULL DEFAULT 100,
      updated_by INT UNSIGNED NULL,
      updated_at {NOW},
      CONSTRAINT ticker_feed_fk FOREIGN KEY (live_feed_key) REFERENCES market_live_feeds(`key`),
      CONSTRAINT ticker_user_fk FOREIGN KEY (updated_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE site_text (
      `key` VARCHAR(100) PRIMARY KEY,
      value_md MEDIUMTEXT NOT NULL,
      updated_by INT UNSIGNED NULL,
      updated_at {NOW},
      CONSTRAINT site_text_user_fk FOREIGN KEY (updated_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE audit_admin_log (
      id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      user_id INT UNSIGNED NULL,
      action VARCHAR(100) NOT NULL,
      entity VARCHAR(50) NOT NULL,
      entity_id VARCHAR(100) NULL,
      detail JSON NOT NULL DEFAULT '{{}}',
      at {NOW},
      KEY admin_log_at_idx (at),
      KEY admin_log_entity_idx (entity, entity_id),
      CONSTRAINT admin_log_user_fk FOREIGN KEY (user_id) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE newsletter_subscribers (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      email VARCHAR(254) NOT NULL,
      status VARCHAR(15) NOT NULL DEFAULT 'pending',
      consent_at DATETIME(6) NULL,
      confirmed_at DATETIME(6) NULL,
      unsubscribed_at DATETIME(6) NULL,
      confirm_token VARCHAR(100) NULL,
      token_expires_at DATETIME(6) NULL,
      source_page VARCHAR(300) NULL,
      unsubscribe_token VARCHAR(100) NULL,
      consent_text TEXT NULL,
      created_at {NOW},
      UNIQUE KEY subscribers_email_uq (email),
      UNIQUE KEY subscribers_confirm_token_uq (confirm_token),
      UNIQUE KEY subscribers_unsubscribe_token_uq (unsubscribe_token),
      CONSTRAINT subscribers_status_ck CHECK (status IN ('pending','confirmed','unsubscribed'))
    ) {OPTS}""",
    f"""CREATE TABLE newsletter_issues (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      issue_number INT NOT NULL,
      subject VARCHAR(300) NOT NULL,
      slug VARCHAR(200) NULL,
      body_md MEDIUMTEXT NOT NULL DEFAULT '',
      status VARCHAR(10) NOT NULL DEFAULT 'draft',
      recipient_count INT NOT NULL DEFAULT 0,
      in_archive TINYINT(1) NOT NULL DEFAULT 0,
      sent_at DATETIME(6) NULL,
      created_by INT UNSIGNED NULL,
      created_at {NOW},
      updated_at {NOW},
      UNIQUE KEY issues_number_uq (issue_number),
      UNIQUE KEY issues_slug_uq (slug),
      CONSTRAINT issues_status_ck CHECK (status IN ('draft','sending','sent')),
      CONSTRAINT issues_user_fk FOREIGN KEY (created_by) REFERENCES auth_users(id)
    ) {OPTS}""",
    f"""CREATE TABLE newsletter_deliveries (
      issue_id INT UNSIGNED NOT NULL,
      subscriber_id INT UNSIGNED NOT NULL,
      status VARCHAR(10) NOT NULL DEFAULT 'queued',
      error TEXT NULL,
      sent_at DATETIME(6) NULL,
      PRIMARY KEY (issue_id, subscriber_id),
      KEY deliveries_sent_idx (status, sent_at),
      CONSTRAINT deliveries_status_ck CHECK (status IN ('queued','sent','failed')),
      CONSTRAINT deliveries_issue_fk FOREIGN KEY (issue_id) REFERENCES newsletter_issues(id) ON DELETE CASCADE,
      CONSTRAINT deliveries_subscriber_fk FOREIGN KEY (subscriber_id) REFERENCES newsletter_subscribers(id) ON DELETE CASCADE
    ) {OPTS}""",
    f"""CREATE TABLE ops_rate_limits (
      bucket VARCHAR(200) NOT NULL,
      window_start DATETIME NOT NULL,
      hits INT UNSIGNED NOT NULL DEFAULT 0,
      PRIMARY KEY (bucket, window_start),
      KEY rate_limits_window_idx (window_start)
    ) {OPTS}""",
    f"""CREATE TABLE ops_job_runs (
      id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      job VARCHAR(50) NOT NULL,
      started_at {NOW},
      finished_at DATETIME(6) NULL,
      status VARCHAR(10) NOT NULL DEFAULT 'running',
      detail TEXT NULL,
      error TEXT NULL,
      KEY job_runs_job_idx (job, started_at),
      CONSTRAINT job_runs_status_ck CHECK (status IN ('running','ok','failed','skipped'))
    ) {OPTS}""",
    f"""CREATE TABLE ops_alert_state (
      job VARCHAR(50) PRIMARY KEY,
      alerted_at {NOW}
    ) {OPTS}""",
]

VERIFIED_STATS = [
    ("ssa_onchain_value", None, 205000000000, "$205B", 52, True, None),
    ("country_onchain_value", "NG", 92100000000, "$92.1B", None, True, None),
    ("country_onchain_value", "ZA", 31400000000, "$31.4B", None, True, None),
    ("country_onchain_value", "KE", None, None, None, False, "top five, exact figure pending"),
    ("country_onchain_value", "GH", None, None, None, False, "top five, exact figure pending"),
    ("stablecoin_ownership_pct", None, 79, "79%", None, True, None),
]
STAT_SOURCES = {"stablecoin_ownership_pct": ("BVNK Stablecoin Utility Report 2026", "Feb 2026")}
OFFICIAL_RATES = [
    ("NG", "USDTNGN", 1530.00, "CBN official rate (seed placeholder — update in admin)"),
    ("ZA", "USDCZAR", 17.80, "SARB reference rate (seed placeholder — update in admin)"),
    ("KE", "USDKES", 129.00, "CBK indicative rate (seed placeholder — update in admin)"),
]


def upgrade() -> None:
    bind = op.get_bind()
    for ddl in TABLES:
        bind.execute(text(ddl))

    for code, name, slug, currency, region in seed.COUNTRIES:
        status, sort_order, summary, compliance = seed.ACTIVE.get(code, ("researching", 100, None, None))
        bind.execute(text(
            """INSERT INTO content_countries (code, name, slug, currency, region, status, coverage, summary,
                                              compliance_md, sort_order)
               VALUES (:code, :name, :slug, :currency, :region, :status, :coverage, :summary, :compliance, :sort)"""),
            {"code": code, "name": name, "slug": slug, "currency": currency, "region": region, "status": status,
             "coverage": "active" if code in seed.ACTIVE else "monitoring", "summary": summary,
             "compliance": compliance, "sort": sort_order})

    for i, (cc, name, abbr, scope, url) in enumerate(seed.REGULATORS):
        bind.execute(text(
            """INSERT INTO content_regulators (country_code, name, abbreviation, scope, website_url, sort_order)
               VALUES (:cc, :name, :abbr, :scope, :url, :sort)"""),
            {"cc": cc, "name": name, "abbr": abbr, "scope": scope, "url": url, "sort": i})

    for cc, name, status, summary, url, eff in seed.REGULATORY_ENTRIES:
        bind.execute(text(
            """INSERT INTO content_regulatory_entries (country_code, regulation_name, status, summary_md, source_url,
                                                       effective_date, last_verified_at)
               VALUES (:cc, :name, :status, :summary, :url, :eff, UTC_TIMESTAMP(6))"""),
            {"cc": cc, "name": name, "status": status, "summary": summary, "url": url, "eff": eff})

    for key, label, unit, cc, source, stale in seed.LIVE_FEEDS:
        bind.execute(text(
            """INSERT INTO market_live_feeds (`key`, label, unit, country_code, source_name, stale_after_minutes)
               VALUES (:key, :label, :unit, :cc, :source, :stale)"""),
            {"key": key, "label": label, "unit": unit, "cc": cc, "source": source, "stale": stale})

    for mk, cc, value, display, yoy, verified, note in VERIFIED_STATS:
        source, period = STAT_SOURCES.get(mk, ("Chainalysis Geography of Crypto 2025", "Jul 2024 - Jun 2025"))
        bind.execute(text(
            """INSERT INTO market_verified_annual_stats (metric_key, country_code, value, display_value,
                   yoy_change_pct, is_verified, pending_note, source_name, source_period)
               VALUES (:mk, :cc, :value, :display, :yoy, :verified, :note, :source, :period)"""),
            {"mk": mk, "cc": cc, "value": value, "display": display, "yoy": yoy, "verified": verified,
             "note": note, "source": source, "period": period})

    for metric_key, cc, label, badge, sample in seed.STAT_LABELS:
        bind.execute(text(
            """UPDATE market_verified_annual_stats SET label = :label, badge = :badge, sample_note = :sample
               WHERE metric_key = :mk AND country_code <=> :cc"""),
            {"label": label, "badge": badge, "sample": sample, "mk": metric_key, "cc": cc})

    for cc, pair, rate, source in OFFICIAL_RATES:
        bind.execute(text(
            """INSERT INTO market_official_rates (country_code, pair, rate, source_name, effective_date)
               VALUES (:cc, :pair, :rate, :source, UTC_DATE())"""),
            {"cc": cc, "pair": pair, "rate": rate, "source": source})

    def stat_id(mk, cc=None):
        return bind.execute(text(
            "SELECT id FROM market_verified_annual_stats WHERE metric_key = :mk AND country_code <=> :cc"),
            {"mk": mk, "cc": cc}).scalar()

    cards = [
        ("metrics", "live", "global_supply", None, None, False, 1),
        ("metrics", "report", None, stat_id("ssa_onchain_value"), None, False, 2),
        ("metrics", "report", None, stat_id("country_onchain_value", "NG"), "Nigeria on-chain value, #1 in Africa", False, 3),
        ("metrics", "report", None, stat_id("stablecoin_ownership_pct"), None, False, 4),
        ("countries", "report", None, stat_id("country_onchain_value", "NG"), None, True, 1),
        ("countries", "report", None, stat_id("country_onchain_value", "ZA"), None, False, 2),
        ("countries", "report", None, stat_id("country_onchain_value", "KE"), None, False, 3),
        ("countries", "report", None, stat_id("country_onchain_value", "GH"), None, False, 4),
    ]
    for zone, kind, feed, sid, label, hi, order in cards:
        bind.execute(text(
            """INSERT INTO site_snapshot_cards (zone, kind, live_feed_key, report_stat_id, label_override,
                                               is_highlighted, sort_order)
               VALUES (:zone, :kind, :feed, :sid, :label, :hi, :order)"""),
            {"zone": zone, "kind": kind, "feed": feed, "sid": sid, "label": label, "hi": hi, "order": order})

    for feed, label, order in seed.TICKER:
        bind.execute(text("INSERT INTO site_ticker_items (live_feed_key, label, sort_order) VALUES (:f, :l, :o)"),
                     {"f": feed, "l": label, "o": order})

    for key, value in seed.SITE_TEXT.items():
        bind.execute(text("INSERT INTO site_text (`key`, value_md) VALUES (:k, :v)"), {"k": key, "v": value})

    bind.execute(text("INSERT INTO content_homepage_slots (slot) VALUES "
                      "('lead'),('secondary_1'),('secondary_2'),('markets_lead'),('regulation_lead')"))
    bind.execute(text("INSERT INTO content_breaking_banner (id) VALUES (1)"))


def downgrade() -> None:
    raise NotImplementedError("Forward-only: dropping the schema would destroy editorial content.")
```

Check `seed_data.REGULATORY_ENTRIES` effective dates: they were passed through `CAST(:eff AS DATE)`. If any is a
string, convert it in the migration with `date.fromisoformat(eff) if eff else None` before binding.

- [ ] **Step 6: Test harness**

In `apps/api/tests/conftest.py`:
- Delete the Redis lines and the `_flush_cache_between_tests` fixture.
- Replace the engine and URL block with:

```python
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "mysql+pymysql://asi:asi_dev_password@localhost:3306/asi_test?charset=utf8mb4")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL       # the app's own engine points at the test database
os.environ["SITE_URL"] = "http://testserver"
os.environ["NEWSLETTER_BATCH_PAUSE"] = "0"
```

Place this block before any `app.` import. Then add:

```python
import pathlib

API_ROOT = pathlib.Path(__file__).resolve().parents[1]

from app.core.db import engine  # noqa: E402  (same engine and converters as the app)


@pytest.fixture(scope="session", autouse=True)
def _migrated():
    """Brings the test database to the latest schema once per run."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _clean_ops_tables():
    """Rows the app writes outside the test transaction (rate limits, job
    runs and lock state are committed by design) never leak between tests."""
    yield
    with engine.begin() as conn:
        for table in ("ops_rate_limits", "ops_job_runs", "ops_alert_state", "auth_revoked_tokens", "auth_totp_used"):
            conn.execute(text(f"DELETE FROM {table}"))
```

Keep `db_session` as is: it uses `engine.connect()`, which already runs READ COMMITTED.

In `make_user`, change `INSERT INTO auth.users` to `INSERT INTO auth_users` (`RETURNING id` stays).

- [ ] **Step 7: Run the tests to verify they pass**

Run: `docker compose run --rm api pytest tests/test_db_mariadb.py tests/test_schema_seed.py tests/test_dialect.py -q`
Expected: all PASS (dialect tests for ported files pass; the rest are skipped).

If `CHECK (CAST(code AS BINARY) REGEXP …)` is rejected by the server, use
`CHECK (code REGEXP BINARY '^[A-Z]{2}$')` instead and re-run.

- [ ] **Step 8: Commit**

```bash
git add -A docker-compose.yml docker apps/api db
git commit -m "feat: MariaDB 11.4 foundation — UTC driver boundary, baseline schema, test harness"
```

---

### Task 2: Replace Redis (rate limits, revocation, TOTP replay) and port auth SQL

**Files:**
- Modify: `apps/api/app/core/rate_limit.py`, `apps/api/app/core/security.py`, `apps/api/app/api/health.py`, `apps/api/app/core/audit.py`
- Modify: `apps/api/app/api/admin/auth.py`, `apps/api/app/api/admin/users.py`, `apps/api/app/api/admin/audit.py`, `apps/api/app/cli/bootstrap_admin.py`
- Modify: `apps/api/app/api/public/newsletter.py` (subscribe rate limit only)
- Delete: `apps/api/app/core/cache.py`
- Modify (callers of `cache.cached` / `invalidate_prefix`): `app/api/public/{countries,home,metrics,news}.py`, `app/api/admin/{countries,fx,homepage,metrics,regulatory,site_text,articles,media}.py`, `app/services/editorial.py`
- Test: `apps/api/tests/test_ops_tables.py`; existing `test_auth.py`, `test_auth_sessions.py`, `test_polish.py`

**Interfaces:**
- Consumes: `app.core.db.engine`, `db_session` fixture.
- Produces:
  - `app.core.rate_limit.hit(bucket: str, limit: int, window_seconds: int) -> bool`: True means over the limit; it
    commits on its own connection, so a rolled-back request still counts.
  - `app.core.rate_limit.enforce_login_rate_limit(request: Request) -> None`
  - `app.core.security.revoke_token(jti: str, exp: datetime) -> None`, `_is_revoked(jti: str) -> bool`
  - `verify_totp(user_id, encrypted_secret, code) -> bool`
  - `app.services.editorial.invalidate_public()` stays the public entry point for "public content changed". Task 8
    turns it into a page-cache purge; here it becomes a no-op.

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_ops_tables.py`:

```python
from datetime import datetime, timedelta, timezone

from app.core import rate_limit, security


def test_fixed_window_rate_limit_counts_and_blocks():
    results = [rate_limit.hit("probe:1.2.3.4", limit=3, window_seconds=60) for _ in range(4)]
    assert results == [False, False, False, True]


def test_rate_limit_buckets_are_independent():
    for _ in range(3):
        rate_limit.hit("probe:a", limit=3, window_seconds=60)
    assert rate_limit.hit("probe:b", limit=3, window_seconds=60) is False


def test_revoked_token_is_refused_until_it_expires():
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    assert security._is_revoked("jti-probe") is False
    security.revoke_token("jti-probe", exp)
    assert security._is_revoked("jti-probe") is True


def test_totp_code_cannot_be_replayed(make_user, db_session):
    import pyotp
    from sqlalchemy import text

    uid, _ = make_user("admin")
    secret = db_session.execute(text("SELECT totp_secret FROM auth_users WHERE id=:i"), {"i": uid}).scalar()
    code = pyotp.TOTP(security.decrypt_secret(secret)).now()
    assert security.verify_totp(uid, secret, code) is True
    assert security.verify_totp(uid, secret, code) is False


def test_health_reports_database_only(client):
    body = client.get("/healthz").json()
    assert body == {"status": "ok", "checks": {"database": True}}
```

In `tests/test_dialect.py`, remove these files from `NOT_YET_PORTED`:
- `api/admin/auth.py`, `api/admin/users.py`, `api/admin/audit.py`
- `api/health.py`
- `core/security.py`, `core/audit.py`
- `cli/bootstrap_admin.py`

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_ops_tables.py tests/test_auth.py tests/test_auth_sessions.py tests/test_dialect.py -q`
Expected: FAIL (`hit` missing, `redis` import errors, schema-qualified SQL).

- [ ] **Step 3: Implement**

`app/core/rate_limit.py` (replace whole file):

```python
"""Fixed-window rate limits stored in MariaDB (ops_rate_limits).

Each attempt is one upsert on its own short connection, committed at once,
so the count survives even when the request itself is rolled back (a failed
login must still count). Fails open: if the database is unreachable the
request is allowed (the login itself will fail anyway).

Login is limited per IP (8 per 15 minutes), deliberately not per email:
per-email limits let an attacker spread guesses across many IPs.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import text

from app.core.db import engine

LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_ATTEMPTS = 8


def _window_start(window_seconds: int) -> datetime:
    now = int(datetime.now(timezone.utc).timestamp())
    return datetime.fromtimestamp(now - now % window_seconds, timezone.utc)


def hit(bucket: str, limit: int, window_seconds: int) -> bool:
    """Counts one attempt; True when this attempt is over the limit."""
    start = _window_start(window_seconds)
    try:
        with engine.begin() as conn:
            conn.execute(text(
                """INSERT INTO ops_rate_limits (bucket, window_start, hits) VALUES (:b, :w, 1)
                   ON DUPLICATE KEY UPDATE hits = hits + 1"""), {"b": bucket[:200], "w": start})
            hits = conn.execute(text(
                "SELECT hits FROM ops_rate_limits WHERE bucket = :b AND window_start = :w"),
                {"b": bucket[:200], "w": start}).scalar()
        return hits > limit
    except Exception as exc:  # noqa: BLE001 — fail open
        print(f"[rate_limit] database unavailable, allowing request: {exc}")
        return False


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_login_rate_limit(request: Request) -> None:
    if hit(f"login:{client_ip(request)}", LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_SECONDS):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Too many login attempts. Try again in a few minutes.")
```

Behind nginx and Apache, `request.client.host` is the proxy address, not the reader's. uvicorn's proxy-headers
middleware isn't available on the host (uvicorn isn't installed there). So add a tiny middleware to
`app/core/middleware.py` that, in production, takes the client address from the first `X-Forwarded-For` entry:

```python
def install_forwarded_for(app: FastAPI) -> None:
    @app.middleware("http")
    async def forwarded_for(request: Request, call_next):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            request.scope["client"] = (forwarded.split(",")[0].strip(), 0)
        return await call_next(request)
```

Call `middleware.install_forwarded_for(app)` in `create_app()` only when `IS_PRODUCTION`. On the host, Apache sits
behind nginx, which sets `X-Forwarded-For`.

Every other `cache.rate_limited(key, max, window)` caller becomes `rate_limit.hit(key, max, window)`. These are the
password reset per address and per IP in `admin/auth.py`, and newsletter subscribe in `api/public/newsletter.py`.

`app/core/security.py`:
- Delete `from app.core.cache import get_client`.
- Add `from sqlalchemy import text` and `from app.core.db import engine`.
- Replace the three Redis uses:

```python
def verify_totp(user_id: int, encrypted_secret: str | None, code: str | None) -> bool:
    secret = decrypt_secret(encrypted_secret) if encrypted_secret else None
    if not secret or not code or not pyotp.TOTP(secret).verify(code.strip(), valid_window=1):
        return False
    # A code can be used once: the primary key makes the second insert a no-op.
    with engine.begin() as conn:
        inserted = conn.execute(text("INSERT IGNORE INTO auth_totp_used (user_id, code) VALUES (:u, :c)"),
                                {"u": user_id, "c": code.strip()}).rowcount
    return inserted == 1


def revoke_token(jti: str, exp: datetime) -> None:
    with engine.begin() as conn:
        conn.execute(text("INSERT IGNORE INTO auth_revoked_tokens (jti, expires_at) VALUES (:j, :e)"),
                     {"j": jti, "e": exp})


def _is_revoked(jti: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT 1 FROM auth_revoked_tokens WHERE jti = :j AND expires_at > UTC_TIMESTAMP(6)"),
            {"j": jti}).first() is not None
```

Keep the existing body of `verify_totp` up to the replay check (read it first). Only the replay mechanism
changes. Port the remaining SQL in `security.py` (`get_session_user` reads `auth_users`) with rules P1/P2.

`app/api/health.py`: drop the Redis check, so `checks = {"database": ...}`, status `"ok"` or `"down"` (503).

`app/core/audit.py`: `INSERT INTO audit_admin_log (user_id, action, entity, entity_id, detail) VALUES (…, :detail)`,
with `json.dumps(detail or {}, default=str)` (P14).

Port `api/admin/auth.py`, `api/admin/users.py`, `api/admin/audit.py` and `cli/bootstrap_admin.py` with P1–P20.
The non-mechanical cases:
- `users.py` `IS DISTINCT FROM` → P10.
- `UPDATE auth.users … RETURNING` → P8: run the `UPDATE`, then `SELECT … FROM auth_users WHERE id = :id`.
- `password_tokens` `RETURNING` on `UPDATE` → P8.
- `sessions_valid_after = clock_timestamp()` → `UTC_TIMESTAMP(6)`.

Delete `app/core/cache.py`:
- In public endpoints, remove the `@cached(...)` decorators and their imports. The page cache (Task 8) replaces them.
- In admin endpoints, replace `invalidate_prefix(...)` calls with `editorial.invalidate_public()`. Change that
  function in `services/editorial.py` to:

```python
def invalidate_public() -> None:
    """Public content changed. Task 8 makes this purge the page cache."""
```

- [ ] **Step 4: Run to verify they pass**

Run: `docker compose run --rm api pytest tests/test_ops_tables.py tests/test_auth.py tests/test_auth_sessions.py tests/test_polish.py tests/test_dialect.py -q`
Expected: PASS. Tests in `test_polish.py` that need articles or newsletter may still fail; they belong to Tasks 3
and 5. Note any such failures in the commit message as "pending Task 3/5".

- [ ] **Step 5: Commit**

```bash
git add -A apps/api
git commit -m "feat: rate limits, token revocation and TOTP replay in MariaDB; Redis removed"
```

---

### Task 3: Articles, editorial workflow, search, authors, SEO routes

**Files:**
- Create: `apps/api/app/services/search.py`
- Modify: `apps/api/app/services/{articles,editorial,authors,images}.py`, `apps/api/app/api/admin/articles.py`, `apps/api/app/api/public/news.py`, `apps/api/app/seo/routes.py`, `apps/api/app/site/routes.py` (article, section, author and search parts), `apps/api/app/cli/seed_demo.py`
- Modify: `apps/api/tests/conftest.py` (add `committed` fixture)
- Test: `apps/api/tests/test_search.py`; existing `test_admin_articles.py`, `test_articles_publish_rules.py`, `test_public_news.py`, `test_site_articles.py`, `test_seo.py`, `test_markdown.py`, `test_text.py`, and the editorial parts of `test_polish.py` / `test_polish_ops.py`

**Interfaces:**
- Consumes: `db_json`, `bindparam` expanding (P9).
- Produces:
  - `app.services.search.fold(text: str) -> str`
  - `boolean_query(q: str) -> str | None`
  - `like_terms(q: str) -> list[str]`
  - `editorial.write_derived(db, article_id: int) -> None`: sets `search_title`, `search_body`, `word_count`.
  - `editorial.set_countries(db, article_id: int, codes: list[str]) -> None`
  - `editorial.COUNTRY_CODES_SQL: str`: a SQL expression yielding a JSON array of the article's codes (alias `a`).
  - `articles.PUBLIC_PREDICATE` (MariaDB form)
  - `editorial.promote_due(db) -> list[str]` (P8 form)
  - fixture `committed(title, body_md="…", tag="Markets", countries=())` → slug

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_search.py`:

```python
from app.services import search


def test_fold_removes_accents_and_case():
    assert search.fold("Côte d’Ivoire RÉGULATION") == "cote d’ivoire regulation"


def test_boolean_query_requires_every_word_and_strips_operators():
    assert search.boolean_query('naira +"stable" -coin*') == "+naira* +stable* +coin*"


def test_short_words_and_stopwords_are_dropped():
    assert search.boolean_query("the SEC on it") == "+sec*"
    assert search.boolean_query("a of") is None
    assert search.like_terms("ai fx") == ["ai", "fx"]


def test_accent_insensitive_search_finds_a_committed_story(client, committed):
    committed(title="Côte d'Ivoire licenses its first stablecoin desk")
    html = client.get("/search?q=cote+divoire").text
    assert "licenses its first stablecoin desk" in html


def test_two_letter_query_still_finds_matches(client, committed):
    committed(title="FX desks in Lagos widen the spread")
    assert "FX desks in Lagos" in client.get("/search?q=fx").text


def test_search_api_ranks_title_matches_first(client, committed):
    committed(title="Stablecoin remittances overview", body_md="General market notes.")
    committed(title="Market notes", body_md="A long piece that mentions remittances once.")
    items = client.get("/api/v1/news?q=remittances").json()["items"]
    assert items[0]["title"] == "Stablecoin remittances overview"


def test_scheduled_in_lagos_time_goes_live_on_time(client, make_user, draft_with_source, db_session):
    from sqlalchemy import text

    from tests.helpers import FULL_CHECKLIST

    art_id, _ = draft_with_source(title="Lagos morning release")
    _, ed = make_user("editor")
    r = client.post(f"/admin/articles/{art_id}/review",
                    json={"decision": "approved", "checklist": FULL_CHECKLIST,
                          "publish_at": "2099-03-01T09:00:00+01:00"}, headers=ed)
    assert r.status_code == 200, r.json()
    stored = db_session.execute(text("SELECT CAST(published_at AS CHAR) FROM content_articles WHERE id=:i"),
                                {"i": art_id}).scalar()
    assert stored.startswith("2099-03-01 08:00:00")
```

Add the `committed` fixture to `conftest.py`:

```python
@pytest.fixture()
def committed():
    """Creates live articles with a real COMMIT (FULLTEXT only indexes committed
    rows) and deletes them afterwards. Returns a factory -> slug."""
    import uuid

    from app.core.text import slugify
    from app.services import editorial

    created_articles, created_users = [], []

    def _make(title, body_md="Body text.", tag="Markets", countries=()):
        slug = f"{slugify(title)}-{uuid.uuid4().hex[:4]}"
        with engine.begin() as conn:
            uid = conn.execute(text(
                "INSERT INTO auth_users (name, email, password_hash, role, slug) "
                "VALUES ('Committed', :e, 'x', 'author', :s) RETURNING id"),
                {"e": f"c-{uuid.uuid4().hex[:8]}@test.local", "s": f"c-{uuid.uuid4().hex[:8]}"}).scalar()
            aid = conn.execute(text(
                "INSERT INTO content_articles (slug, title, body_md, tag, status, author_id, published_at) "
                "VALUES (:slug, :title, :body, :tag, 'published', :uid, UTC_TIMESTAMP(6) - INTERVAL 1 MINUTE) "
                "RETURNING id"), {"slug": slug, "title": title, "body": body_md, "tag": tag, "uid": uid}).scalar()
            editorial.set_countries(conn, aid, list(countries))
            editorial.write_derived(conn, aid)
        created_articles.append(aid)
        created_users.append(uid)
        return slug

    yield _make
    with engine.begin() as conn:
        for aid in created_articles:
            conn.execute(text("DELETE FROM content_articles WHERE id = :i"), {"i": aid})
        for uid in created_users:
            conn.execute(text("DELETE FROM auth_users WHERE id = :i"), {"i": uid})
```

(`set_countries` and `write_derived` accept either a `Session` or a `Connection`; both have `.execute`.)

Remove from `NOT_YET_PORTED`:
- `api/admin/articles.py`, `api/public/news.py`
- `seo/routes.py`
- `services/articles.py`, `services/editorial.py`, `services/authors.py`, `services/images.py`
- `cli/seed_demo.py`

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_search.py tests/test_admin_articles.py tests/test_articles_publish_rules.py tests/test_public_news.py tests/test_site_articles.py tests/test_seo.py tests/test_dialect.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement search helpers**

`app/services/search.py`:

```python
"""Reader search on MariaDB FULLTEXT.

Titles and bodies are stored folded (accents removed, lower case, Markdown
stripped) in content_articles.search_title / search_body, and queries are
folded the same way, so "cote" finds "Côte d'Ivoire" whatever the collation.
InnoDB ignores words under 3 characters and a list of stopwords, so those
are dropped from the boolean query; a query made only of short words falls
back to LIKE.
"""

from __future__ import annotations

import re
import unicodedata

MIN_WORD = 3
# InnoDB's default stopword list (information_schema.INNODB_FT_DEFAULT_STOPWORD).
STOPWORDS = frozenset(
    "a about an are as at be by com de en for from how i in is it la of on or that the this to was what when "
    "where who will with und www".split()
)
_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def fold(value: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _words(q: str) -> list[str]:
    return _WORD.findall(fold(q))[:12]


def boolean_query(q: str) -> str | None:
    terms = [w for w in _words(q) if len(w) >= MIN_WORD and w not in STOPWORDS]
    return " ".join(f"+{w}*" for w in terms) or None


def like_terms(q: str) -> list[str]:
    return [w for w in _words(q) if w not in STOPWORDS] or _words(q)
```

- [ ] **Step 4: Port articles, editorial, authors, images, admin articles, news, SEO, site routes**

Apply P1–P20 to every SQL string in these files. The non-mechanical parts:

`services/articles.py`:

```python
PUBLIC_PREDICATE = "a.status IN ('published', 'scheduled') AND a.published_at <= UTC_TIMESTAMP(6)"

_CARD_COLUMNS = """
    a.id, a.slug, a.title, a.dek, a.tag, a.is_featured, a.published_at, a.updated_at,
    a.seo_description, a.correction_at, a.word_count,
    u.name AS author_name, u.slug AS author_slug, u.title AS author_title,
    (SELECT JSON_ARRAYAGG(JSON_OBJECT('code', c.code, 'name', c.name, 'slug', c.slug) ORDER BY c.name)
       FROM content_article_countries ac JOIN content_countries c ON c.code = ac.country_code
      WHERE ac.article_id = a.id) AS country_list,
    CASE WHEN m.id IS NULL THEN NULL ELSE JSON_OBJECT(
        'id', m.id, 'object_key', m.object_key, 'original_filename', m.original_filename,
        'width', m.width, 'height', m.height, 'alt_text', m.alt_text, 'caption', m.caption,
        'credit', m.credit, 'licence', m.licence, 'licence_note', m.licence_note,
        'focal_x', m.focal_x, 'focal_y', m.focal_y, 'variants', m.variants,
        'uploaded_at', m.uploaded_at) END AS cover_row
"""
_CARD_FROM = """
    FROM content_articles a
    JOIN auth_users u ON u.id = a.author_id
    LEFT JOIN content_media m ON m.id = a.cover_media_id
"""
```

In `_card(row)`:
- `"countries": db_json(row["country_list"], [])`
- `"cover": images.image_dict(db_json(row["cover_row"]))`
- `reading_minutes` uses `row["word_count"]`

In `list_public`:

```python
    if country:
        clauses.append("EXISTS (SELECT 1 FROM content_article_countries ac "
                       "WHERE ac.article_id = a.id AND ac.country_code = :country)")
        params["country"] = country.upper()
    if exclude_ids:
        clauses.append("a.id NOT IN :exclude")
        params["exclude"] = list(exclude_ids)
    ...
    rank = ""
    if q and q.strip():
        boolean = search.boolean_query(q[:200])
        if boolean:
            clauses.append("MATCH(a.search_title, a.search_body) AGAINST (:q IN BOOLEAN MODE)")
            params["q"] = boolean
            rank = ("(MATCH(a.search_title) AGAINST (:q IN BOOLEAN MODE) * 3 + "
                    "MATCH(a.search_title, a.search_body) AGAINST (:q IN BOOLEAN MODE)) DESC, ")
        else:
            for i, term in enumerate(search.like_terms(q[:200])):
                clauses.append(f"(a.search_title LIKE :like{i} OR a.search_body LIKE :like{i})")
                params[f"like{i}"] = f"%{term}%"
    order_sql = (f"(a.is_featured AND a.published_at > UTC_TIMESTAMP(6) - INTERVAL {FEATURED_WINDOW_DAYS} DAY) DESC, "
                 "a.published_at DESC") if order == "featured" else "a.published_at DESC"
```

Build the statement with `stmt = text(...)`. When `exclude_ids` is set, call
`stmt = stmt.bindparams(bindparam("exclude", expanding=True))`. Apply this to both the COUNT and the page query.

- `cards_by_ids`: `a.id IN :ids` with an expanding bindparam.
- `get_public`: replace `a.countries AS country_codes` with `{editorial.COUNTRY_CODES_SQL} AS country_codes`, then
  `country_codes=db_json(row["country_codes"], [])`. Import `COUNTRY_CODES_SQL` from `editorial`, or move the
  constant to `articles` and import it in `editorial`, to avoid an import cycle. Place it in `articles.py`.
- `related`:

```python
ORDER BY (a.tag = :section) DESC,
         EXISTS (SELECT 1 FROM content_article_countries ac
                  WHERE ac.article_id = a.id AND ac.country_code IN :countries) DESC,
         a.published_at DESC
```

with `bindparam("countries", expanding=True)`. When the article has no countries, pass `["--"]` (a code that
can't exist) so the expanding list is never empty.

- `most_read`: `WHERE day > UTC_DATE() - INTERVAL :days DAY`.

`services/images.py`: in `image_dict(row)`, parse `variants` with `db_json(row.get("variants"), {})` before use.
`lookup(db, ids)`: `WHERE id IN :ids` (expanding).

`services/editorial.py`:

```python
COUNTRY_CODES_SQL = ("(SELECT JSON_ARRAYAGG(ac.country_code ORDER BY ac.country_code) "
                     "FROM content_article_countries ac WHERE ac.article_id = a.id)")


def set_countries(db, article_id: int, codes: list[str]) -> None:
    db.execute(text("DELETE FROM content_article_countries WHERE article_id = :a"), {"a": article_id})
    for code in dict.fromkeys(c.upper() for c in codes):
        db.execute(text("INSERT INTO content_article_countries (article_id, country_code) VALUES (:a, :c)"),
                   {"a": article_id, "c": code})


def write_derived(db, article_id: int) -> None:
    """Search columns and word count, computed in Python so they are identical
    on every database and always match the folding used for queries."""
    row = db.execute(text("SELECT title, dek, body_md FROM content_articles WHERE id = :i"),
                     {"i": article_id}).mappings().first()
    plain = markdown.plain_text(row["body_md"], 1_000_000)
    db.execute(text("UPDATE content_articles SET search_title = :t, search_body = :b, word_count = :w WHERE id = :i"),
               {"t": search.fold(row["title"])[:300],
                "b": search.fold(" ".join(filter(None, [row["dek"], plain]))),
                "w": len(plain.split()), "i": article_id})
```

Wire the two helpers in:
- Call `set_countries` wherever `countries` used to be written to the array column: create article, `_apply_update`,
  revision restore, and `seed_demo`.
- Call `write_derived` after every write of title, dek or body: create, update, restore, correction.
- `get_or_404` (and any `SELECT a.* FROM content.articles a`) adds `, {COUNTRY_CODES_SQL} AS countries` and maps
  `article["countries"] = db_json(article["countries"], [])`.
- Revisions store `json.dumps(codes)` in `countries` and read it back with `db_json`.

Other `editorial.py` conversions:
- `validate_countries`: `WHERE code IN :c` (expanding).
- Slug-taken check: P10, e.g. `AND NOT (id <=> :id)`.
- Media link insert: `INSERT IGNORE INTO content_article_media_links … SELECT :a, id, :r FROM content_media WHERE id = :m`.
- Redirect upsert: `INSERT INTO content_slug_redirects (old_slug, article_id) VALUES (:old, :id) ON DUPLICATE KEY UPDATE article_id = VALUES(article_id)`.
- `approve` (P8):

```python
    db.execute(text(f"""UPDATE content_articles SET status = :status, reviewed_by = :reviewer,
                        published_at = {stamp_sql}, updated_at = UTC_TIMESTAMP(6) WHERE id = :id"""),
               {"status": status, "reviewer": user["id"], "id": article["id"], **params})
    published_at = db.execute(text("SELECT published_at FROM content_articles WHERE id = :id"),
                              {"id": article["id"]}).scalar()
```

  Where `stamp_sql` was `now()`, it becomes `UTC_TIMESTAMP(6)`. A scheduled time is bound as an aware datetime;
  the driver converts it to UTC.
- `promote_due` (P8):

```python
def promote_due(db: Session) -> list[str]:
    rows = db.execute(text(
        """SELECT id, slug, tag FROM content_articles
           WHERE status = 'scheduled' AND published_at <= UTC_TIMESTAMP(6) FOR UPDATE SKIP LOCKED""")).all()
    if not rows:
        db.commit()
        return []
    db.execute(text("UPDATE content_articles SET status = 'published', updated_at = UTC_TIMESTAMP(6) "
                    "WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": [r.id for r in rows]})
    db.commit()
    invalidate_public()
    paths = [articles.article_url(r.tag, r.slug) for r in rows]
    seo.indexnow_ping(paths)
    return paths
```

- `_record_review`: `checklist` bound as `json.dumps(...)` (P14).

`api/admin/articles.py`:
- `ILIKE` → `LIKE`.
- The country filter uses the same `EXISTS` clause as above.
- `to_jsonb(...)` → `JSON_OBJECT(...)` listing the needed columns, parsed with `db_json`.
- Every `UPDATE … RETURNING` → P8.
- `clock_timestamp()`/`now()` → `UTC_TIMESTAMP(6)`.
- The optimistic-lock comparison `body.expected_updated_at != article["updated_at"]` keeps working: both are aware
  UTC datetimes with microseconds.
- `GREATEST` and the window in `seo/routes.py`: `UTC_TIMESTAMP(6) - INTERVAL {NEWS_WINDOW_HOURS} HOUR`, and
  `to_jsonb` → `JSON_OBJECT`.

`services/authors.py` and the author, section, search and article routes in `site/routes.py`: P1/P2 only.

- [ ] **Step 5: Run to verify they pass**

Run: `docker compose run --rm api pytest tests/test_search.py tests/test_admin_articles.py tests/test_articles_publish_rules.py tests/test_public_news.py tests/test_site_articles.py tests/test_seo.py tests/test_markdown.py tests/test_text.py tests/test_dialect.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A apps/api
git commit -m "feat: articles, editorial workflow and accent-insensitive FULLTEXT search on MariaDB"
```

---

### Task 4: Homepage, snapshot, live figures, metrics, FX, flags, countries, regulatory, site text, dashboard

**Files:**
- Modify: `apps/api/app/services/{homepage,snapshot,live,countries,site_text}.py`
- Modify: `apps/api/app/api/admin/{homepage,snapshot,metrics,fx,flags,countries,regulatory,site_text,dashboard}.py`
- Modify: `apps/api/app/api/public/{home,metrics,countries}.py`
- Modify: `apps/api/app/site/routes.py` (remaining parts)
- Test: existing `test_homepage.py`, `test_admin_homepage_snapshot.py`, `test_live_snapshot.py`, `test_public_metrics_honesty.py`, `test_public_countries.py`, `test_public_api.py`, `test_site_home.py`, `test_site_pages.py`, `test_site_base.py`, `test_core.py`

**Interfaces:**
- Produces:
  - `app.services.live.payload(db) -> dict`: the exact JSON body of `GET /api/v1/live` (refactor the endpoint to
    return `live.payload(db)`). Task 9 writes it to `live.json`.

- [ ] **Step 1: Make the target tests runnable**

Remove these files from `NOT_YET_PORTED`:
- `api/admin/homepage.py`, `api/admin/snapshot.py`, `api/admin/metrics.py`, `api/admin/fx.py`, `api/admin/flags.py`, `api/admin/countries.py`, `api/admin/regulatory.py`, `api/admin/site_text.py`, `api/admin/dashboard.py`
- `api/public/home.py`, `api/public/metrics.py`, `api/public/countries.py`
- `services/homepage.py`, `services/snapshot.py`, `services/live.py`, `services/countries.py`, `services/site_text.py`
- `site/routes.py`

Add to `tests/test_live_snapshot.py`:

```python
def test_live_payload_matches_the_endpoint(client, db_session):
    from fastapi.encoders import jsonable_encoder

    from app.services import live

    assert client.get("/api/v1/live").json() == jsonable_encoder(live.payload(db_session))
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_homepage.py tests/test_admin_homepage_snapshot.py tests/test_live_snapshot.py tests/test_public_metrics_honesty.py tests/test_public_countries.py tests/test_public_api.py tests/test_site_home.py tests/test_site_pages.py tests/test_site_base.py tests/test_core.py tests/test_dialect.py -q`
Expected: FAIL.

- [ ] **Step 3: Port**

Apply P1–P20. The non-mechanical parts:

`services/live.py`, `_premium_points` (P12):

```python
    latest = db.execute(text(
        """SELECT country_code, premium_pct, fetched_at FROM (
               SELECT country_code, premium_pct, fetched_at,
                      ROW_NUMBER() OVER (PARTITION BY country_code ORDER BY ts DESC) AS rn
                 FROM market_country_proxy_metrics WHERE premium_pct IS NOT NULL) x
           WHERE rn = 1""")).mappings().all()
    previous = db.execute(text(
        """SELECT country_code, premium_pct FROM (
               SELECT country_code, premium_pct,
                      ROW_NUMBER() OVER (PARTITION BY country_code ORDER BY ts DESC) AS rn
                 FROM market_country_proxy_metrics WHERE premium_pct IS NOT NULL AND ts <= :since) x
           WHERE rn = 1"""), {"since": since}).mappings().all()
```

`SELECT * FROM market_data.live_feeds ORDER BY key` becomes ``SELECT * FROM market_live_feeds ORDER BY `key` ``. Do
the same anywhere `key` is a column (P20), including `site_text` reads and writes in `services/site_text.py` and
`api/admin/site_text.py`.

Other conversions:
- `services/countries.py` and `admin/regulatory.py` `NULLS LAST` → P11. `admin/metrics.py` `NULLS FIRST` → P11.
- `admin/fx.py` and `admin/homepage.py` `ON CONFLICT … DO UPDATE` → P5.
- `admin/countries.py`, `admin/regulatory.py`, `admin/snapshot.py` and `admin/metrics.py` `UPDATE … RETURNING` → P8.
  `INSERT … RETURNING` stays.
- `admin/flags.py`: `CAST(:note AS jsonb)` / `::jsonb` → P14. For resolving with a note merged into `detail`, use
  `detail = JSON_MERGE_PATCH(COALESCE(detail, '{}'), :note_json)`. Read `detail` with `db_json`.
- `admin/dashboard.py`: `now() - interval '7 days'` → `UTC_TIMESTAMP(6) - INTERVAL 7 DAY`.
- `services/homepage.py`: `= ANY(` → expanding `IN`.
- `market_verified_annual_stats` writes must never list `country_key` (it is generated).
- `snapshot_cards` and similar booleans come back as `bool` (driver), so templates and JSON are unchanged.

Refactor `api/public/metrics.py` `/live` (or wherever `/api/v1/live` is defined): move its body into
`services/live.py` as `payload(db) -> dict`, and have the endpoint `return live.payload(db)`.

- [ ] **Step 4: Run to verify they pass**

Same command as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api
git commit -m "feat: homepage, snapshot, live figures, metrics, countries and regulatory on MariaDB"
```

---

### Task 5: Media and newsletter (queued sending with an hourly cap)

**Files:**
- Modify: `apps/api/app/services/media.py`, `apps/api/app/api/admin/media.py`, `apps/api/app/cli/regenerate_media.py`
- Modify: `apps/api/app/services/newsletter.py`, `apps/api/app/api/admin/newsletter.py`, `apps/api/app/api/public/newsletter.py`
- Modify: `apps/api/app/core/settings.py` (`MAIL_MAX_PER_HOUR`, `SMTP_SSL`), `apps/api/app/core/email.py`
- Test: existing `test_media.py`, `test_newsletter.py`, `test_admin_countries_newsletter.py`, `test_polish_ops.py`; new tests below

**Interfaces:**
- Produces:
  - `newsletter.send_issue(db, issue_id, batch_size=50, sleep_s=1.0, max_messages=None, deadline=None) -> int`
  - `newsletter.send_pending(db, max_per_hour: int, deadline: float | None = None, sleep_s=1.0) -> int`, which
    returns the number of emails sent this call
  - `newsletter.sent_last_hour(db) -> int`
  - `newsletter.send_lock_name(issue_id) -> str`
  - admin `POST /admin/newsletter/issues/{id}/send` → `{"status": "queued"}` (status `sending`)
  - `resume` → same
  - settings `MAIL_MAX_PER_HOUR: int` (default 100), `SMTP_SSL: bool`
  - `media.MAX_PIXELS = 24_000_000`

- [ ] **Step 1: Write the failing tests**

Replace the three newsletter tests at the top of `tests/test_polish_ops.py`:
- `test_one_odd_address_does_not_stop_the_send`: keep it, using `nl.send_issue`.
- `test_two_workers_never_send_the_same_issue_at_once`: rewrite to use `named_lock`.
- `test_interrupted_sends_resume_by_themselves`: rewrite to use `send_pending`.

```python
def test_two_workers_never_send_the_same_issue_at_once(db_session, outbox):
    from app.core.db import engine, named_lock, release_lock

    _subscribers(db_session, "solo@example.com")
    issue_id = _issue(db_session, 51)
    with engine.connect() as other:
        assert named_lock(other, nl.send_lock_name(issue_id))
        assert nl.send_issue(db_session, issue_id, sleep_s=0) == 0
        assert outbox.messages == []
        release_lock(other, nl.send_lock_name(issue_id))
    assert nl.send_issue(db_session, issue_id, sleep_s=0) == 1


def test_interrupted_sends_resume_on_the_next_job_run(db_session, outbox):
    from sqlalchemy import text

    _subscribers(db_session, "r1@example.com", "r2@example.com")
    issue_id = _issue(db_session, 52)
    db_session.execute(text("UPDATE newsletter_issues SET status='sending' WHERE id=:i"), {"i": issue_id})
    db_session.commit()
    outbox.fail_after(1)
    with pytest.raises(ConnectionError):
        nl.send_pending(db_session, max_per_hour=100, sleep_s=0)
    outbox.fail_after(None)
    assert nl.send_pending(db_session, max_per_hour=100, sleep_s=0) == 1
    assert sorted(m.to for m in outbox.messages) == ["r1@example.com", "r2@example.com"]


def test_hourly_cap_spreads_a_send_over_several_runs(db_session, outbox):
    from sqlalchemy import text

    _subscribers(db_session, *[f"cap{i}@example.com" for i in range(5)])
    issue_id = _issue(db_session, 53)
    db_session.execute(text("UPDATE newsletter_issues SET status='sending' WHERE id=:i"), {"i": issue_id})
    db_session.commit()
    assert nl.send_pending(db_session, max_per_hour=3, sleep_s=0) == 3
    assert nl.send_pending(db_session, max_per_hour=3, sleep_s=0) == 0      # cap reached for this hour
    db_session.execute(text("UPDATE newsletter_deliveries SET sent_at = sent_at - INTERVAL 2 HOUR"))
    db_session.commit()
    assert nl.send_pending(db_session, max_per_hour=3, sleep_s=0) == 2
    status = db_session.execute(text("SELECT status FROM newsletter_issues WHERE id=:i"), {"i": issue_id}).scalar()
    assert status == "sent"


def test_send_button_queues_instead_of_sending(client, make_user, db_session, outbox):
    _subscribers(db_session, "q@example.com")
    issue_id = _issue(db_session, 54)
    _, admin = make_user("admin")
    r = client.post(f"/admin/newsletter/issues/{issue_id}/send", headers=admin, json={"confirm_count": 1})
    assert r.status_code == 200 and r.json()["status"] == "queued"
    assert outbox.messages == []
```

Read the existing send endpoint first. If it takes the typed subscriber-count confirmation under another field
name, use that name in the test.

In `tests/test_newsletter.py`, wherever a test POSTs `/send` and then asserts on `outbox`, add
`nl.send_pending(db_session, max_per_hour=10_000, sleep_s=0)` between the two (import
`from app.services import newsletter as nl`).

Add to `tests/test_media.py`:

```python
def test_over_24_megapixels_is_refused():
    import io

    import pytest
    from PIL import Image

    from app.services import media

    buf = io.BytesIO()
    Image.new("RGB", (6000, 4100)).save(buf, "JPEG", quality=20)
    with pytest.raises(media.MediaError):
        media.process(buf.getvalue())
```

Remove `api/admin/media.py`, `api/admin/newsletter.py`, `api/public/newsletter.py`, `services/media.py`,
`services/newsletter.py` and `cli/regenerate_media.py` from `NOT_YET_PORTED`.

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_media.py tests/test_newsletter.py tests/test_admin_countries_newsletter.py tests/test_polish_ops.py tests/test_dialect.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

Settings:

```python
MAIL_MAX_PER_HOUR = int(os.environ.get("MAIL_MAX_PER_HOUR", "100"))
SMTP_SSL = os.environ.get("SMTP_SSL", "false").lower() == "true"   # port 465 on the host's mail server
```

`app/core/email.py`: `smtp_class = smtplib.SMTP_SSL if SMTP_SSL else smtplib.SMTP`. Open with
`smtp_class(SMTP_HOST, SMTP_PORT, timeout=15)`, and skip `starttls()` when `SMTP_SSL`.

`services/media.py`:
- `MAX_PIXELS = 24_000_000` and the message "over 24 megapixels".
- In `_open`, before `im.load()` for JPEGs, call `im.draft("RGB", (3200, 3200))` so huge photos decode at reduced
  size.
- `variants` writes `json.dumps(keys)` without the cast (P14). Reads use `db_json`.
- `usage()`: `~ :pattern` → `REGEXP :pattern`. `NULL::int` → `CAST(NULL AS UNSIGNED)`. Table names per mapping.
  `site_text` uses `` t.`key` ``.

`api/admin/media.py`: `ILIKE` → `LIKE`. `UPDATE content.media … RETURNING` → P8.

`services/newsletter.py`:

```python
def send_lock_name(issue_id: int) -> str:
    return f"newsletter:{int(issue_id)}"


def sent_last_hour(db: Session) -> int:
    return db.execute(text(
        "SELECT COUNT(*) FROM newsletter_deliveries WHERE status = 'sent' "
        "AND sent_at > UTC_TIMESTAMP(6) - INTERVAL 1 HOUR")).scalar() or 0


def send_pending(db: Session, max_per_hour: int, deadline: float | None = None, sleep_s: float = 1.0) -> int:
    """Called by the `newsletter` cron job: sends queued issues within the
    hourly cap and the job's time budget. Resumes without duplicates."""
    sent = 0
    ids = [r[0] for r in db.execute(text("SELECT id FROM newsletter_issues WHERE status = 'sending' ORDER BY id"))]
    for issue_id in ids:
        allowance = max_per_hour - sent_last_hour(db)
        if allowance <= 0 or (deadline is not None and time.monotonic() >= deadline):
            break
        sent += send_issue(db, issue_id, sleep_s=sleep_s, max_messages=allowance, deadline=deadline)
    return sent
```

In `send_issue`:
- Replace the advisory-lock block with `named_lock` / `release_lock` on the dedicated connection, keeping the
  existing structure (`own = isinstance(bind, Engine)`, dedicated connection, commit when own).
- Pass `max_messages` and `deadline` into `_send_locked`.
- In `_send_locked`'s loop, stop before sending when `sent_this_call >= max_messages`, or when
  `deadline is not None and time.monotonic() >= deadline`.
- Mark the issue `sent` only when no `queued` deliveries remain.
- Delete `resume_interrupted`.

The other SQL in `newsletter.py`:
- `ON CONFLICT` → P5/P6.
- `::text` → drop.
- `UPDATE … RETURNING` → P8 (subscriber confirm and unsubscribe).
- `pg_*` → `named_lock`.
- `now()` → `UTC_TIMESTAMP(6)`.

`api/admin/newsletter.py`:
- Delete `_send_in_background` and the `BackgroundTasks` use.
- `send` checks the typed count as before, creates the delivery rows for every confirmed subscriber the way
  `_send_locked` does, sets `status='sending'`, `updated_at=UTC_TIMESTAMP(6)`, commits, and returns
  `{"status": "queued"}`.
- If `_send_locked` creates the deliveries itself on first run, keep that, and have `send` only set the status.
- `resume` does the same (it re-queues a stopped send).
- `now() - interval '30 days'` → `UTC_TIMESTAMP(6) - INTERVAL 30 DAY`.

In `apps/admin/src/pages/Newsletter.jsx`:
- Change the success message `"Sending started — you can leave this page"` to
  `"Queued — sending starts within 5 minutes; you can leave this page"`.
- In the in-progress notice, change "If it has stopped … resume it" to "It picks up again by itself every 5 minutes;
  Resume re-queues it now."

- [ ] **Step 4: Run to verify they pass**

Same command as Step 2, then `cd apps/admin && npx vitest run`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api apps/admin
git commit -m "feat: media and newsletter on MariaDB; sends are queued and capped per hour"
```

---

### Task 6: View counting by beacon; whole suite green on MariaDB

**Files:**
- Create: `apps/api/app/api/public/views.py`
- Modify: `apps/api/app/services/views.py`, `apps/api/app/site/routes.py` (remove `record_view` call), `apps/api/app/main.py` (router, lifespan removal), `apps/api/app/site/static/js/site.js`, `apps/api/app/site/templates/article.html` (data attribute)
- Delete from `NOT_YET_PORTED`: everything left (the set becomes empty)
- Test: `apps/api/tests/test_views.py` (rewrite)

**Interfaces:**
- Produces:
  - `POST /api/v1/views` with body `{"slug": str}` → 204. Bots are ignored. It increments
    `content_article_daily_views` (today, UTC) and `content_articles.view_count` for a live article.
  - `views.record(db, slug: str, user_agent: str | None) -> bool`

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_views.py`:

```python
from sqlalchemy import text


def test_beacon_counts_a_view(client, publish, db_session):
    slug = publish("Counted story")
    r = client.post("/api/v1/views", json={"slug": slug}, headers={"User-Agent": "Mozilla/5.0"})
    assert r.status_code == 204
    views = db_session.execute(text(
        "SELECT v.views FROM content_article_daily_views v JOIN content_articles a ON a.id = v.article_id "
        "WHERE a.slug = :s AND v.day = UTC_DATE()"), {"s": slug}).scalar()
    assert views == 1


def test_bots_and_unknown_slugs_are_ignored(client, publish, db_session):
    slug = publish("Bot-visited story")
    client.post("/api/v1/views", json={"slug": slug}, headers={"User-Agent": "Googlebot/2.1"})
    client.post("/api/v1/views", json={"slug": "no-such-story"}, headers={"User-Agent": "Mozilla/5.0"})
    total = db_session.execute(text("SELECT COALESCE(SUM(views), 0) FROM content_article_daily_views")).scalar()
    assert total == 0


def test_article_page_carries_the_beacon_slug(client, publish):
    slug = publish("Beacon story")
    assert f'data-view-slug="{slug}"' in client.get(f"/markets/{slug}").text


def test_every_module_is_ported():
    from tests.test_dialect import NOT_YET_PORTED

    assert NOT_YET_PORTED == set()
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_views.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

`app/services/views.py` (replace):

```python
"""Anonymous article view counts — no cookies, no personal data.

Article pages are served from the page cache, so the server never sees most
page views. The page sends a small beacon instead (once per article per
browser per day); each beacon is one upsert.
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.articles import PUBLIC_PREDICATE

_BOT_RE = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|curl|wget|python-requests|headless",
                     re.IGNORECASE)


def record(db: Session, slug: str, user_agent: str | None) -> bool:
    if not user_agent or _BOT_RE.search(user_agent):
        return False
    article_id = db.execute(text(f"SELECT a.id FROM content_articles a WHERE a.slug = :s AND {PUBLIC_PREDICATE}"),
                            {"s": slug}).scalar()
    if article_id is None:
        return False
    db.execute(text("""INSERT INTO content_article_daily_views (article_id, day, views) VALUES (:a, UTC_DATE(), 1)
                       ON DUPLICATE KEY UPDATE views = views + 1"""), {"a": article_id})
    db.execute(text("UPDATE content_articles SET view_count = view_count + 1 WHERE id = :a"), {"a": article_id})
    db.commit()
    return True
```

`app/api/public/views.py`:

```python
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.rate_limit import client_ip, hit
from app.services import views

router = APIRouter(prefix="/api/v1", tags=["public"])


class ViewIn(BaseModel):
    slug: str = Field(min_length=1, max_length=200)


@router.post("/views", status_code=204)
def record_view(body: ViewIn, request: Request, db: Session = Depends(get_db)) -> Response:
    if not hit(f"views:{client_ip(request)}", 120, 3600):   # 120 beacons an hour per address
        views.record(db, body.slug, request.headers.get("user-agent"))
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
```

`navigator.sendBeacon` sends `text/plain`. Accept that by parsing the raw body when the content type isn't JSON:
make the endpoint `async def`, `body = json.loads(await request.body() or b"{}")`, then validate with
`ViewIn(**body)`. Return 204 even on invalid input, so the endpoint can't be probed.

In `app/main.py`:
- Delete `lifespan`, `_every`, `_flush_views_once`, `_flush_views_forever`, `_promote_due_once`, `_resume_sends_once`
  and the related constants and imports.
- Create the app without `lifespan=`.
- Include `public_views.router`.

In `site/routes.py`, remove the `views.record_view(...)` call on the article page.

`article.html`: add `data-view-slug="{{ article.slug }}"` on the article's root `<article>` element.

`site.js`: add, at the end of the init function:

```js
  /* ---------- view beacon (once per article per browser per day) ---------- */
  var viewed = $('[data-view-slug]');
  if (viewed && navigator.sendBeacon) {
    var slug = viewed.getAttribute('data-view-slug');
    var key = 'asi-viewed:' + slug + ':' + new Date().toISOString().slice(0, 10);
    var seen = false;
    try { seen = localStorage.getItem(key) === '1'; } catch (e) { seen = false; }
    if (!seen) {
      navigator.sendBeacon('/api/v1/views', JSON.stringify({ slug: slug }));
      try { localStorage.setItem(key, '1'); } catch (e) { /* private mode: count anyway */ }
    }
  }
```

Empty `NOT_YET_PORTED` (`NOT_YET_PORTED = set()`). Delete `app/cli/migrate.py` (the legacy SQL-file runner). Port
anything still flagged by `test_dialect.py`.

- [ ] **Step 4: Run the whole suite**

Run: `docker compose run --rm api pytest -q`
Expected: every test passes. This is the MariaDB port checkpoint: the launch build's behaviour suite is green on
MariaDB.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api
git commit -m "feat: view beacon replaces server-side counting; whole suite green on MariaDB"
```

---

### Task 7: Host routing, security headers, admin panel served by the app

**Files:**
- Create: `apps/api/app/core/hosts.py`
- Modify: `apps/api/app/core/settings.py` (`HOST_ROUTING`, `ADMIN_DIST_DIR`), `apps/api/app/core/middleware.py`, `apps/api/app/main.py`
- Test: `apps/api/tests/test_hosts.py`

**Interfaces:**
- Produces:
  - `hosts.site_of(host_header: str) -> Literal["public", "admin", "unknown"]`
  - `hosts.install(app)` (middleware)
  - `request.state.site`
  - settings `HOST_ROUTING: bool` (default: `IS_PRODUCTION`), `PUBLIC_HOST`, `ADMIN_HOST` (from `SITE_URL` /
    `ADMIN_URL`), `ADMIN_DIST_DIR` (default `<repo>/apps/admin/dist`)

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_hosts.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def routed(client, monkeypatch, tmp_path):
    from app.core import hosts

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>ASI admin</title>", encoding="utf8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf8")
    monkeypatch.setattr(hosts, "ENABLED", True)
    monkeypatch.setattr(hosts, "PUBLIC_HOST", "asi.test")
    monkeypatch.setattr(hosts, "ADMIN_HOST", "admin.asi.test")
    monkeypatch.setattr(hosts, "ADMIN_DIST", dist)
    return client


def test_public_host_serves_the_site_and_hides_admin(routed):
    assert routed.get("/", headers={"Host": "asi.test"}).status_code == 200
    assert routed.get("/admin/me", headers={"Host": "asi.test"}).status_code == 404


def test_admin_host_serves_api_and_spa_but_not_the_site(routed):
    assert routed.get("/admin/me", headers={"Host": "admin.asi.test"}).status_code == 401
    spa = routed.get("/articles/12", headers={"Host": "admin.asi.test"})
    assert spa.status_code == 200 and "ASI admin" in spa.text
    assert routed.get("/assets/app.js", headers={"Host": "admin.asi.test"}).text == "console.log(1)"
    assert routed.get("/markets", headers={"Host": "admin.asi.test"}).status_code == 200  # SPA route, not the site
    assert "ASI admin" in routed.get("/markets", headers={"Host": "admin.asi.test"}).text


def test_unknown_host_is_refused(routed):
    assert routed.get("/", headers={"Host": "evil.example"}).status_code == 404


def test_admin_host_headers(routed):
    r = routed.get("/", headers={"Host": "admin.asi.test"})
    assert r.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_routing_is_off_in_development(client):
    assert client.get("/admin/me").status_code == 401
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_hosts.py -q`
Expected: FAIL (`app.core.hosts` missing).

- [ ] **Step 3: Implement**

Settings:

```python
from urllib.parse import urlparse

HOST_ROUTING = os.environ.get("HOST_ROUTING", "true" if IS_PRODUCTION else "false").lower() == "true"
PUBLIC_HOST = urlparse(SITE_URL).hostname or ""
ADMIN_HOST = urlparse(ADMIN_URL).hostname or ""
ADMIN_DIST_DIR = os.environ.get(
    "ADMIN_DIST_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "..", "admin", "dist"))
```

`app/core/hosts.py`:

```python
"""One app, two host names (spec §2.1). Production only — development and
tests run everything on one host.

- public host: the site and /api/v1; /admin answers 404
- admin host:  the /admin API, plus the built admin panel (files from
               apps/admin/dist, index.html for any other path)
- any other Host header: 404 (no host-header games, nothing cached)
"""

from __future__ import annotations

import pathlib

from starlette.responses import FileResponse, PlainTextResponse

from app.core.settings import ADMIN_DIST_DIR, ADMIN_HOST, HOST_ROUTING, PUBLIC_HOST

ENABLED = HOST_ROUTING
ADMIN_DIST = pathlib.Path(ADMIN_DIST_DIR).resolve()
ADMIN_API_PREFIX = "/admin"
SHARED_PATHS = ("/healthz",)


def site_of(host_header: str) -> str:
    host = (host_header or "").split(":", 1)[0].lower().rstrip(".")
    if host == PUBLIC_HOST or host == f"www.{PUBLIC_HOST}":
        return "public"
    if host == ADMIN_HOST:
        return "admin"
    return "unknown"


def _not_found():
    return PlainTextResponse("Not found", status_code=404, headers={"Cache-Control": "no-store"})


def _admin_file(path: str):
    target = (ADMIN_DIST / path.lstrip("/")).resolve()
    if ADMIN_DIST in target.parents and target.is_file():
        return FileResponse(target, headers={"Cache-Control": "public, max-age=31536000, immutable"}
                            if "/assets/" in path else {"Cache-Control": "no-cache"})
    index = ADMIN_DIST / "index.html"
    return FileResponse(index, headers={"Cache-Control": "no-cache"}) if index.is_file() else _not_found()


def install(app) -> None:
    @app.middleware("http")
    async def route_by_host(request, call_next):
        if not ENABLED:
            request.state.site = "public"
            return await call_next(request)
        site = site_of(request.headers.get("host", ""))
        request.state.site = site
        path = request.url.path
        if path in SHARED_PATHS and site != "unknown":
            return await call_next(request)
        if site == "unknown":
            return _not_found()
        if site == "public":
            if path == ADMIN_API_PREFIX or path.startswith(ADMIN_API_PREFIX + "/"):
                return _not_found()
            return await call_next(request)
        # admin host
        if path == ADMIN_API_PREFIX or path.startswith(ADMIN_API_PREFIX + "/"):
            response = await call_next(request)
        else:
            response = _admin_file(path)
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["X-Frame-Options"] = "DENY"
        return response
```

In `create_app()`, call `hosts.install(app)` after `middleware.install(app)`. Starlette applies the last-added
middleware first, so host routing runs before everything else.

In `app/core/middleware.py`, the admin CSP: when `getattr(request.state, "site", "public") == "admin"`, set
`Content-Security-Policy` to:

```
default-src 'self'; img-src 'self' data: <SITE_URL origin>; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
```

HSTS stays as is (`COOKIE_SECURE`).

- [ ] **Step 4: Run to verify they pass**

Run: `docker compose run --rm api pytest tests/test_hosts.py tests/test_site_base.py tests/test_auth.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api
git commit -m "feat: route by host name — public site, admin panel and API from one app"
```

---

### Task 8: Page cache

**Files:**
- Create: `apps/api/app/core/page_cache.py`
- Modify: `apps/api/app/core/settings.py` (`PAGE_CACHE_ROOT`), `apps/api/app/main.py`, `apps/api/app/services/editorial.py` (`invalidate_public`, article-change purge)
- Modify: every admin mutation that affects public output. Article endpoints call `page_cache.article_changed(paths)`;
  site-wide endpoints (site text, snapshot, ticker, homepage slots and banner, countries, regulators, regulatory
  entries, report figures, FX, user byline/profile, media replace) call `page_cache.site_changed()`.
- Test: `apps/api/tests/test_page_cache.py`

**Interfaces:**
- Produces:
  - `page_cache.enabled() -> bool`
  - `is_cacheable_path(path) -> bool`
  - `file_for(path, content_type) -> pathlib.Path | None`
  - `generation() -> int`
  - `store(path, content_type, body: bytes, generation_at_start: int) -> bool`
  - `lookup(path) -> tuple[bytes, str] | None`
  - `purge_all() -> None`, `purge_lists() -> None`, `purge_paths(paths: list[str]) -> None`
  - `article_changed(paths: list[str]) -> None` (= purge those paths + lists)
  - `site_changed() -> None` (= purge all)
  - `expire(list_max_age=600, article_max_age=86400, now=None) -> int`
  - `PageCacheMiddleware` (ASGI)
  - setting `PAGE_CACHE_ROOT: str` ("" = disabled)

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_page_cache.py`:

```python
import os
import time

import pytest

from app.core import page_cache


@pytest.fixture()
def cache_dir(tmp_path, monkeypatch):
    root = tmp_path / "_cache"
    monkeypatch.setattr(page_cache, "ROOT", root)
    return root


def test_home_is_written_on_first_render_and_served_from_file(client, cache_dir):
    first = client.get("/")
    assert first.status_code == 200 and (cache_dir / "index.html").is_file()
    second = client.get("/")
    assert second.headers.get("X-ASI-Cache") == "app" and second.text == first.text


def test_never_cached_requests(client, cache_dir, publish):
    client.get("/?country=NG")
    client.get("/search?q=naira")
    client.get("/no-such-page")
    client.post("/api/v1/views", json={"slug": "x"})
    client.get("/healthz")
    client.get("/admin/me")
    stored = list(cache_dir.rglob("index.*")) if cache_dir.exists() else []
    assert stored == []


def test_path_traversal_is_never_cached(cache_dir):
    assert page_cache.file_for("/../../etc/passwd", "text/html") is None
    assert page_cache.file_for("/markets/%2e%2e/x", "text/html") is None
    assert page_cache.store("/a/../../b", "text/html; charset=utf-8", b"x", page_cache.generation()) is False


def test_content_types_map_to_extensions(cache_dir):
    assert page_cache.file_for("/", "text/html; charset=utf-8").name == "index.html"
    assert page_cache.file_for("/api/v1/home", "application/json").name == "index.json"
    assert page_cache.file_for("/feed.xml", "application/rss+xml").name == "index.xml"
    assert page_cache.file_for("/robots.txt", "text/plain").name == "index.txt"
    assert page_cache.file_for("/x", "image/png") is None


def test_publishing_purges_lists_but_keeps_other_articles(client, cache_dir, publish):
    old = publish("Older story")
    client.get("/"), client.get(f"/markets/{old}")
    publish("Brand new story")
    assert not (cache_dir / "index.html").exists()
    assert (cache_dir / "markets" / old / "index.html").exists()
    assert "Brand new story" in client.get("/").text


def test_renaming_a_live_article_purges_the_old_address(client, cache_dir, publish, make_user, db_session):
    from sqlalchemy import text

    slug = publish("Name before")
    client.get(f"/markets/{slug}")
    art_id = db_session.execute(text("SELECT id FROM content_articles WHERE slug=:s"), {"s": slug}).scalar()
    _, ed = make_user("editor")
    r = client.put(f"/admin/articles/{art_id}", headers=ed,
                   json={"title": "Name after", "body_md": "Body text.", "tag": "Markets", "slug": "name-after"})
    assert r.status_code == 200, r.json()
    assert not (cache_dir / "markets" / slug / "index.html").exists()
    moved = client.get(f"/markets/{slug}", follow_redirects=False)
    assert moved.status_code == 301 and moved.headers["location"].endswith("/markets/name-after")


def test_site_wide_change_purges_everything(client, cache_dir, publish, make_user):
    slug = publish("Kept until site change")
    client.get("/"), client.get(f"/markets/{slug}")
    _, admin = make_user("admin")
    client.put("/admin/site-text/footer_note", headers=admin, json={"value_md": "New footer"})
    assert not any(cache_dir.rglob("index.html"))


def test_render_that_raced_a_purge_is_not_stored(cache_dir):
    started = page_cache.generation()
    page_cache.purge_lists()                       # an edit lands while the page renders
    assert page_cache.store("/", "text/html", b"stale", started) is False
    assert not (cache_dir / "index.html").exists()


def test_expire_removes_old_list_pages_sooner_than_articles(cache_dir):
    page_cache.store("/", "text/html", b"home", page_cache.generation())
    page_cache.store("/markets/x", "text/html", b"article", page_cache.generation())
    old = time.time() - 3600
    for f in cache_dir.rglob("index.html"):
        os.utime(f, (old, old))
    assert page_cache.expire(list_max_age=600, article_max_age=86400) == 1
    assert (cache_dir / "markets" / "x" / "index.html").exists()


def test_cached_bytes_are_identical_for_different_visitors(client, cache_dir):
    a = client.get("/", cookies={"asi_session": "visitor-a"}).content
    page_cache.purge_all()
    b = client.get("/", cookies={"theme": "dark"}).content
    assert a == b
```

Before writing `test_site_wide_change_purges_everything`, read the site-text admin route. Use its real
path/method/body (in `apps/api/app/api/admin/site_text.py`) and an existing key from `seed_data.SITE_TEXT`.

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_page_cache.py -q`
Expected: FAIL (`page_cache` missing).

- [ ] **Step 3: Implement**

Setting: `PAGE_CACHE_ROOT = os.environ.get("PAGE_CACHE_ROOT", "")`.

`app/core/page_cache.py`:

```python
"""Disk page cache (spec §2.2).

After a public page renders, its bytes are written to
<PAGE_CACHE_ROOT>/<path>/index.<ext>. On the host, .htaccess serves that file
directly — Python never starts for most readers. When .htaccess cannot (or in
development), the middleware below serves the file itself.

Purging deletes files; a generation number (a file whose content increments
on every purge) stops a page that started rendering before a purge from being
written after it.
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import tempfile
import time

from app.core.settings import PAGE_CACHE_ROOT

ROOT = pathlib.Path(PAGE_CACHE_ROOT) if PAGE_CACHE_ROOT else None
EXTENSIONS = {"text/html": "html", "application/json": "json", "application/xml": "xml",
              "application/rss+xml": "xml", "text/xml": "xml", "text/plain": "txt"}
CONTENT_TYPES = {"html": "text/html; charset=utf-8", "json": "application/json", "xml": "application/xml",
                 "txt": "text/plain; charset=utf-8"}
NEVER = ("/admin", "/healthz", "/search", "/static/", "/media/", "/docs", "/openapi.json",
         "/newsletter/confirm", "/newsletter/unsubscribe", "/api/v1/newsletter", "/api/v1/views")
SAFE_PATH = re.compile(r"^/[A-Za-z0-9/._-]*$")
ARTICLE_PATH = re.compile(r"^/(markets|regulation)/[a-z0-9-]+$")
GENERATION_FILE = ".generation"


def enabled() -> bool:
    return ROOT is not None


def is_cacheable_path(path: str) -> bool:
    if not SAFE_PATH.match(path) or ".." in path or "//" in path:
        return False
    return not any(path == p.rstrip("/") or path.startswith(p if p.endswith("/") else p + "/") or path == p
                   for p in NEVER)


def file_for(path: str, content_type: str) -> pathlib.Path | None:
    if ROOT is None or not is_cacheable_path(path):
        return None
    ext = EXTENSIONS.get((content_type or "").split(";", 1)[0].strip().lower())
    if not ext:
        return None
    target = (ROOT / path.strip("/") / f"index.{ext}").resolve()
    root = ROOT.resolve()
    return target if root in target.parents else None


def generation() -> int:
    if ROOT is None:
        return 0
    try:
        return int((ROOT / GENERATION_FILE).read_text())
    except (OSError, ValueError):
        return 0


def _bump() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    _atomic_write(ROOT / GENERATION_FILE, str(generation() + 1).encode())


def _atomic_write(target: pathlib.Path, body: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
    with os.fdopen(fd, "wb") as handle:
        handle.write(body)
    os.chmod(tmp, 0o644)
    os.replace(tmp, target)


def store(path: str, content_type: str, body: bytes, generation_at_start: int) -> bool:
    target = file_for(path, content_type)
    if target is None or generation() != generation_at_start:
        return False
    _atomic_write(target, body)
    return True


def lookup(path: str) -> tuple[bytes, str] | None:
    if ROOT is None or not is_cacheable_path(path):
        return None
    for ext, ctype in CONTENT_TYPES.items():
        candidate = ROOT / path.strip("/") / f"index.{ext}"
        if candidate.is_file():
            return candidate.read_bytes(), ctype
    return None


def _cached_files():
    if ROOT is None or not ROOT.exists():
        return []
    return [p for p in ROOT.rglob("index.*") if p.is_file()]


def _url_of(file: pathlib.Path) -> str:
    rel = file.parent.relative_to(ROOT).as_posix()
    return "/" if rel == "." else f"/{rel}"


def purge_paths(paths: list[str]) -> None:
    if ROOT is None:
        return
    _bump()
    for path in paths:
        if is_cacheable_path(path):
            for ext in CONTENT_TYPES:
                (ROOT / path.strip("/") / f"index.{ext}").unlink(missing_ok=True)


def purge_lists() -> None:
    if ROOT is None:
        return
    _bump()
    for file in _cached_files():
        if not ARTICLE_PATH.match(_url_of(file)):
            file.unlink(missing_ok=True)


def purge_all() -> None:
    if ROOT is None or not ROOT.exists():
        return
    _bump()
    for child in ROOT.iterdir():
        if child.name != GENERATION_FILE:
            shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink(missing_ok=True)


def article_changed(paths: list[str]) -> None:
    purge_paths(paths)
    purge_lists()


def site_changed() -> None:
    purge_all()


def expire(list_max_age: int = 600, article_max_age: int = 86400, now: float | None = None) -> int:
    now = now or time.time()
    removed = 0
    for file in _cached_files():
        limit = article_max_age if ARTICLE_PATH.match(_url_of(file)) else list_max_age
        if now - file.stat().st_mtime > limit:
            file.unlink(missing_ok=True)
            removed += 1
    return removed


class PageCacheMiddleware:
    """Writes cacheable public responses to disk and serves them back when the
    web server did not (development, or hosts where .htaccess can't)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or ROOT is None or scope["method"] not in ("GET", "HEAD")
                or scope.get("query_string") or not is_cacheable_path(scope["path"])
                or scope.get("state", {}).get("site", "public") != "public"):
            return await self.app(scope, receive, send)
        hit = lookup(scope["path"])
        if hit:
            body, ctype = hit
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", ctype.encode()), (b"x-asi-cache", b"app"),
                                    (b"cache-control", b"public, max-age=60")]})
            await send({"type": "http.response.body", "body": b"" if scope["method"] == "HEAD" else body})
            return
        started = generation()
        head, chunks = {}, []

        async def capture(message):
            if message["type"] == "http.response.start":
                head.update(message)
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
            await send(message)

        await self.app(scope, receive, capture)
        if scope["method"] != "GET" or head.get("status") != 200:
            return
        headers = {k.decode().lower(): v.decode() for k, v in head.get("headers", [])}
        if "set-cookie" in headers or "no-store" in headers.get("cache-control", ""):
            return
        store(scope["path"], headers.get("content-type", ""), b"".join(chunks), started)
```

Three notes on this code:
- `request.state.site` is set by `hosts` middleware in `scope["state"]`. Starlette keeps `request.state` in
  `scope["state"]`, so this check works when `PageCacheMiddleware` runs inside the host middleware.
- Register `app.add_middleware(PageCacheMiddleware)` **before** `hosts.install(app)` in `create_app()`. Middleware
  added later runs first, so hosts runs before page cache.
- `test_never_cached_requests` uses `/admin/me` without routing; it must not be stored because `/admin` is in `NEVER`.

Wire purges:
- `editorial.invalidate_public()` → `page_cache.purge_lists()`.
- In the admin article endpoints (create, update, publish, review/approve, unpublish, delete, correction, revision
  restore, feature toggle), call `page_cache.article_changed([old_url, new_url])` after commit when the article is
  or was live. `old_url` is the article's URL before the change (it differs on rename or section change).
- `promote_due` calls `page_cache.article_changed(paths)`.
- Site-wide admin endpoints call `page_cache.site_changed()` after commit, instead of `editorial.invalidate_public()`.

Grep `invalidate_public` and decide each call: article-scoped → `article_changed`; anything else → `site_changed`.

Configure in tests: `conftest.py` leaves `PAGE_CACHE_ROOT` empty (disabled) except in `test_page_cache.py`, whose
fixture monkeypatches `ROOT`.

- [ ] **Step 4: Run to verify they pass**

Run: `docker compose run --rm api pytest tests/test_page_cache.py -q && docker compose run --rm api pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api
git commit -m "feat: disk page cache with event purges, generation guard and expiry"
```

---

### Task 9: Job runner and jobs (tick, newsletter, cleanup, backup, selfcheck)

**Files:**
- Create: `apps/api/app/jobs/__init__.py`, `apps/api/app/jobs/__main__.py`, `apps/api/app/jobs/runner.py`, `apps/api/app/jobs/tasks.py`, `apps/api/app/jobs/selfcheck.py`
- Modify: `apps/api/app/core/settings.py` (`LIVE_JSON_PATH`, `BACKUP_DIR`, `LOG_DIR`, `JOB_BUDGET_SECONDS`, `MEDIA_BACKUP_WEEKDAY`)
- Test: `apps/api/tests/test_jobs.py`

**Interfaces:**
- Consumes:
  - `editorial.promote_due`, `page_cache.expire`/`article_changed`, `live.payload`
  - `newsletter.send_pending`, `named_lock`/`release_lock`, `rate_limit` tables
- Produces:
  - `app.jobs.JOBS: dict[str, Job]`, where `Job = (name, fn(db, deadline) -> str, every_minutes: int)`
  - `runner.run(name: str, session_factory=None) -> dict`, which returns `{"status": "ok"|"failed"|"skipped", "detail": str}`
  - `python -m app.jobs <name>`
  - `selfcheck.run_checks(db, http_get=None) -> list[dict]`, rows of `{"check", "ok", "detail"}`

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_jobs.py`:

```python
import json

from sqlalchemy import text

from app.jobs import JOBS, runner


def _lagging(db, name):
    return db.execute(text("SELECT status, detail, error FROM ops_job_runs WHERE job=:j ORDER BY id DESC LIMIT 1"),
                      {"j": name}).mappings().first()


def test_every_job_is_registered():
    assert set(JOBS) >= {"tick", "newsletter", "cleanup", "backup", "global-metrics", "country-proxy",
                         "cross-check", "ng-official-rate", "selfcheck"}


def test_a_run_is_logged(db_session, monkeypatch):
    monkeypatch.setitem(JOBS, "probe", runner.Job("probe", lambda db, deadline: "did it", 1))
    result = runner.run("probe", session_factory=lambda: db_session)
    assert result == {"status": "ok", "detail": "did it"}
    assert _lagging(db_session, "probe")["status"] == "ok"


def test_a_running_job_is_not_started_twice(db_session, monkeypatch):
    from app.core.db import engine, named_lock, release_lock

    monkeypatch.setitem(JOBS, "probe", runner.Job("probe", lambda db, deadline: "ran", 1))
    with engine.connect() as other:
        assert named_lock(other, "job:probe")
        assert runner.run("probe", session_factory=lambda: db_session)["status"] == "skipped"
        release_lock(other, "job:probe")


def test_failure_alerts_once_until_a_success(db_session, monkeypatch, outbox):
    monkeypatch.setattr(runner, "ALERT_EMAIL_TO", "ops@example.com")
    boom = runner.Job("probe", lambda db, deadline: (_ for _ in ()).throw(RuntimeError("feed down")), 1)
    monkeypatch.setitem(JOBS, "probe", boom)
    runner.run("probe", session_factory=lambda: db_session)
    runner.run("probe", session_factory=lambda: db_session)
    assert len([m for m in outbox.messages if "probe" in m.subject]) == 1
    assert "feed down" in _lagging(db_session, "probe")["error"]
    monkeypatch.setitem(JOBS, "probe", runner.Job("probe", lambda db, deadline: "back", 1))
    runner.run("probe", session_factory=lambda: db_session)
    monkeypatch.setitem(JOBS, "probe", boom)
    runner.run("probe", session_factory=lambda: db_session)
    assert len([m for m in outbox.messages if "probe" in m.subject]) == 2


def test_tick_promotes_due_stories_and_writes_live_json(client, make_user, draft_with_source, db_session,
                                                       monkeypatch, tmp_path):
    from app.jobs import tasks
    from tests.helpers import FULL_CHECKLIST

    monkeypatch.setattr("app.services.seo.indexnow_ping", lambda paths, background=True: None)
    monkeypatch.setattr(tasks, "LIVE_JSON_PATH", str(tmp_path / "live.json"))
    art_id, _ = draft_with_source(title="Tick promotes me")
    _, ed = make_user("editor")
    client.post(f"/admin/articles/{art_id}/review", json={"decision": "approved", "checklist": FULL_CHECKLIST,
                                                          "publish_at": "2099-01-01T08:00:00+01:00"}, headers=ed)
    db_session.execute(text("UPDATE content_articles SET published_at = UTC_TIMESTAMP(6) - INTERVAL 1 MINUTE "
                            "WHERE id = :i"), {"i": art_id})
    db_session.commit()
    detail = tasks.tick(db_session, deadline=None)
    assert "promoted 1" in detail
    assert json.loads((tmp_path / "live.json").read_text())["ticker"] is not None


def test_cleanup_prunes_expired_rows(db_session):
    from app.core import rate_limit
    from app.jobs import tasks

    db_session.execute(text("INSERT INTO ops_rate_limits (bucket, window_start, hits) "
                            "VALUES ('old', UTC_TIMESTAMP() - INTERVAL 2 DAY, 1)"))
    db_session.execute(text("INSERT INTO auth_revoked_tokens (jti, expires_at) "
                            "VALUES ('gone', UTC_TIMESTAMP(6) - INTERVAL 1 HOUR)"))
    db_session.commit()
    tasks.cleanup(db_session, deadline=None)
    assert db_session.execute(text("SELECT COUNT(*) FROM ops_rate_limits WHERE bucket='old'")).scalar() == 0
    assert db_session.execute(text("SELECT COUNT(*) FROM auth_revoked_tokens WHERE jti='gone'")).scalar() == 0


def test_selfcheck_reports_each_line(db_session, tmp_path, monkeypatch):
    from app.jobs import selfcheck

    monkeypatch.setattr(selfcheck, "WRITABLE_DIRS", {"cache": str(tmp_path)})
    calls = []

    def fake_get(url):
        calls.append(url)
        return 200, {"x-asi-cache": "file"} if len(calls) > 1 else {}

    rows = {r["check"]: r for r in selfcheck.run_checks(db_session, http_get=fake_get)}
    assert rows["database time zone is UTC"]["ok"] is True
    assert rows["writable: cache"]["ok"] is True
    assert rows["page cache served by the web server"]["ok"] is True
```

The `live.json` assertion depends on `live.payload`'s shape. Read `services/live.py` after Task 4 and assert on a
top-level key it really has.

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_jobs.py -q`
Expected: FAIL (`app.jobs` missing).

- [ ] **Step 3: Implement**

Settings:

```python
LIVE_JSON_PATH = os.environ.get("LIVE_JSON_PATH", "")
BACKUP_DIR = os.environ.get("BACKUP_DIR", os.path.join(DATA_DIR, "backups"))
LOG_DIR = os.environ.get("LOG_DIR", os.path.join(DATA_DIR, "logs"))
JOB_BUDGET_SECONDS = int(os.environ.get("JOB_BUDGET_SECONDS", "240"))
BACKUP_KEEP_DAILY = int(os.environ.get("BACKUP_KEEP_DAILY", "14"))
MEDIA_BACKUP_WEEKDAY = int(os.environ.get("MEDIA_BACKUP_WEEKDAY", "6"))   # Sunday; keep 2 media archives
```

`app/jobs/runner.py`:

```python
"""Runs one cron job: lock (never twice at once), time budget, run log in
ops_job_runs, one alert e-mail per failure streak."""

from __future__ import annotations

import time
import traceback
from typing import Callable, NamedTuple

from sqlalchemy import text

from app.core import email as mailer
from app.core.db import SessionLocal, engine, named_lock, release_lock
from app.core.settings import ALERT_EMAIL_TO, JOB_BUDGET_SECONDS


class Job(NamedTuple):
    name: str
    fn: Callable
    every_minutes: int


def _alert(db, name: str, error: str) -> None:
    if not ALERT_EMAIL_TO:
        return
    first = db.execute(text("INSERT IGNORE INTO ops_alert_state (job) VALUES (:j)"), {"j": name}).rowcount == 1
    db.commit()
    if first:
        try:
            mailer.send_email(ALERT_EMAIL_TO, f"[ASI alert] job {name} failed",
                              f"The {name} job failed:\n\n{error}\n\nSee Admin → System health.")
        except Exception as exc:  # noqa: BLE001 — an alert must never hide the failure
            print(f"[jobs] alert e-mail failed: {exc}")


def run(name: str, session_factory=None) -> dict:
    from app.jobs import JOBS

    job = JOBS[name]
    session_factory = session_factory or SessionLocal
    lock_conn = engine.connect()
    db = session_factory()
    try:
        if not named_lock(lock_conn, f"job:{name}"):
            return {"status": "skipped", "detail": "already running"}
        run_id = db.execute(text("INSERT INTO ops_job_runs (job) VALUES (:j) RETURNING id"), {"j": name}).scalar()
        db.commit()
        deadline = time.monotonic() + JOB_BUDGET_SECONDS
        try:
            detail = str(job.fn(db, deadline) or "")[:2000]
            db.execute(text("UPDATE ops_job_runs SET status='ok', finished_at=UTC_TIMESTAMP(6), detail=:d "
                            "WHERE id=:i"), {"d": detail, "i": run_id})
            db.execute(text("DELETE FROM ops_alert_state WHERE job = :j"), {"j": name})
            db.commit()
            return {"status": "ok", "detail": detail}
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=5)}"[:4000]
            db.execute(text("UPDATE ops_job_runs SET status='failed', finished_at=UTC_TIMESTAMP(6), error=:e "
                            "WHERE id=:i"), {"e": error, "i": run_id})
            db.commit()
            _alert(db, name, error)
            return {"status": "failed", "detail": str(exc)}
    finally:
        try:
            release_lock(lock_conn, f"job:{name}")
        finally:
            lock_conn.close()
            if not db.info.get("owned_by_test"):
                db.close()
```

`ALERT_EMAIL_TO` must be imported into `runner` as a module attribute, as above, so tests can monkeypatch it.

`app/jobs/tasks.py`:

```python
"""The cron jobs (spec §4). Each takes (db, deadline) and returns a one-line summary."""

from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core import page_cache
from app.core.settings import (BACKUP_DIR, BACKUP_KEEP_DAILY, DATABASE_URL, LIVE_JSON_PATH, LOG_DIR,
                               MAIL_MAX_PER_HOUR, MEDIA_BACKUP_WEEKDAY, MEDIA_ROOT, NEWSLETTER_BATCH_PAUSE)
from app.services import editorial, live
from app.services import newsletter as nl


def _write_atomic(path: str, body: bytes) -> None:
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".tmp-")
    with os.fdopen(fd, "wb") as handle:
        handle.write(body)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def tick(db, deadline) -> str:
    promoted = editorial.promote_due(db)
    if LIVE_JSON_PATH:
        payload = jsonable_encoder(live.payload(db))
        _write_atomic(LIVE_JSON_PATH, json.dumps(payload, separators=(",", ":")).encode())
    expired = page_cache.expire()
    return f"promoted {len(promoted)}, expired {expired} cached pages"


def newsletter(db, deadline) -> str:
    sent = nl.send_pending(db, max_per_hour=MAIL_MAX_PER_HOUR, deadline=deadline, sleep_s=NEWSLETTER_BATCH_PAUSE)
    return f"sent {sent}"


def cleanup(db, deadline) -> str:
    db.execute(text("DELETE FROM ops_rate_limits WHERE window_start < UTC_TIMESTAMP() - INTERVAL 1 DAY"))
    db.execute(text("DELETE FROM auth_revoked_tokens WHERE expires_at < UTC_TIMESTAMP(6)"))
    db.execute(text("DELETE FROM auth_totp_used WHERE used_at < UTC_TIMESTAMP(6) - INTERVAL 10 MINUTE"))
    db.execute(text("DELETE FROM ops_job_runs WHERE started_at < UTC_TIMESTAMP(6) - INTERVAL 90 DAY"))
    db.commit()
    rotated = 0
    if os.path.isdir(LOG_DIR):
        for name in os.listdir(LOG_DIR):
            path = os.path.join(LOG_DIR, name)
            if os.path.isfile(path) and os.path.getsize(path) > 5_000_000:
                with open(path, "rb") as handle:
                    handle.seek(-1_000_000, os.SEEK_END)
                    tail = handle.read()
                _write_atomic(path, tail)
                rotated += 1
    return f"pruned; rotated {rotated} logs"


def backup(db, deadline) -> str:
    """mariadb-dump (credentials in a temporary options file, never on the
    command line) + a weekly media archive. Keeps BACKUP_KEEP_DAILY dumps and
    2 media archives. Writes LAST_STATUS for System health."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    url = make_url(DATABASE_URL)
    dump_bin = shutil.which("mariadb-dump") or shutil.which("mysqldump")
    if not dump_bin:
        raise RuntimeError("mariadb-dump/mysqldump not found on PATH")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    with tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False) as opts:
        opts.write(f"[client]\nuser={url.username}\npassword={url.password}\nhost={url.host or 'localhost'}\n"
                   f"port={url.port or 3306}\n")
    try:
        target = os.path.join(BACKUP_DIR, f"db-{stamp}.sql.gz")
        with gzip.open(target, "wb") as out:
            proc = subprocess.run([dump_bin, f"--defaults-extra-file={opts.name}", "--single-transaction",
                                   "--routines", "--default-character-set=utf8mb4", url.database],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.decode(errors="replace")[:1000])
            out.write(proc.stdout)
    finally:
        os.unlink(opts.name)
    dumps = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("db-"))
    for old in dumps[:-BACKUP_KEEP_DAILY]:
        os.unlink(os.path.join(BACKUP_DIR, old))
    media_note = ""
    if datetime.now(timezone.utc).weekday() == MEDIA_BACKUP_WEEKDAY and os.path.isdir(MEDIA_ROOT):
        archive = os.path.join(BACKUP_DIR, f"media-{stamp}.tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(MEDIA_ROOT, arcname="media")
        media = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("media-"))
        for old in media[:-2]:
            os.unlink(os.path.join(BACKUP_DIR, old))
        media_note = ", media archived"
    _write_atomic(os.path.join(BACKUP_DIR, "LAST_STATUS"),
                  f"ok {datetime.now(timezone.utc).isoformat()} {os.path.basename(target)}\n".encode())
    return f"database dumped{media_note}"
```

The database-dump test is not run in CI (no dump binary guaranteed). The job's failure path is covered by the
runner tests. `deploy/test_htaccess.sh` (Task 13) runs a real dump in the MariaDB container as a smoke check.

`app/jobs/selfcheck.py`:

```python
"""python -m app.jobs selfcheck — verifies on the server everything the
design assumes about the host (spec §6). Prints a table; the job runner
stores the summary for System health."""

from __future__ import annotations

import os
import urllib.request

from sqlalchemy import text

from app.core.settings import DATA_DIR, MEDIA_ROOT, PAGE_CACHE_ROOT, SITE_URL

WRITABLE_DIRS = {"media": MEDIA_ROOT, "cache": PAGE_CACHE_ROOT, "data": DATA_DIR}
JOB_INTERVALS = {"tick": 1, "newsletter": 5, "global-metrics": 15, "country-proxy": 15, "cross-check": 15,
                 "ng-official-rate": 120, "cleanup": 1440, "backup": 1440}


def _http_get(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "asi-selfcheck"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status, {k.lower(): v for k, v in response.headers.items()}


def run_checks(db, http_get=None) -> list[dict]:
    http_get = http_get or _http_get
    rows = []

    def add(check, ok, detail=""):
        rows.append({"check": check, "ok": bool(ok), "detail": str(detail)})

    tz = db.execute(text("SELECT @@session.time_zone")).scalar()
    add("database time zone is UTC", tz == "+00:00", tz)
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    add("database migrated", bool(version), version)
    for name, path in WRITABLE_DIRS.items():
        ok = bool(path) and os.path.isdir(path) and os.access(path, os.W_OK)
        add(f"writable: {name}", ok, path or "not set")
    for job, minutes in JOB_INTERVALS.items():
        last = db.execute(text("SELECT MAX(started_at) FROM ops_job_runs WHERE job = :j AND status = 'ok' "
                               "AND started_at > UTC_TIMESTAMP(6) - INTERVAL :m MINUTE"),
                          {"j": job, "m": minutes * 2}).scalar()
        add(f"cron ran recently: {job}", last is not None, last or "no successful run in 2× its interval")
    try:
        http_get(SITE_URL + "/")
        status, headers = http_get(SITE_URL + "/")
        add("page cache served by the web server", status == 200 and headers.get("x-asi-cache") == "file",
            headers.get("x-asi-cache", "served by Python (fallback works, but .htaccess rule did not apply)"))
    except Exception as exc:  # noqa: BLE001
        add("page cache served by the web server", False, exc)
    return rows


def selfcheck(db, deadline) -> str:
    rows = run_checks(db)
    width = max(len(r["check"]) for r in rows)
    for r in rows:
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['check']:<{width}}  {r['detail']}")
    failed = [r["check"] for r in rows if not r["ok"]]
    if failed:
        raise RuntimeError("selfcheck failed: " + "; ".join(failed))
    return f"all {len(rows)} checks passed"
```

The SMTP login check is part of `selfcheck`, too. Add:

```python
    try:
        import smtplib
        from app.core.settings import SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_SSL, SMTP_USER
        cls = smtplib.SMTP_SSL if SMTP_SSL else smtplib.SMTP
        with cls(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if not SMTP_SSL and SMTP_USER:
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD or "")
        add("e-mail login", True, f"{SMTP_HOST}:{SMTP_PORT}")
    except Exception as exc:  # noqa: BLE001
        add("e-mail login", False, exc)
```

Put it before the HTTP check. `run_checks(..., smtp=False)` skips it in tests: add a keyword argument
`smtp: bool = True` and pass `smtp=False` from the test.

`app/jobs/__init__.py`:

```python
"""Cron jobs. Registry only; pipelines register in Task 10."""

from app.jobs import selfcheck as _selfcheck
from app.jobs import tasks as _tasks
from app.jobs.runner import Job

JOBS: dict[str, Job] = {
    "tick": Job("tick", _tasks.tick, 1),
    "newsletter": Job("newsletter", _tasks.newsletter, 5),
    "cleanup": Job("cleanup", _tasks.cleanup, 1440),
    "backup": Job("backup", _tasks.backup, 1440),
    "selfcheck": Job("selfcheck", _selfcheck.selfcheck, 0),
}
```

`app/jobs/__main__.py`:

```python
"""python -m app.jobs <name>   — run one job (what cron calls)
   python -m app.jobs --list   — list jobs"""

import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, HERE)

from app.core.envfile import load_env  # noqa: E402

load_env(os.environ.get("ASI_ENV_FILE", os.path.expanduser("~/asi/.env")))

from app.jobs import JOBS  # noqa: E402
from app.jobs.runner import run  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 2
    if argv[1] == "--list":
        print("\n".join(sorted(JOBS)))
        return 0
    if argv[1] not in JOBS:
        print(f"unknown job {argv[1]!r}; try --list")
        return 2
    result = run(argv[1])
    print(f"[{argv[1]}] {result['status']}: {result['detail']}")
    return 0 if result["status"] in ("ok", "skipped") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

`seo.indexnow_ping(paths, background=True)` runs in a thread. In a cron process the thread could be cut off at
exit. In `promote_due`, call `seo.indexnow_ping(paths, background=False)`.

- [ ] **Step 4: Run to verify they pass**

Run: `docker compose run --rm api pytest tests/test_jobs.py -q && docker compose run --rm api python -m app.jobs --list`
Expected: PASS; the list prints the job names.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api
git commit -m "feat: cron job runner with locks, run log, alerts; tick, newsletter, cleanup, backup, selfcheck"
```

---

### Task 10: Data pipelines as jobs

**Files:**
- Create: `apps/api/app/pipelines/__init__.py`, `common.py`, `global_metrics.py`, `country_proxy.py`, `cross_check.py`, `ng_official_rate.py`
- Modify: `apps/api/app/jobs/__init__.py` (register four jobs)
- Delete: `pipelines/` (whole directory, after the port)
- Test: `apps/api/tests/test_pipelines.py` (port `pipelines/tests/test_common.py` plus new tests)

**Interfaces:**
- Consumes: `runner.Job`, `db_json`, `requests`.
- Produces:
  - `common.flag(db, metric_key, variance_pct, detail) -> bool`: True only when a new flag was raised.
  - Each module exposes `run(db, deadline) -> str` and keeps its fetch/parse functions pure (take a `get` callable
    for HTTP).

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_pipelines.py`:

```python
import pytest
from sqlalchemy import text

from app.pipelines import common, country_proxy, cross_check, global_metrics


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_flag_never_duplicates_an_open_alert(db_session):
    assert common.flag(db_session, "probe_metric", 12.5, {"why": "test"}) is True
    assert common.flag(db_session, "probe_metric", 13.0, {"why": "again"}) is False


def test_global_metrics_writes_total_and_shares(db_session):
    payload = {"peggedAssets": [
        {"symbol": "USDT", "circulating": {"peggedUSD": 600}},
        {"symbol": "USDC", "circulating": {"peggedUSD": 300}},
        {"symbol": "DAI", "circulating": {"peggedUSD": 100}}]}
    detail = global_metrics.run(db_session, None, get=lambda url, timeout: FakeResponse(payload))
    row = db_session.execute(text("SELECT stablecoin_supply_usd, usdt_share_pct FROM market_global_metrics "
                                  "ORDER BY id DESC LIMIT 1")).first()
    assert float(row[0]) == 1000 and float(row[1]) == 60 and "1,000" in detail


def test_global_metrics_refuses_a_shape_change(db_session):
    with pytest.raises(RuntimeError, match="peggedAssets"):
        global_metrics.run(db_session, None, get=lambda url, timeout: FakeResponse({"unexpected": True}))


def test_country_proxy_survives_one_source_failing(db_session):
    def get(url, timeout):
        if "quidax" in url:
            return FakeResponse({"data": {"ticker": {"last": "1600"}}})
        if "valr" in url:
            return FakeResponse([{"currencyPair": "USDCZAR", "lastTradedPrice": "18.2"}])
        raise RuntimeError("luno down")

    detail = country_proxy.run(db_session, None, get=get)
    pairs = {r[0] for r in db_session.execute(text(
        "SELECT pair FROM market_country_proxy_metrics WHERE source IN ('quidax','valr')"))}
    assert pairs == {"USDTNGN", "USDCZAR"} and "2 row" in detail


def test_country_proxy_fails_when_every_source_fails(db_session):
    def get(url, timeout):
        raise RuntimeError("all down")

    with pytest.raises(RuntimeError, match="ALL sources failed"):
        country_proxy.run(db_session, None, get=get)


def test_cross_check_writes_hourly_trend_points(db_session):
    db_session.execute(text("INSERT INTO market_global_metrics (ts, stablecoin_supply_usd, source) "
                            "VALUES (UTC_TIMESTAMP(6), 1234, 'test')"))
    db_session.commit()
    cross_check.run(db_session, None)
    point = db_session.execute(text("SELECT value FROM market_metric_trend_snapshots "
                                    "WHERE metric_key='global_supply' ORDER BY ts DESC LIMIT 1")).scalar()
    assert float(point) == 1234
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_pipelines.py -q`
Expected: FAIL (`app.pipelines` missing).

- [ ] **Step 3: Port**

`app/pipelines/common.py`:

```python
"""Shared pipeline helpers: data-quality flags (never duplicated while one is
still open). Alerts on failure come from the job runner."""

import json

from sqlalchemy import text

FLAG_DEDUPE_HOURS = 6


def flag(db, metric_key: str, variance_pct: float | None, detail: dict) -> bool:
    exists = db.execute(text(
        f"""SELECT 1 FROM market_data_quality_flags
            WHERE metric_key = :k AND resolved = 0
              AND flagged_at > UTC_TIMESTAMP(6) - INTERVAL {FLAG_DEDUPE_HOURS} HOUR LIMIT 1"""),
        {"k": metric_key}).first()
    if exists:
        return False
    db.execute(text("INSERT INTO market_data_quality_flags (metric_key, variance_pct, detail) VALUES (:k, :v, :d)"),
               {"k": metric_key, "v": variance_pct, "d": json.dumps(detail, default=str)})
    db.commit()
    return True
```

`app/pipelines/global_metrics.py`: move the body of `fetch_and_store` from `pipelines/dags/dag_global_metrics.py`
into `run(db, deadline, get=requests.get)`. Keep the module docstring and the defensive checks verbatim. Replace
the psycopg2 insert with:

```python
    db.execute(text("""INSERT INTO market_global_metrics (ts, stablecoin_supply_usd, usdt_share_pct, usdc_share_pct, source)
                       VALUES (UTC_TIMESTAMP(6), :total, :usdt, :usdc, 'defillama')"""),
               {"total": total, "usdt": usdt_share_pct, "usdc": usdc_share_pct})
    db.commit()
    return f"wrote total=${total:,.0f} usdt={usdt_share_pct}% usdc={usdc_share_pct}%"
```

Call `get(DEFILLAMA_URL, timeout=15)`. Add retries: wrap each HTTP call in
`for attempt in range(3): try … except Exception: if attempt == 2: raise; time.sleep(2 ** attempt * 5)`. Use a
helper `common.fetch(get, url, timeout)` doing exactly that, and use it in every pipeline. The tests pass a `get`
that succeeds or raises immediately. For the failing case, patch `time.sleep` to a no-op through
`monkeypatch.setattr("app.pipelines.common.time.sleep", lambda s: None)` in the two tests that raise. Add that
monkeypatch to `test_country_proxy_survives_one_source_failing` and
`test_country_proxy_fails_when_every_source_fails`.

`app/pipelines/country_proxy.py`: port `fetch_quidax`, `fetch_valr` and `fetch_luno` as plain functions
`(db, get) -> list[dict]`. Keep the per-source `try/except` that logs and returns `[]`. `_lookup_official_rate(db, cc, pair)`:

```sql
SELECT rate FROM market_official_rates WHERE country_code = :cc
ORDER BY (pair = :pair) DESC, effective_date DESC, updated_at DESC LIMIT 1
```

`run(db, deadline, get=requests.get)` calls the three, raises
`RuntimeError("country_proxy: ALL sources failed this run …")` when every list is empty, and inserts rows with
`ts = datetime.now(timezone.utc)` (aware; the driver stores UTC):

```sql
INSERT INTO market_country_proxy_metrics (ts, country_code, pair, p2p_rate, official_rate, source)
VALUES (:ts, :country_code, :pair, :p2p_rate, :official_rate, :source)
```

It then commits and returns `f"upserted {n} row(s)"`.

`app/pipelines/cross_check.py`: port each `check_*` task and `write_trend_snapshots` as functions `(db) -> None`,
and have `run(db, deadline)` call them in the DAG's order, then return a summary. SQL conversions:
- `DISTINCT ON (country_code, pair) … ORDER BY country_code, pair, ts DESC` → P12 with
  `PARTITION BY country_code, pair`.
- `DISTINCT ON (country_code)` → P12.
- `now() - interval '2 hours'` → `UTC_TIMESTAMP(6) - INTERVAL 2 HOUR`.
- `SELECT now()` → use `datetime.now(timezone.utc)` in Python.
- Trend snapshots:

```sql
INSERT INTO market_metric_trend_snapshots (ts, metric_key, value)
SELECT DATE_FORMAT(ts, '%Y-%m-%d %H:00:00'), 'global_supply', stablecoin_supply_usd
FROM market_global_metrics
WHERE ts = (SELECT m FROM (SELECT MAX(ts) AS m FROM market_global_metrics) x)
  AND stablecoin_supply_usd IS NOT NULL
ON DUPLICATE KEY UPDATE value = VALUES(value)
```

```sql
INSERT INTO market_metric_trend_snapshots (ts, metric_key, value)
SELECT DATE_FORMAT(ts, '%Y-%m-%d %H:00:00'), CONCAT('premium_', country_code), premium_pct
FROM (SELECT country_code, ts, premium_pct,
             ROW_NUMBER() OVER (PARTITION BY country_code ORDER BY ts DESC) AS rn
        FROM market_country_proxy_metrics WHERE premium_pct IS NOT NULL) x
WHERE rn = 1
ON DUPLICATE KEY UPDATE value = VALUES(value)
```

Keep the existing alert rule: send an e-mail only when `flag()` returned True. Raise `RuntimeError` listing the new
flags, so the runner's single alert covers them. Read the DAG first: if it e-mails itself through
`send_alert`, replace that with collecting messages and raising at the end of `run`.

`app/pipelines/ng_official_rate.py`: port `fetch_and_apply`. The update uses P18:

```sql
UPDATE market_country_proxy_metrics SET official_rate = :rate
WHERE country_code = 'NG'
  AND ts = (SELECT m FROM (SELECT MAX(ts) AS m FROM market_country_proxy_metrics WHERE country_code = 'NG') x)
```

Register in `app/jobs/__init__.py`:

```python
from app.pipelines import country_proxy, cross_check, global_metrics, ng_official_rate

JOBS.update({
    "global-metrics": Job("global-metrics", global_metrics.run, 15),
    "country-proxy": Job("country-proxy", country_proxy.run, 15),
    "cross-check": Job("cross-check", cross_check.run, 15),
    "ng-official-rate": Job("ng-official-rate", ng_official_rate.run, 120),
})
```

`run(db, deadline, get=requests.get)` keeps `get` optional, so the runner's `job.fn(db, deadline)` call works.
Add `requests==2.32.3` to `requirements.txt` if it isn't there.

Delete `pipelines/` with `git rm -r pipelines`.

- [ ] **Step 4: Run to verify they pass**

Run: `docker compose run --rm api pytest tests/test_pipelines.py tests/test_jobs.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api pipelines
git commit -m "feat: data pipelines run as cron jobs (Airflow removed)"
```

---

### Task 11: System health in the admin panel; live figures from live.json

**Files:**
- Create: `apps/api/app/api/admin/system.py`, `apps/admin/src/pages/SystemHealth.jsx`, `apps/admin/src/pages/systemRules.js`, `apps/admin/src/__tests__/systemRules.test.js`
- Modify: `apps/api/app/main.py` (router), `apps/admin/src/App.jsx` (route), `apps/admin/src/components/Layout.jsx` (nav link), `apps/api/app/site/static/js/site.js` (live.json)
- Test: `apps/api/tests/test_system.py`

**Interfaces:**
- Consumes: `ops_job_runs`, `selfcheck.JOB_INTERVALS`, `BACKUP_DIR/LAST_STATUS`.
- Produces:
  - `GET /admin/system` (admin role) returns `{"jobs": [{"job", "last_ok", "last_status", "last_error",
    "every_minutes", "late"}], "backup": {"status", "line"}, "mail": {"max_per_hour", "sent_last_hour"},
    "selfcheck": {"status", "detail", "at"}}`
  - `systemRules.jobState(job) -> "ok" | "late" | "failing"`

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_system.py`:

```python
from sqlalchemy import text


def test_system_health_lists_jobs_and_marks_late_ones(client, make_user, db_session):
    db_session.execute(text("INSERT INTO ops_job_runs (job, started_at, finished_at, status) VALUES "
                            "('tick', UTC_TIMESTAMP(6) - INTERVAL 30 MINUTE, UTC_TIMESTAMP(6) - INTERVAL 30 MINUTE, 'ok')"))
    db_session.commit()
    _, admin = make_user("admin")
    body = client.get("/admin/system", headers=admin).json()
    tick = next(j for j in body["jobs"] if j["job"] == "tick")
    assert tick["late"] is True and tick["last_status"] == "ok"
    assert "max_per_hour" in body["mail"]


def test_system_health_is_admin_only(client, make_user):
    _, editor = make_user("editor")
    assert client.get("/admin/system", headers=editor).status_code == 403
```

`apps/admin/src/__tests__/systemRules.test.js`:

```js
import { describe, expect, it } from "vitest";
import { jobState } from "../pages/systemRules";

describe("job state", () => {
  it("is failing when the last run failed", () => {
    expect(jobState({ last_status: "failed", late: false })).toBe("failing");
  });
  it("is late when no successful run in twice its interval", () => {
    expect(jobState({ last_status: "ok", late: true })).toBe("late");
  });
  it("is ok otherwise", () => {
    expect(jobState({ last_status: "ok", late: false })).toBe("ok");
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_system.py -q; cd apps/admin && npx vitest run`
Expected: FAIL.

- [ ] **Step 3: Implement**

`app/api/admin/system.py`:

```python
"""System health for admins: cron jobs, backups, mail volume, last selfcheck."""

import os

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role
from app.core.settings import BACKUP_DIR, MAIL_MAX_PER_HOUR
from app.jobs.selfcheck import JOB_INTERVALS
from app.services import newsletter as nl

router = APIRouter(prefix="/admin/system", tags=["admin"])


@router.get("")
def system_health(user: dict = Depends(require_role("admin")), db: Session = Depends(get_db)):
    jobs = []
    for job, minutes in JOB_INTERVALS.items():
        last = db.execute(text("SELECT status, error, started_at FROM ops_job_runs WHERE job = :j "
                               "ORDER BY id DESC LIMIT 1"), {"j": job}).mappings().first()
        last_ok = db.execute(text("SELECT MAX(started_at) FROM ops_job_runs WHERE job = :j AND status = 'ok'"),
                             {"j": job}).scalar()
        late = db.execute(text("SELECT :t IS NULL OR :t < UTC_TIMESTAMP(6) - INTERVAL :m MINUTE"),
                          {"t": last_ok, "m": minutes * 2}).scalar()
        jobs.append({"job": job, "every_minutes": minutes, "last_ok": last_ok,
                     "last_status": last["status"] if last else None,
                     "last_error": (last["error"] or "")[:500] if last else None, "late": bool(late)})
    status_file = os.path.join(BACKUP_DIR, "LAST_STATUS")
    line = open(status_file, encoding="utf8").read().strip() if os.path.exists(status_file) else ""
    selfcheck = db.execute(text("SELECT status, COALESCE(detail, error) AS detail, started_at AS at "
                                "FROM ops_job_runs WHERE job = 'selfcheck' ORDER BY id DESC LIMIT 1")).mappings().first()
    return {"jobs": jobs,
            "backup": {"status": line.split(" ", 1)[0] if line else "none", "line": line},
            "mail": {"max_per_hour": MAIL_MAX_PER_HOUR, "sent_last_hour": nl.sent_last_hour(db)},
            "selfcheck": dict(selfcheck) if selfcheck else None}
```

Include the router in `create_app()`.

`apps/admin/src/pages/systemRules.js`:

```js
/** How a cron job looks on the System health page. */
export function jobState(job) {
  if (job.last_status === "failed") return "failing";
  if (job.late) return "late";
  return "ok";
}
```

`apps/admin/src/pages/SystemHealth.jsx`: a page in the style of `Dashboard.jsx` (read it for the `useApi`/`get`
helper and the `ui.jsx` components). It contains:
- a table of jobs (name, every N min, last success with relative time, state badge from `jobState`, last error in a
  `<details>`)
- a backup line
- "Emails this hour: X of Y"
- the last selfcheck status and detail

Add `<Route path="system" element={<RequireAuth min="admin"><SystemHealth /></RequireAuth>} />` in `App.jsx`, and
a "System health" nav link for admins in `Layout.jsx` next to "Audit log".

`site.js`: change the live refresh to fetch `'/live.json?ts=' + Date.now()` first and fall back to `/api/v1/live`
when that request fails or returns non-200 (development has no `live.json`). Make sure the refresh runs once
immediately on page load and then every 60 seconds. If it currently waits 60 seconds for the first refresh, add an
immediate call, so a page served from cache shows current figures at once.

The `?ts=` makes the URL carry a query string, and `.htaccess` only serves the page cache for empty query strings.
`live.json` is a real static file, so Apache/nginx serve it directly anyway. Also set
`<Files "live.json"> Header set Cache-Control "no-cache" </Files>` in `htaccess.public` (Task 13).

- [ ] **Step 4: Run to verify they pass**

Run: `docker compose run --rm api pytest tests/test_system.py -q && cd apps/admin && npx vitest run && npm run build`
Expected: PASS; build succeeds.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api apps/admin
git commit -m "feat: System health page; live figures read live.json"
```

---

### Task 12: 3Consulting brand orange

**Files:**
- Modify: `apps/api/app/site/static/css/site.css`, `apps/admin/src/styles.css`, the favicon SVG(s) (`apps/api/app/site/static/` and `apps/admin/public/favicon.svg`), the social-card background constant if it uses ochre
- Test: `apps/api/tests/test_brand.py`

**Interfaces:**
- Produces: CSS tokens `--brand`, `--brand-ink`, `--brand-pale` in both stylesheets. `--ochre` and `--ochre-pale`
  are removed; every former use maps to a brand token.

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_brand.py`:

```python
"""3Consulting orange (#ff914d) is the main accent, and every text pairing the
stylesheets use with it stays readable (WCAG AA 4.5:1)."""

import os
import pathlib
import re

ROOT = pathlib.Path(os.environ.get("ASI_REPO") or pathlib.Path(__file__).resolve().parents[3])
SHEETS = [ROOT / "apps/api/app/site/static/css/site.css", ROOT / "apps/admin/src/styles.css"]


def _lum(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(a, b):
    hi, lo = sorted([_lum(a), _lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _tokens(css):
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", css))


def test_brand_tokens_present_and_ochre_gone():
    for sheet in SHEETS:
        css = sheet.read_text(encoding="utf8")
        tokens = _tokens(css)
        assert tokens["brand"].lower() == "#ff914d", sheet
        assert tokens["brand-ink"].lower() == "#a84d12", sheet
        assert tokens["brand-pale"].lower() == "#ffd2b3", sheet
        assert "--ochre" not in css, sheet


def test_text_pairings_meet_wcag_aa():
    for sheet in SHEETS:
        t = _tokens(sheet.read_text(encoding="utf8"))
        assert contrast(t["ink"], t["brand"]) >= 4.5
        assert contrast(t["brand-ink"], t["paper"]) >= 4.5
        assert contrast(t["ink"], t["brand-pale"]) >= 4.5


def test_brand_is_never_text_on_the_cream_page():
    for sheet in SHEETS:
        css = sheet.read_text(encoding="utf8")
        # "color: var(--brand)" (text) is allowed only inside rules for dark bands.
        for rule in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            selector, body = rule
            if re.search(r"(?<![-\w])color:\s*var\(--brand\)", body):
                assert re.search(r"dark|masthead|ticker|footer|header|\.primary", selector), selector


def test_never_white_text_on_brand():
    for sheet in SHEETS:
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", sheet.read_text(encoding="utf8")):
            if "background: var(--brand)" in body or "background-color: var(--brand)" in body:
                assert not re.search(r"(?<![-\w])color:\s*(#fff\b|#ffffff|white)", body), selector
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose run --rm api pytest tests/test_brand.py -q`
Expected: FAIL (`brand` missing, ochre present).

- [ ] **Step 3: Implement**

In both stylesheets' `:root`:
- Delete `--ochre` and `--ochre-pale`.
- Add:

```css
  --brand: #ff914d;       /* 3Consulting orange — fills with ink text; text only on dark bands */
  --brand-ink: #a84d12;   /* the same orange, deep enough for text on the cream page (4.9:1) */
  --brand-pale: #ffd2b3;  /* soft highlight backgrounds with ink text */
```

Replace every `var(--ochre)` with these rules:
- **Fills** (`background:`, `border-color`, `border-bottom-color`, focus `outline`): use `var(--brand)`. The text
  on those fills must be `var(--ink)`. This covers subscribe CTA, primary buttons, ticker label, tags, active nav
  underline, the skip link, the big-story rule and snapshot highlights.
- **Text on dark bands** (masthead, ticker, footer, `.dark-band`): `color: var(--brand)`.
- **Text on the cream page** (links on hover, section labels, small accents): `color: var(--brand-ink)`.
- **`var(--ochre-pale)`** becomes `var(--brand-pale)`.

`--amber` stays only where it marks "Delayed" or warnings. If it is used as a decorative accent, change it to
`var(--brand)` too.

Favicons and logo SVGs: replace the ochre fill `#c7862b` with `#ff914d`. In `services/media.py`,
`SOCIAL_BACKGROUND` stays the paper colour (cards are photos).

- [ ] **Step 4: Run to verify it passes and look at it**

Run: `docker compose run --rm api pytest tests/test_brand.py -q`
Expected: PASS.

Then start the dev stack (`docker compose up -d`), seed demo content
(`docker compose exec api python -m app.cli.seed_demo`), and take screenshots of `/`, `/markets`, an article page
and the admin dashboard, at 1280 px and 390 px. Check by eye that the orange carries roughly a quarter of the
accent weight and every label is readable.

- [ ] **Step 5: Commit**

```bash
git add -A apps
git commit -m "feat: 3Consulting orange (#ff914d) as the main accent, contrast-checked"
```

---

### Task 13: Server kit — Passenger entry, .htaccess, deploy script, crontab

**Files:**
- Create: `apps/api/passenger_wsgi.py`
- Create: `deploy/htaccess.public`, `deploy/htaccess.admin`, `deploy/deploy.sh`, `deploy/crontab.txt`, `deploy/env.example`, `deploy/test_htaccess.sh`, `deploy/apache-test.conf`
- Move: `infra/scripts/check_env.py` → `deploy/check_env.py`, `infra/scripts/test_check_env.py` → `deploy/test_check_env.py` (adapt keys)
- Test: `apps/api/tests/test_deploy_kit.py`

**Interfaces:**
- Consumes: `app.main.app`, `app.core.envfile.load_env`, `app.jobs.JOBS`.
- Produces:
  - `passenger_wsgi.application` (WSGI callable)
  - `deploy.sh` (idempotent)
  - cron lines (one per job)

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_deploy_kit.py`:

```python
import io
import os
import pathlib
import re
import runpy
from wsgiref.util import setup_testing_defaults

REPO = pathlib.Path(os.environ.get("ASI_REPO") or pathlib.Path(__file__).resolve().parents[3])
DEPLOY = REPO / "deploy"


def test_passenger_entry_serves_a_request_through_the_wsgi_adapter():
    module = runpy.run_path(str(REPO / "apps/api/passenger_wsgi.py"))
    application = module["application"]
    environ = {}
    setup_testing_defaults(environ)
    environ.update({"PATH_INFO": "/healthz", "REQUEST_METHOD": "GET", "HTTP_HOST": "testserver",
                    "wsgi.input": io.BytesIO(b"")})
    captured = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status

    body = b"".join(application(environ, start_response))
    assert captured["status"].startswith("200") and b'"database":true' in body.replace(b" ", b"")


def test_every_job_has_exactly_one_cron_line():
    from app.jobs import JOBS

    crontab = (DEPLOY / "crontab.txt").read_text(encoding="utf8")
    scheduled = re.findall(r"-m app\.jobs ([\w-]+)", crontab)
    expected = {name for name, job in JOBS.items() if job.every_minutes > 0}
    assert sorted(scheduled) == sorted(expected)


def test_daily_jobs_run_at_0200_and_0230_utc_on_a_sast_clock():
    crontab = (DEPLOY / "crontab.txt").read_text(encoding="utf8")
    assert re.search(r"^0 4 \* \* \* .*-m app\.jobs cleanup", crontab, re.M)
    assert re.search(r"^30 4 \* \* \* .*-m app\.jobs backup", crontab, re.M)


def test_public_htaccess_caches_only_safe_requests_and_hides_admin():
    rules = (DEPLOY / "htaccess.public").read_text(encoding="utf8")
    assert "RewriteCond %{QUERY_STRING} ^$" in rules
    assert "RewriteCond %{REQUEST_METHOD} ^(GET|HEAD)$" in rules
    assert re.search(r"RewriteRule \^admin\(/\|\$\) - \[R=404,L\]", rules)
    assert "X-ASI-Cache" in rules and "PassengerMaxPoolSize 3" in rules


def test_admin_htaccess_never_uses_the_page_cache():
    rules = (DEPLOY / "htaccess.admin").read_text(encoding="utf8")
    assert "_cache" not in rules and "noindex" in rules


def test_env_example_lists_every_production_setting():
    example = (DEPLOY / "env.example").read_text(encoding="utf8")
    for key in ("ENVIRONMENT", "SITE_URL", "ADMIN_URL", "DATABASE_URL", "JWT_SECRET", "TOTP_SECRET_KEY",
                "SMTP_HOST", "SMTP_PORT", "SMTP_SSL", "SMTP_USER", "SMTP_PASSWORD", "MAIL_MAX_PER_HOUR",
                "MEDIA_ROOT", "MEDIA_ORIGINALS_ROOT", "PAGE_CACHE_ROOT", "LIVE_JSON_PATH", "DATA_DIR",
                "ALERT_EMAIL_TO", "INDEXNOW_KEY"):
        assert re.search(rf"^{key}=", example, re.M), key
```

`passenger_wsgi.py` reads `ASI_ENV_FILE`. In the test, no `.env` exists at the default path, so the loader is a
no-op and the test environment's settings stand.

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_deploy_kit.py -q`
(The container sees the whole repository read-only at `/repo` through `ASI_REPO`, set up in Task 1.)
Expected: FAIL (files missing).

- [ ] **Step 3: Implement**

`apps/api/passenger_wsgi.py`:

```python
"""Passenger entry point (DirectAdmin → Setup Python App:
application root ~/asi/apps/api, startup file passenger_wsgi.py, entry point
`application`). Passenger speaks WSGI; FastAPI is ASGI — a2wsgi bridges them.
Lifespan events don't run under a2wsgi, which is fine: the app starts no
background work (cron does it)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from app.core.envfile import load_env  # noqa: E402

load_env(os.environ.get("ASI_ENV_FILE", os.path.expanduser("~/asi/.env")))

from a2wsgi import ASGIMiddleware  # noqa: E402

from app.main import app  # noqa: E402

application = ASGIMiddleware(app)
```

`deploy/htaccess.public`. `deploy.sh` installs this above the CloudLinux Passenger block, which Setup Python App
manages and `deploy.sh` preserves:

```apache
# ===== ASI public site (installed by deploy/deploy.sh — edit the copy in git, not this file) =====
Options -Indexes
AddDefaultCharset utf-8
AddType application/json .json
AddType application/xml .xml

<IfModule mod_passenger.c>
  PassengerMaxPoolSize 3
  PassengerMinInstances 1
  PassengerFriendlyErrorPages off
</IfModule>

RewriteEngine On

# HTTPS and the bare domain
RewriteCond %{HTTPS} !=on
RewriteCond %{HTTP:X-Forwarded-Proto} !=https
RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]
RewriteCond %{HTTP_HOST} ^www\.(.+)$ [NC]
RewriteRule ^ https://%1%{REQUEST_URI} [R=301,L]

# Dot-files, the subdomain folder and direct requests into the cache are not part of the site
RewriteRule (^|/)\. - [F,L]
RewriteRule ^admin(/|$) - [R=404,L]
RewriteCond %{ENV:REDIRECT_STATUS} ^$
RewriteRule ^_cache(/|$) - [R=404,L]

# Page cache: serve a saved page without starting Python
RewriteCond %{REQUEST_METHOD} ^(GET|HEAD)$
RewriteCond %{QUERY_STRING} ^$
RewriteCond %{DOCUMENT_ROOT}/_cache%{REQUEST_URI}/index.html -f
RewriteRule ^ _cache%{REQUEST_URI}/index.html [L,E=ASI_CACHE:1]
RewriteCond %{REQUEST_METHOD} ^(GET|HEAD)$
RewriteCond %{QUERY_STRING} ^$
RewriteCond %{DOCUMENT_ROOT}/_cache%{REQUEST_URI}/index.json -f
RewriteRule ^ _cache%{REQUEST_URI}/index.json [L,E=ASI_CACHE:1]
RewriteCond %{REQUEST_METHOD} ^(GET|HEAD)$
RewriteCond %{QUERY_STRING} ^$
RewriteCond %{DOCUMENT_ROOT}/_cache%{REQUEST_URI}/index.xml -f
RewriteRule ^ _cache%{REQUEST_URI}/index.xml [L,E=ASI_CACHE:1]
RewriteCond %{REQUEST_METHOD} ^(GET|HEAD)$
RewriteCond %{QUERY_STRING} ^$
RewriteCond %{DOCUMENT_ROOT}/_cache%{REQUEST_URI}/index.txt -f
RewriteRule ^ _cache%{REQUEST_URI}/index.txt [L,E=ASI_CACHE:1]

<IfModule mod_headers.c>
  Header always set X-ASI-Cache "file" env=REDIRECT_ASI_CACHE
  Header always set Cache-Control "public, max-age=60" env=REDIRECT_ASI_CACHE
  Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
  Header always set X-Content-Type-Options "nosniff"
  Header always set Referrer-Policy "strict-origin-when-cross-origin"
  <FilesMatch "^live\.json$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
</IfModule>

# Uploaded pictures and fingerprinted assets never change
<IfModule mod_expires.c>
  ExpiresActive On
  ExpiresByType image/webp "access plus 1 year"
  ExpiresByType image/jpeg "access plus 1 year"
  ExpiresByType image/png "access plus 1 year"
  ExpiresByType font/woff2 "access plus 1 year"
</IfModule>
# ===== end ASI =====
```

`deploy/htaccess.admin` (installed into `public_html/admin/.htaccess`, the admin subdomain's folder):

```apache
# ===== ASI admin panel (installed by deploy/deploy.sh) =====
Options -Indexes
RewriteEngine On
RewriteCond %{HTTPS} !=on
RewriteCond %{HTTP:X-Forwarded-Proto} !=https
RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]
RewriteRule (^|/)\. - [F,L]
<IfModule mod_headers.c>
  Header always set X-Robots-Tag "noindex, nofollow"
  Header always set X-Frame-Options "DENY"
  Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
</IfModule>
# Passenger directives (same application as the public site) are copied below by deploy.sh
# ===== end ASI =====
```

`deploy/deploy.sh`:

```bash
#!/usr/bin/env bash
# Deploys the latest `release` branch on the server. Safe to run again.
#   ~/asi/deploy/deploy.sh
set -euo pipefail

ASI_HOME="${ASI_HOME:-$HOME/asi}"
DOMAIN="${DOMAIN:-africastablecoinintelligence.com}"
PUBLIC="$HOME/domains/$DOMAIN/public_html"
ADMIN_DIR="$PUBLIC/admin"
VENV="${ASI_VENV:-$HOME/virtualenv/asi/apps/api/3.11}"
PY="$VENV/bin/python"
DATA="$HOME/asi-data"

step() { printf '\n==> %s\n' "$*"; }

step "Fetching the release branch"
git -C "$ASI_HOME" fetch --quiet origin release
git -C "$ASI_HOME" reset --hard --quiet origin/release

step "Checking settings"
"$PY" "$ASI_HOME/deploy/check_env.py" "$ASI_HOME/.env"

step "Installing Python packages (wheels only)"
"$PY" -m pip install --quiet --only-binary=:all: -r "$ASI_HOME/apps/api/requirements.txt"

step "Migrating the database"
(cd "$ASI_HOME/apps/api" && ASI_ENV_FILE="$ASI_HOME/.env" "$PY" -c \
  "import os; from app.core.envfile import load_env; load_env(os.environ['ASI_ENV_FILE']); \
from alembic.config import main; main(['upgrade', 'head'])")

step "Folders"
mkdir -p "$DATA/originals" "$DATA/backups" "$DATA/logs" "$PUBLIC/media" "$PUBLIC/_cache" "$ADMIN_DIR"

step "Static files"
link_or_copy() {  # $1 source dir, $2 target path
  rm -rf "$2"
  if ln -s "$1" "$2" 2>/dev/null && [ -e "$2/." ]; then echo "linked $2"; else rm -f "$2"; cp -R "$1" "$2"; echo "copied $2"; fi
}
link_or_copy "$ASI_HOME/apps/api/app/site/static" "$PUBLIC/static"
link_or_copy "$ASI_HOME/apps/admin/dist/assets" "$ADMIN_DIR/assets"

step "Web server rules"
install_rules() {  # $1 our rules file, $2 target .htaccess, $3 passenger block source (optional)
  local tmp; tmp="$(mktemp)"
  cat "$1" > "$tmp"
  if [ -n "${3:-}" ] && [ -f "$3" ]; then
    sed -n '/CLOUDLINUX PASSENGER CONFIGURATION BEGIN/,/CLOUDLINUX PASSENGER CONFIGURATION END/p' "$3" >> "$tmp"
  elif [ -f "$2" ]; then
    sed -n '/CLOUDLINUX PASSENGER CONFIGURATION BEGIN/,/CLOUDLINUX PASSENGER CONFIGURATION END/p' "$2" >> "$tmp"
  fi
  mv "$tmp" "$2"
  chmod 644 "$2"
}
install_rules "$ASI_HOME/deploy/htaccess.public" "$PUBLIC/.htaccess"
install_rules "$ASI_HOME/deploy/htaccess.admin" "$ADMIN_DIR/.htaccess" "$PUBLIC/.htaccess"
grep -q "CLOUDLINUX PASSENGER CONFIGURATION BEGIN" "$PUBLIC/.htaccess" \
  || { echo "!! The Passenger block is missing from $PUBLIC/.htaccess — create the app in Setup Python App first."; exit 1; }

step "Clearing the page cache"
find "$PUBLIC/_cache" -mindepth 1 -delete

step "Restarting the application"
mkdir -p "$ASI_HOME/apps/api/tmp" && touch "$ASI_HOME/apps/api/tmp/restart.txt"

step "Self-check"
(cd "$ASI_HOME/apps/api" && ASI_ENV_FILE="$ASI_HOME/.env" "$PY" -m app.jobs selfcheck) \
  || echo "!! Self-check reported problems (above). The site is deployed; fix these next."
```

`deploy/crontab.txt`:

```
# Paste into DirectAdmin → Cron Jobs (one line per entry). Server clock is SAST (UTC+2):
# the two daily jobs run at 04:00 / 04:30 server time = 02:00 / 02:30 UTC.
# PY = ~/virtualenv/asi/apps/api/3.11/bin/python   (adjust if Setup Python App shows another path)
* * * * *     cd ~/asi/apps/api && ~/virtualenv/asi/apps/api/3.11/bin/python -m app.jobs tick >> ~/asi-data/logs/tick.log 2>&1
*/5 * * * *   cd ~/asi/apps/api && ~/virtualenv/asi/apps/api/3.11/bin/python -m app.jobs newsletter >> ~/asi-data/logs/newsletter.log 2>&1
*/15 * * * *  cd ~/asi/apps/api && ~/virtualenv/asi/apps/api/3.11/bin/python -m app.jobs global-metrics >> ~/asi-data/logs/global-metrics.log 2>&1
2-59/15 * * * * cd ~/asi/apps/api && ~/virtualenv/asi/apps/api/3.11/bin/python -m app.jobs country-proxy >> ~/asi-data/logs/country-proxy.log 2>&1
7-59/15 * * * * cd ~/asi/apps/api && ~/virtualenv/asi/apps/api/3.11/bin/python -m app.jobs cross-check >> ~/asi-data/logs/cross-check.log 2>&1
20 */2 * * *  cd ~/asi/apps/api && ~/virtualenv/asi/apps/api/3.11/bin/python -m app.jobs ng-official-rate >> ~/asi-data/logs/ng-official-rate.log 2>&1
0 4 * * *     cd ~/asi/apps/api && ~/virtualenv/asi/apps/api/3.11/bin/python -m app.jobs cleanup >> ~/asi-data/logs/cleanup.log 2>&1
30 4 * * *    cd ~/asi/apps/api && ~/virtualenv/asi/apps/api/3.11/bin/python -m app.jobs backup >> ~/asi-data/logs/backup.log 2>&1
```

`deploy/env.example`:

```
# ~/asi/.env on the server — never commit the real file. deploy.sh checks it before every deploy.
# Generate secrets with: python3 -c "import secrets; print(secrets.token_urlsafe(48))"
ENVIRONMENT=production
SITE_URL=https://africastablecoinintelligence.com
ADMIN_URL=https://admin.africastablecoinintelligence.com
# DirectAdmin → MySQL Management: database africast_asi, user africast_asi
DATABASE_URL=mysql+pymysql://africast_asi:change-me@localhost:3306/africast_asi?charset=utf8mb4
JWT_SECRET=change-me-to-a-48-character-random-string
# Encrypts two-factor secrets. Set once; changing it means every admin re-enrols.
TOTP_SECRET_KEY=change-me-to-a-48-character-random-string
COOKIE_SECURE=true

# E-mail — DirectAdmin → E-mail Accounts (desk@ and newsletter@)
SMTP_HOST=mail.africastablecoinintelligence.com
SMTP_PORT=465
SMTP_SSL=true
SMTP_USER=desk@africastablecoinintelligence.com
SMTP_PASSWORD=change-me
TRANSACTIONAL_FROM_ADDRESS=Africa Stablecoin Intelligence <desk@africastablecoinintelligence.com>
NEWSLETTER_FROM_ADDRESS=Africa Stablecoin Intelligence <newsletter@africastablecoinintelligence.com>
# Ask WhoGoHost for the hourly sending limit and put it here.
MAIL_MAX_PER_HOUR=100
NEWSLETTER_BATCH_PAUSE=1.0
ALERT_EMAIL_TO=ops@africastablecoinintelligence.com

# Files (paths for user "africast")
MEDIA_ROOT=/home/africast/domains/africastablecoinintelligence.com/public_html/media
MEDIA_PUBLIC_BASE_URL=/media
MEDIA_ORIGINALS_ROOT=/home/africast/asi-data/originals
PAGE_CACHE_ROOT=/home/africast/domains/africastablecoinintelligence.com/public_html/_cache
LIVE_JSON_PATH=/home/africast/domains/africastablecoinintelligence.com/public_html/live.json
DATA_DIR=/home/africast/asi-data
ADMIN_DIST_DIR=/home/africast/asi/apps/admin/dist

# Search engines & analytics
GOOGLE_SITE_VERIFICATION=
BING_SITE_VERIFICATION=
INDEXNOW_KEY=
ANALYTICS_SCRIPT_URL=
ANALYTICS_DOMAIN=

# Market data keys
QUIDAX_API_KEY=
ETHERSCAN_API_KEY=
COINGECKO_DEMO_KEY=

SENTRY_DSN=
```

`deploy/check_env.py`: `git mv` from `infra/scripts/check_env.py`. Change `REQUIRED` to:

```
ENVIRONMENT, SITE_URL, ADMIN_URL, DATABASE_URL, JWT_SECRET, TOTP_SECRET_KEY, SMTP_HOST, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO, MEDIA_ROOT, MEDIA_ORIGINALS_ROOT, PAGE_CACHE_ROOT, LIVE_JSON_PATH, DATA_DIR
```

Change `SECRETS` to `{"JWT_SECRET": 32, "TOTP_SECRET_KEY": 32}`. Remove the Airflow Fernet check, and add:
- `DATABASE_URL` must start with `mysql+pymysql://` and its password must not be a placeholder
- `ENVIRONMENT` must equal `production`
- `SITE_URL` and `ADMIN_URL` must start with `https://`

Update `deploy/test_check_env.py` so it reads `deploy/env.example` and asserts that the example (placeholders) is
rejected, and that a filled copy passes.

`deploy/apache-test.conf` and `deploy/test_htaccess.sh` check the cache rules in real Apache (httpd 2.4, with no
Passenger and no network):

```apache
# deploy/apache-test.conf — loaded by test_htaccess.sh
ServerName localhost
Listen 8080
LoadModule rewrite_module modules/mod_rewrite.so
LoadModule headers_module modules/mod_headers.so
LoadModule expires_module modules/mod_expires.so
DocumentRoot "/srv/public_html"
<Directory "/srv/public_html">
  AllowOverride All
  Require all granted
</Directory>
```

```bash
#!/usr/bin/env bash
# Proves the .htaccess page-cache rules in real Apache 2.4: a cached page is
# served with X-ASI-Cache: file; a query string or a missing file is not.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
mkdir -p "$WORK/public_html/_cache/markets/story" "$WORK/public_html/admin"
cp "$HERE/htaccess.public" "$WORK/public_html/.htaccess"
# Over HTTP inside the test: neutralise the HTTPS redirect by faking the proxy header.
echo '<p>cached home</p>' > "$WORK/public_html/_cache/index.html"
echo '<p>cached story</p>' > "$WORK/public_html/_cache/markets/story/index.html"
echo 'fallthrough' > "$WORK/public_html/fallthrough.txt"
cid=$(docker run -d --rm -p 18080:8080 -v "$WORK/public_html:/srv/public_html:ro" \
      -v "$HERE/apache-test.conf:/usr/local/apache2/conf/extra/asi.conf:ro" httpd:2.4.62 \
      sh -c "echo 'Include conf/extra/asi.conf' >> conf/httpd.conf && httpd-foreground")
trap 'docker stop "$cid" >/dev/null; rm -rf "$WORK"' EXIT
sleep 2
H=(-s -D - -o /dev/null -H "X-Forwarded-Proto: https" -H "Host: asi.test")
curl "${H[@]}" http://localhost:18080/ | grep -qi '^x-asi-cache: file' || { echo "FAIL home not served from cache"; exit 1; }
curl "${H[@]}" http://localhost:18080/markets/story | grep -qi '^x-asi-cache: file' || { echo "FAIL story"; exit 1; }
if curl "${H[@]}" "http://localhost:18080/?country=NG" | grep -qi '^x-asi-cache'; then echo "FAIL query string cached"; exit 1; fi
curl "${H[@]}" http://localhost:18080/admin/ | grep -q '^HTTP/1.1 404' || { echo "FAIL /admin not 404"; exit 1; }
curl "${H[@]}" http://localhost:18080/_cache/index.html | grep -q '^HTTP/1.1 404' || { echo "FAIL direct _cache"; exit 1; }
echo "htaccess: all checks passed"
```

The `RewriteRule ^admin(/|$) - [R=404,L]` in the public file must apply to the public host only. On the server, the
admin host's own `.htaccess` (in `public_html/admin`) has `RewriteEngine On` without `RewriteOptions Inherit`, so
the parent's rewrite rules do not apply there. Note this in a comment in `htaccess.public`.

- [ ] **Step 4: Run to verify they pass**

Run: `docker compose run --rm api pytest tests/test_deploy_kit.py -q && bash deploy/test_htaccess.sh && python deploy/test_check_env.py`
Expected: PASS, "htaccess: all checks passed", check_env passes.

If Apache serves `/` without the cache header because `%{REQUEST_URI}` is `/` and the rewrite target becomes
`_cache//index.html`, add a dedicated root rule above the generic ones:

```apache
RewriteCond %{REQUEST_METHOD} ^(GET|HEAD)$
RewriteCond %{QUERY_STRING} ^$
RewriteCond %{DOCUMENT_ROOT}/_cache/index.html -f
RewriteRule ^$ _cache/index.html [L,E=ASI_CACHE:1]
```

Then re-run.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api deploy infra docker-compose.yml
git commit -m "feat: server kit — Passenger entry, .htaccess with page cache, deploy.sh, crontab"
```

---

### Task 14: CI, release branch, repository cleanup and documentation

**Files:**
- Modify: `.github/workflows/ci.yml` (replace)
- Delete: `infra/` (whole), `docs/design/plans/2026-10-08-*` stays (history), `apps/admin/Dockerfile` if present
- Modify: `Makefile`, `README.md`, `.env.example` (dev), `.gitignore` (`apps/admin/dist` stays ignored on `main`)
- Rewrite: `docs/DEPLOYMENT.md`, `docs/ARCHITECTURE.md`, `docs/LAUNCH_CHECKLIST.md`; update `docs/EDITORIAL_GUIDE.md` (newsletter queue, System health), `docs/reference/README.md`
- Modify: `docs/design/specs/2026-10-09-asi-shared-hosting-design.md` (record the small deviations listed in Step 4)

**Interfaces:**
- Produces: branch `release` = `main` + `apps/admin/dist`, force-updated by CI after green tests.

- [ ] **Step 1: Write the CI workflow**

`.github/workflows/ci.yml`:

```yaml
name: ci
on:
  push:
    branches: [main, shared-hosting]
  pull_request:

permissions:
  contents: write

jobs:
  api:
    runs-on: ubuntu-latest
    services:
      mariadb:
        image: mariadb:11.4
        env:
          MARIADB_ROOT_PASSWORD: root_dev_password
          MARIADB_DATABASE: asi_test
          MARIADB_USER: asi
          MARIADB_PASSWORD: asi_dev_password
        options: >-
          --health-cmd "healthcheck.sh --connect --innodb_initialized" --health-interval 5s --health-retries 30
        ports: ["3306:3306"]
    defaults:
      run:
        working-directory: apps/api
    env:
      TEST_DATABASE_URL: mysql+pymysql://asi:asi_dev_password@127.0.0.1:3306/asi_test?charset=utf8mb4
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - name: Runtime dependencies install from wheels only (as on the shared host)
        run: pip install --only-binary=:all: -r requirements.txt
      - run: pip install -r requirements-dev.txt
      - name: Server time zone like the host (SAST)
        run: mysql -h127.0.0.1 -uroot -proot_dev_password -e "SET GLOBAL time_zone = '+02:00'"
      - run: python -m pytest -q
      - name: Deploy kit checks
        working-directory: .
        run: python deploy/test_check_env.py && bash deploy/test_htaccess.sh

  admin:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/admin
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: {node-version: "20", cache: npm, cache-dependency-path: apps/admin/package-lock.json}
      - run: npm ci
      - run: npx vitest run
      - run: npm run build
        env: {VITE_SITE_URL: "https://africastablecoinintelligence.com"}
      - uses: actions/upload-artifact@v4
        with: {name: admin-dist, path: apps/admin/dist}

  release:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    needs: [api, admin]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with: {name: admin-dist, path: apps/admin/dist}
      - name: Publish the release branch (code + built admin panel)
        run: |
          git config user.name "asi-ci"
          git config user.email "ci@africastablecoinintelligence.com"
          git add -f apps/admin/dist
          git commit -m "release: ${GITHUB_SHA::7}"
          git push --force origin HEAD:release
```

The MariaDB service runs in UTC by default. The `SET GLOBAL time_zone` step makes new connections default to
+02:00, so the app's own `SET time_zone='+00:00'` is really exercised. The `mysql` client is preinstalled on
`ubuntu-latest`.

- [ ] **Step 2: Clean up the repository**

- `git rm -r infra` (prod compose, Caddy, backup container, old scripts; check_env moved in Task 13).
- `Makefile`: replace the targets with `up`, `down`, `logs`, `test` (`docker compose run --rm api pytest -q`),
  `test-admin`, `admin-dev`, `migrate` (`docker compose run --rm api alembic upgrade head`), `seed-demo`,
  `bootstrap-admin`, `check-deploy` (`python deploy/test_check_env.py && bash deploy/test_htaccess.sh`), and
  `help`. Remove `prod-*` targets.
- Root `.env.example` (dev): `DATABASE_URL=mysql+pymysql://asi:asi_dev_password@localhost:3306/asi?charset=utf8mb4`,
  SMTP to MailHog, `SITE_URL`, `ADMIN_URL`. Remove Postgres, Redis and Airflow lines.
- Grep for `postgres`, `redis`, `airflow`, `caddy`, `timescale` and `psycopg` across the repo (excluding
  `docs/design/` and `docs/reference/`), and fix or remove each mention.

- [ ] **Step 3: Documentation**

`docs/DEPLOYMENT.md`: rewrite as the numbered checklist from spec §6, each step naming the DirectAdmin screen. This
is the screen sequence from the user's screenshots:

1. **MySQL Management** → create database `asi` and user `asi` (DirectAdmin prefixes them `africast_`); note the
   password.
2. **E-mail Accounts** → create `desk@` and `newsletter@`; **E-mail Manager → MX/DNS**: check SPF, DKIM and DMARC
   records (give the three expected TXT records).
3. **Subdomain Management** → create `admin`; **SSL/TLS Certificates** → Let's Encrypt for the domain, `www` and
   `admin`.
4. **Terminal**:
   - generate a deploy key: `ssh-keygen -t ed25519 -f ~/.ssh/asi_deploy -N ""`, then add `~/.ssh/asi_deploy.pub`
     to GitHub → repo → Settings → Deploy keys (read-only)
   - `git clone -b release git@github.com:Chidi-3consulting/Africa_Stablecoin_Intelligence.git ~/asi`, with an
     `~/.ssh/config` entry pointing github.com at that key
5. `cp ~/asi/deploy/env.example ~/asi/.env`, fill it in, `chmod 600 ~/asi/.env`.
6. **Setup Python App** → Create application:
   - Python 3.11.16
   - application root `asi/apps/api`
   - URL: the domain root
   - startup file `passenger_wsgi.py`
   - entry point `application`
   - Passenger log `~/asi-data/logs/passenger.log`

   Note the virtual environment path it shows.
7. Terminal: `ASI_VENV=<that path> bash ~/asi/deploy/deploy.sh`.
8. `cd ~/asi/apps/api && <venv>/bin/python -m app.cli.bootstrap_admin` → sign in at `admin.` → set up two-factor.
9. **Cron Jobs** → add each line of `deploy/crontab.txt`.
10. Wait two minutes, then `python -m app.jobs selfcheck` → all PASS. Explain each line, and what to do when "page
    cache served by the web server" fails (the fallback still serves cached pages; open a WhoGoHost ticket asking
    whether mod_rewrite runs before Passenger).
11. Google Search Console and Bing Webmaster: verify (meta tag via `.env`), submit `/sitemap.xml` and
    `/news-sitemap.xml`. Set `INDEXNOW_KEY`.
12. Lighthouse on the home page (mobile).
13. Routine work:
    - deploying an update: push to `main`, wait for CI to go green, then run `deploy.sh`
    - restoring a backup: `gunzip -c ~/asi-data/backups/db-….sql.gz | mariadb -u… -p… africast_asi`
    - reading job logs

`docs/ARCHITECTURE.md`: replace the infrastructure sections with spec §2–§4 in prose:
- one app with two hosts
- the page cache and its purge map
- MariaDB conventions
- cron jobs
- the memory budget

Keep the "Key behaviours" list, updated: newsletter queued and capped, view beacon, jobs instead of loops, admin
host only.

`docs/LAUNCH_CHECKLIST.md`: the spec §9 acceptance criteria as tick boxes.

`docs/EDITORIAL_GUIDE.md`:
- Newsletter: "Send queues the issue; sending starts within 5 minutes and is spread to stay within the hourly limit."
- Add an "Admin → System health" paragraph.

`docs/reference/README.md`: add a paragraph, "The Docker/Postgres/Redis/Airflow/Caddy production setup (branch
`launch-build`, commit a883839) was replaced on 2026-10-09 because the only infrastructure available is WhoGoHost
shared hosting; see the shared-hosting spec."

`README.md`: the quick start becomes `docker compose up -d && make migrate && make test`, then `make admin-dev`. The
production section points to `docs/DEPLOYMENT.md`.

- [ ] **Step 4: Record deviations in the spec**

Append to the spec a "## 10. Implementation notes" section:
- `passenger_wsgi.py` lives in `apps/api/` (the application root), not `deploy/`.
- Search columns are `search_title` / `search_body`, folded in Python and holding the dek plus plain body text.
- `live.json` carries the same payload as `/api/v1/live` (server-computed "Delayed" flags, regenerated every
  minute), rather than the browser computing staleness.
- Media archives are weekly with 2 kept, because 14 daily media copies would not fit in 8 GB. Database dumps are
  daily with 14 kept.
- The views table keeps its existing name, `content_article_daily_views`.

- [ ] **Step 5: Verify and commit**

Run: `make test && make test-admin && make check-deploy`
Expected: all pass.

```bash
git add -A
git commit -m "chore: CI with MariaDB and release branch; remove Docker production stack; docs for shared hosting"
```

---

### Task 15: Final verification

**Files:** none new (fixes only, if verification finds problems).

- [ ] **Step 1: Full local run**

Run:
- `docker compose down -v && docker compose up -d && make migrate && make test`
- `cd apps/admin && npx vitest run && npm run build`
- `make check-deploy`

Expected: all green on a fresh database.

- [ ] **Step 2: The app under the WSGI adapter, as Passenger will run it**

Run inside the api container:

```bash
docker compose run --rm -p 8001:8001 api python -c "
from wsgiref.simple_server import make_server
import runpy
app = runpy.run_path('passenger_wsgi.py')['application']
make_server('0.0.0.0', 8001, app).serve_forever()"
```

Then from the host: `curl -s localhost:8001/healthz`, `curl -s localhost:8001/ | head -5`, and
`curl -s localhost:8001/api/v1/home | head -c 300`.
Expected: 200 responses with real content.

- [ ] **Step 3: Jobs end to end against the dev database**

Run:

```bash
docker compose exec api python -m app.cli.seed_demo
docker compose exec -e LIVE_JSON_PATH=/tmp/live.json -e PAGE_CACHE_ROOT=/tmp/cache api python -m app.jobs tick
docker compose exec api python -m app.jobs global-metrics
docker compose exec api python -m app.jobs cross-check
docker compose exec api python -m app.jobs cleanup
```

Expected: each prints `ok`. `global-metrics` needs internet access; if offline it prints `failed` with a network
error, which is the correct behaviour.

- [ ] **Step 4: Memory sanity check**

Run: `docker stats --no-stream` while requesting `/`, an article and the admin dashboard 50 times
(`for i in $(seq 50); do curl -s -o /dev/null localhost:8000/; done`).
Expected: the API container stays well under 300 MB.

- [ ] **Step 5: Whole-branch review and hand-off**

Run the final code review (per the execution method), fix what it finds, re-run Step 1, and commit. Then report:
- what was verified locally
- what can only be verified on the host: `selfcheck`, the cache-file header, two hosts sharing one Passenger app,
  and the mail limit
- the deployment checklist location

---

## Self-review notes (for the plan author)

- **Spec coverage:**
  - §2.1 runtime/hosts → T7, T13
  - §2.2 page cache → T8
  - §2.3 layout → T13
  - §3 MariaDB → T1–T6
  - §3.3 Redis → T2, T6
  - §4 cron → T9, T10
  - §5 admin build/deps/pictures/email → T5, T11, T14
  - §5a brand → T12
  - §6 deploy/ops/selfcheck/docs → T9, T13, T14
  - §7 testing → every task
  - §8 risks → selfcheck (T9), deploy.sh fallbacks (T13)
  - §9 acceptance → T14 checklist, T15
- **Interfaces used across tasks:**
  - `invalidate_public` (T2 → T8)
  - `live.payload` (T4 → T9)
  - `send_pending` (T5 → T9)
  - `named_lock` (T1 → T5, T9)
  - `article_changed`/`site_changed` (T8)
  - `JOBS`/`Job` (T9 → T10, T13)
  - `JOB_INTERVALS` (T9 → T11)
