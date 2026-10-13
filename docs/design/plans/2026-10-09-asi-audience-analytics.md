# ASI Audience Analytics Implementation Plan

**Goal:** Count ASI's audience anonymously on every public page, write fine-grained daily fact files each night, and
serve them to Power BI Desktop through secure download addresses.

**Architecture:**
- **Counting:** a first-party beacon from `site.js` posts to `/api/v1/views`. The server derives country (offline
  GeoIP), source and device, then upserts a daily aggregate row; the IP is never stored.
- **Daily files:** a nightly `analytics-export` job writes immutable per-day CSVs and current dimension snapshots
  under `DATA_DIR/exports`.
- **Delivery:** `/admin/exports/*.csv` on the admin host streams them to Power BI. Access is by Basic sign-in with
  revocable export keys.

**Tech Stack:** FastAPI, SQLAlchemy Core (MariaDB 11.4), `maxminddb`, the existing `app.jobs` runner, React admin
(vitest), plain-JS `site.js`.

**Spec:** `docs/design/specs/2026-10-09-asi-audience-analytics-design.md`

## Global Constraints

- **No personal data:** no IP address, user agent, persistent identifier or e-mail is stored, logged or exported. This
  includes rate-limit buckets, which are stored hashed (Task 3).
- **Times:** UTC days everywhere (`UTC_DATE()` in SQL, `datetime.now(timezone.utc).date()` in Python).
- **SQL:** MariaDB dialect only. `tests/test_dialect.py` must stay green. Write the column `key` as `` `key` ``.
- **Packages:** wheels only. `maxminddb==2.6.2` is the only new runtime package.
- **Fact files:** `<DATA_DIR>/exports/<table>/<YYYY-MM-DD>.csv`, UTF-8, header row, comma separated, ISO dates. Write
  `.partial`, then rename. Never rewrite an existing day except through `--rebuild`.
- **Dimension files:** `<DATA_DIR>/exports/<dim>.csv`, rewritten every run.
- **Export addresses:** admin host only; `Cache-Control: no-store`; `X-Robots-Tag: noindex`.
- **Export keys:**
  - 40+ random characters, stored as SHA-256 hashes
  - valid only on `/admin/exports*`
  - 120 requests per key per hour
- **Beacon endpoint:** always answers `204`; at most 120 pings per address per hour.
- **Visitor flags:** `asi-v-day` and `asi-v-last` (UTC `YYYY-MM-DD`). Never read or written under Global Privacy
  Control, `doNotTrack === "1"`, or `ANALYTICS_VISITOR_FLAGS=off`.
- **Commits:** on branch `shared-hosting`, one or more per task.
- **Tests:** run in Docker: `docker compose run --rm api pytest -o addopts= -q -p no:cacheprovider …`;
  `cd apps/admin && npx vitest run`.

## Review Focus

1. **Rate-limit buckets would keep raw IPs.** The beacon's `views:<ip>` bucket and the login and subscribe buckets must
   not store addresses. Pinned by `test_rate_limit_buckets_never_store_addresses` (Task 3).
2. **Pages cached before the deploy still send the old `{"slug": …}` ping.** It must be ignored quietly (204, no row,
   no error). Pinned by `test_old_slug_ping_is_ignored` (Task 3).
3. **A story renamed after it was read.** Older traffic rows keep the old path but must still join to the story.
   Pinned by `test_story_rows_carry_the_story_id` (Task 3).
4. **A day with no traffic, or no files yet.** Power BI must still get a well-formed CSV with a header. Pinned by
   `test_empty_day_still_gets_a_file_with_a_header` and `test_stream_with_no_files_is_header_only` (Tasks 5, 6).
5. **The UTC day boundary.** A ping at 23:59 UTC belongs to that day's file, not the next. Pinned by
   `test_export_writes_only_that_days_rows` (Task 5).

---

## File Structure

| Path | Responsibility | Task |
|---|---|---|
| `apps/api/alembic/versions/0002_audience_analytics.py` | Tables: `analytics_traffic_daily`, `analytics_errors_daily`, `analytics_countries`, `ops_export_keys`; `newsletter_deliveries.failed_at` | 1 |
| `apps/api/app/core/settings.py` | `ANALYTICS_START`, `ANALYTICS_VISITOR_FLAGS`, `GEOIP_PATH`, `EXPORTS_DIR` | 1 |
| `apps/api/app/services/audience.py` | Pure classification (source, device, path) and recording (page view, error) | 1, 3, 4 |
| `apps/api/app/services/geo.py` | Offline GeoIP lookup behind `lookup(ip) -> Country` | 2 |
| `apps/api/app/jobs/geoip.py` | `geoip-update` job | 2 |
| `apps/api/app/api/public/views.py` | Beacon endpoint (rewritten) | 3 |
| `apps/api/app/services/views.py` | Removed; its "Most read" upsert moves to `audience.py` | 3 |
| `apps/api/app/core/rate_limit.py` | Hashed buckets | 3 |
| `apps/api/app/site/static/js/site.js`, `templates/base.html`, `site/context.py` | Beacon on every page, visitor flags | 3 |
| `apps/api/app/services/newsletter.py` | `#from=newsletter` marker; `failed_at` | 3, 5 |
| `apps/api/app/core/middleware.py` | Error counting | 4 |
| `apps/api/app/jobs/analytics.py` | `analytics-export` job: facts, dimensions, meta, fill, rebuild, prune | 5 |
| `apps/api/app/jobs/{__init__,__main__,runner,selfcheck,tasks}.py` | Register jobs, `--rebuild`, self-check lines, exports in backup | 2, 5 |
| `apps/api/app/api/admin/exports.py` | `/admin/exports*` streaming, export keys API | 6 |
| `apps/admin/src/pages/DataExports.jsx`, `exportRules.js` | Admin page | 6 |
| `deploy/crontab.txt`, `deploy/deploy.sh`, `deploy/env.example` | Cron lines, first GeoIP fetch, settings | 2, 5, 7 |
| `docs/POWER_BI.md`, `docs/DEPLOYMENT.md`, `docs/LAUNCH_CHECKLIST.md`, `docs/ARCHITECTURE.md` | Analyst guide and ops docs | 7 |

---

### Task 1: Schema, settings and classification

**Files:**
- Create: `apps/api/alembic/versions/0002_audience_analytics.py`, `apps/api/app/services/audience.py`
- Modify: `apps/api/app/core/settings.py`
- Test: `apps/api/tests/test_audience_classify.py`

**Interfaces:**
- Produces:
  - `audience.classify_source(ref: str | None, from_marker: str | None, site_host: str) -> tuple[str, str]`, which
    returns `(source, source_domain)`
  - `audience.classify_device(user_agent: str) -> str`
  - `audience.classify_path(path: str) -> tuple[str, str | None] | None`, which returns `(page_type, story_slug)` or
    `None`
  - `audience.SOURCES: tuple[tuple[str, str, str], ...]`
  - settings `ANALYTICS_START: date`, `ANALYTICS_VISITOR_FLAGS: bool`, `GEOIP_PATH: str`, `EXPORTS_DIR: str`
  - tables as listed under File Structure

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_audience_classify.py`:

```python
import pytest
from sqlalchemy import text

from app.services import audience

SITE = "africastablecoinintelligence.com"


@pytest.mark.parametrize("ref, marker, expected", [
    ("", None, ("direct", "")),
    (None, None, ("direct", "")),
    ("https://africastablecoinintelligence.com/markets", None, ("internal", "")),
    ("https://www.google.com/", None, ("search", "google.com")),
    ("https://www.google.com.ng/", None, ("search", "google.com.ng")),
    ("https://news.google.com/articles/x", None, ("search", "news.google.com")),
    ("https://www.bing.com/search?q=x", None, ("search", "bing.com")),
    ("https://duckduckgo.com/", None, ("search", "duckduckgo.com")),
    ("https://t.co/abc", None, ("social", "t.co")),
    ("https://lnkd.in/xyz", None, ("social", "lnkd.in")),
    ("https://l.facebook.com/l.php?u=x", None, ("social", "l.facebook.com")),
    ("https://www.linkedin.com/feed/", None, ("social", "linkedin.com")),
    ("https://web.whatsapp.com/", None, ("social", "web.whatsapp.com")),
    ("https://techcabal.com/2026/10/x", None, ("referral", "techcabal.com")),
    ("http://203.0.113.9:8080/page", None, ("referral", "(ip address)")),
    ("https://www.google.com/", "newsletter", ("newsletter", "")),
    ("not a url", None, ("referral", "(unknown)")),
])
def test_sources(ref, marker, expected):
    assert audience.classify_source(ref, marker, SITE) == expected


@pytest.mark.parametrize("ua, device", [
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148", "mobile"),
    ("Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile Safari/537.36", "mobile"),
    ("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X)", "tablet"),
    ("Mozilla/5.0 (Linux; Android 13; SM-X700) Safari/537.36", "tablet"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36", "desktop"),
])
def test_devices(ua, device):
    assert audience.classify_device(ua) == device


@pytest.mark.parametrize("path, expected", [
    ("/", ("home", None)),
    ("/markets", ("section", None)),
    ("/regulation/kenya-vasp-act", ("story", "kenya-vasp-act")),
    ("/countries", ("page", None)),
    ("/countries/nigeria", ("country", None)),
    ("/authors/ada-obi", ("author", None)),
    ("/newsletter", ("newsletter", None)),
    ("/newsletter/issues/12-weekly", ("newsletter", None)),
    ("/privacy", ("page", None)),
    ("/search", None),
    ("/admin/me", None),
    ("/markets/../etc", None),
    ("/wp-login.php", None),
])
def test_paths(path, expected):
    assert audience.classify_path(path) == expected


def test_tables_exist(db_session):
    names = {r[0] for r in db_session.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE()"))}
    assert {"analytics_traffic_daily", "analytics_errors_daily", "analytics_countries", "ops_export_keys"} <= names
    cols = {r[0] for r in db_session.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = DATABASE() "
        "AND table_name = 'newsletter_deliveries'"))}
    assert "failed_at" in cols
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_audience_classify.py -o addopts= -q -p no:cacheprovider`
Expected: FAIL (`app.services.audience` missing).

- [ ] **Step 3: Implement**

`apps/api/alembic/versions/0002_audience_analytics.py`:

```python
"""Audience analytics: daily traffic and error counts, countries seen, export keys;
newsletter delivery failure time.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-09
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OPTS = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci"
NOW = "DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)"

STATEMENTS = [
    f"""CREATE TABLE analytics_traffic_daily (
      day DATE NOT NULL,
      path VARCHAR(300) NOT NULL,
      page_type VARCHAR(12) NOT NULL,
      article_id INT UNSIGNED NULL,
      country_code VARCHAR(2) NOT NULL,
      source VARCHAR(10) NOT NULL,
      source_domain VARCHAR(100) NOT NULL DEFAULT '',
      device VARCHAR(8) NOT NULL,
      views INT UNSIGNED NOT NULL DEFAULT 0,
      visitors INT UNSIGNED NOT NULL DEFAULT 0,
      new_visitors INT UNSIGNED NOT NULL DEFAULT 0,
      returning_visitors INT UNSIGNED NOT NULL DEFAULT 0,
      PRIMARY KEY (day, path, country_code, source, source_domain, device),
      KEY traffic_day_idx (day)
    ) {OPTS}""",
    f"""CREATE TABLE analytics_errors_daily (
      day DATE NOT NULL,
      path VARCHAR(300) NOT NULL,
      status SMALLINT UNSIGNED NOT NULL,
      hits INT UNSIGNED NOT NULL DEFAULT 0,
      PRIMARY KEY (day, path, status)
    ) {OPTS}""",
    f"""CREATE TABLE analytics_countries (
      code VARCHAR(2) PRIMARY KEY,
      name VARCHAR(100) NOT NULL,
      continent VARCHAR(2) NULL,
      first_seen DATE NOT NULL
    ) {OPTS}""",
    f"""CREATE TABLE ops_export_keys (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      label VARCHAR(100) NOT NULL,
      key_hash VARCHAR(64) NOT NULL,
      created_by INT UNSIGNED NULL,
      created_at {NOW},
      last_used_at DATETIME(6) NULL,
      revoked_at DATETIME(6) NULL,
      UNIQUE KEY export_keys_hash_uq (key_hash),
      CONSTRAINT export_keys_user_fk FOREIGN KEY (created_by) REFERENCES auth_users(id) ON DELETE SET NULL
    ) {OPTS}""",
    "ALTER TABLE newsletter_deliveries ADD COLUMN failed_at DATETIME(6) NULL AFTER sent_at",
]


def upgrade() -> None:
    bind = op.get_bind()
    for statement in STATEMENTS:
        bind.execute(text(statement))


def downgrade() -> None:
    raise NotImplementedError("Forward-only.")
```

Append to `apps/api/app/core/settings.py`, after the jobs block:

```python
# Audience analytics (docs/design/specs/2026-10-09-asi-audience-analytics-design.md).
from datetime import date as _date  # noqa: E402

ANALYTICS_START = _date.fromisoformat(os.environ.get("ANALYTICS_START", "2026-10-01"))
ANALYTICS_VISITOR_FLAGS = os.environ.get("ANALYTICS_VISITOR_FLAGS", "on").lower() != "off"
GEOIP_PATH = os.environ.get("GEOIP_PATH", os.path.join(DATA_DIR, "geoip", "dbip-country-lite.mmdb"))
EXPORTS_DIR = os.environ.get("EXPORTS_DIR", os.path.join(DATA_DIR, "exports"))
```

`apps/api/app/services/audience.py`:

```python
"""Audience counting: what a page view is (path, source, device) — pure
functions — plus the recording functions added in Tasks 3 and 4. Nothing here
ever stores an IP address, a user agent or an identifier."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

SOURCES = (
    ("direct", "Direct", "No referrer: typed, bookmarked, or an app that hides it"),
    ("internal", "Internal", "Another ASI page"),
    ("search", "Search", "A search engine"),
    ("social", "Social", "A social network or messaging app"),
    ("newsletter", "Newsletter", "A link in an ASI newsletter issue"),
    ("referral", "Referral", "Any other website"),
)
_SEARCH = re.compile(r"(^|\.)(google|yahoo|yandex)\.[a-z.]+$|(^|\.)(bing\.com|duckduckgo\.com|ecosia\.org|baidu\.com)$")
_SOCIAL = ("facebook.com", "instagram.com", "linkedin.com", "lnkd.in", "x.com", "twitter.com", "t.co",
           "whatsapp.com", "wa.me", "t.me", "telegram.org", "reddit.com", "youtube.com", "tiktok.com")
_STORY = re.compile(r"^/(markets|regulation)/([a-z0-9]+(?:-[a-z0-9]+)*)$")
_PAGES = (
    (re.compile(r"^/$"), "home"),
    (re.compile(r"^/(markets|regulation)$"), "section"),
    (re.compile(r"^/countries$"), "page"),
    (re.compile(r"^/countries/[a-z0-9-]+$"), "country"),
    (re.compile(r"^/authors/[a-z0-9-]+$"), "author"),
    (re.compile(r"^/newsletter$"), "newsletter"),
    (re.compile(r"^/newsletter/issues/[a-z0-9-]+$"), "newsletter"),
    (re.compile(r"^/(about|methodology|editorial-policy|corrections|privacy|terms)$"), "page"),
)


def _host(ref: str) -> str | None:
    try:
        host = (urlparse(ref).hostname or "").lower()
    except ValueError:
        return None
    return host[4:] if host.startswith("www.") else host or None


def classify_source(ref: str | None, from_marker: str | None, site_host: str) -> tuple[str, str]:
    if from_marker == "newsletter":
        return "newsletter", ""
    if not ref:
        return "direct", ""
    host = _host(ref)
    if host is None:
        return "referral", "(unknown)"
    site = site_host.lower().removeprefix("www.")
    if host == site:
        return "internal", ""
    try:
        ipaddress.ip_address(host)
        return "referral", "(ip address)"  # never keep an address, even a website's
    except ValueError:
        pass
    if _SEARCH.search(host):
        return "search", host[:100]
    if any(host == d or host.endswith("." + d) for d in _SOCIAL):
        return "social", host[:100]
    return "referral", host[:100]


def classify_device(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        return "tablet"
    if "mobi" in ua or "iphone" in ua or "android" in ua:
        return "mobile"
    return "desktop"


def classify_path(path: str) -> tuple[str, str | None] | None:
    if not path or len(path) > 300 or ".." in path:
        return None
    story = _STORY.match(path)
    if story:
        return "story", story.group(2)
    for pattern, page_type in _PAGES:
        if pattern.match(path):
            return page_type, None
    return None
```

- [ ] **Step 4: Run to verify they pass**

Run: `docker compose run --rm api pytest tests/test_audience_classify.py tests/test_dialect.py -o addopts= -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/alembic/versions/0002_audience_analytics.py apps/api/app/services/audience.py apps/api/app/core/settings.py apps/api/tests/test_audience_classify.py
git commit -m "feat: audience analytics schema and page/source/device classification"
```

---

### Task 2: Offline GeoIP lookup and its monthly update job

**Files:**
- Create: `apps/api/app/services/geo.py`, `apps/api/app/jobs/geoip.py`
- Modify: `apps/api/requirements.txt` (`maxminddb==2.6.2`), `apps/api/app/jobs/__init__.py`, `apps/api/app/jobs/selfcheck.py`, `deploy/crontab.txt`
- Test: `apps/api/tests/test_geo.py`

**Interfaces:**
- Produces:
  - `geo.Country(code: str, name: str | None, continent: str | None)` (a NamedTuple)
  - `geo.lookup(ip: str) -> geo.Country`, which never raises and gives `Country("ZZ", None, None)` when unknown
  - `geo.reset() -> None`, which drops the cached reader
  - job `geoip-update` (`every_minutes=44640`)
  - `geoip.update(db, deadline, get=requests.get, verify=None, now=None) -> str`
  - self-check rows "GeoIP file present and recent", and "cron ran recently: geoip-update" via
    `JOB_INTERVALS["geoip-update"] = 44640`

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_geo.py`:

```python
import gzip
from datetime import datetime, timezone

import pytest

from app.services import geo


class FakeReader:
    def __init__(self, records):
        self.records = records

    def get(self, ip):
        if ip == "bad":
            raise ValueError("not an address")
        return self.records.get(ip)


def test_lookup_returns_code_name_and_continent(monkeypatch):
    monkeypatch.setattr(geo, "_reader", FakeReader(
        {"102.89.1.1": {"country": {"iso_code": "NG", "names": {"en": "Nigeria"}}, "continent": {"code": "AF"}}}))
    monkeypatch.setattr(geo, "_opened", True)
    assert geo.lookup("102.89.1.1") == geo.Country("NG", "Nigeria", "AF")


def test_unknown_private_or_bad_addresses_are_ZZ(monkeypatch):
    monkeypatch.setattr(geo, "_reader", FakeReader({}))
    monkeypatch.setattr(geo, "_opened", True)
    assert geo.lookup("10.0.0.1").code == "ZZ"
    assert geo.lookup("bad").code == "ZZ"


def test_missing_database_file_is_ZZ_not_an_error(monkeypatch, tmp_path):
    geo.reset()
    monkeypatch.setattr(geo, "GEOIP_PATH", str(tmp_path / "missing.mmdb"))
    assert geo.lookup("102.89.1.1").code == "ZZ"
    geo.reset()


class FakeResponse:
    def __init__(self, status, body=b""):
        self.status_code, self.content = status, body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_update_downloads_the_current_month_and_swaps_atomically(tmp_path, monkeypatch):
    from app.jobs import geoip

    target = tmp_path / "geoip" / "dbip-country-lite.mmdb"
    monkeypatch.setattr(geoip, "GEOIP_PATH", str(target))
    urls = []

    def get(url, timeout):
        urls.append(url)
        return FakeResponse(200, gzip.compress(b"MMDB-BYTES"))

    detail = geoip.update(None, None, get=get, verify=lambda path: None,
                          now=datetime(2026, 10, 9, tzinfo=timezone.utc))
    assert urls[0].endswith("dbip-country-lite-2026-10.mmdb.gz")
    assert target.read_bytes() == b"MMDB-BYTES" and "2026-10" in detail


def test_update_falls_back_to_last_month_early_in_the_month(tmp_path, monkeypatch):
    from app.jobs import geoip

    monkeypatch.setattr(geoip, "GEOIP_PATH", str(tmp_path / "db.mmdb"))

    def get(url, timeout):
        return FakeResponse(404) if url.endswith("2026-10.mmdb.gz") else FakeResponse(200, gzip.compress(b"OLD"))

    assert "2026-09" in geoip.update(None, None, get=get, verify=lambda p: None,
                                     now=datetime(2026, 10, 1, tzinfo=timezone.utc))


def test_a_corrupt_download_keeps_the_old_file(tmp_path, monkeypatch):
    from app.jobs import geoip

    target = tmp_path / "db.mmdb"
    target.write_bytes(b"GOOD")
    monkeypatch.setattr(geoip, "GEOIP_PATH", str(target))

    def verify(path):
        raise ValueError("not a MaxMind DB")

    with pytest.raises(RuntimeError):
        geoip.update(None, None, get=lambda url, timeout: FakeResponse(200, gzip.compress(b"JUNK")), verify=verify,
                     now=datetime(2026, 10, 9, tzinfo=timezone.utc))
    assert target.read_bytes() == b"GOOD"


def test_selfcheck_reports_the_geoip_file(db_session, tmp_path, monkeypatch):
    from app.jobs import selfcheck

    monkeypatch.setattr(selfcheck, "GEOIP_PATH", str(tmp_path / "none.mmdb"))
    rows = {r["check"]: r for r in selfcheck.run_checks(
        db_session, http_get=lambda url: (200, {"x-asi-instance": "a", "x-asi-cache": "file"}), smtp=False)}
    assert rows["GeoIP file present and recent"]["ok"] is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_geo.py -o addopts= -q -p no:cacheprovider`
Expected: FAIL (`app.services.geo` missing).

- [ ] **Step 3: Implement**

`requirements.txt`: add `maxminddb==2.6.2`. Rebuild the dev image: `docker compose build api`. Confirm a host wheel
exists:
`docker compose run --rm api pip download -q --only-binary=:all: --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 --implementation cp --python-version 3.11 -d /tmp/w maxminddb==2.6.2`.

`apps/api/app/services/geo.py`:

```python
"""Country from an IP address, using the offline DB-IP Lite file (CC BY 4.0,
"IP geolocation by DB-IP"). The address is used for the lookup only and is
never stored. A missing or unreadable file means "ZZ" (unknown), never an error."""

from __future__ import annotations

import ipaddress
import os
from typing import NamedTuple

from app.core.settings import GEOIP_PATH


class Country(NamedTuple):
    code: str
    name: str | None
    continent: str | None


UNKNOWN = Country("ZZ", None, None)
_reader = None
_opened = False


def reset() -> None:
    global _reader, _opened
    if _reader is not None and hasattr(_reader, "close"):
        _reader.close()
    _reader, _opened = None, False


def _open():
    global _reader, _opened
    _opened = True
    if not os.path.exists(GEOIP_PATH):
        return None
    try:
        import maxminddb

        _reader = maxminddb.open_database(GEOIP_PATH, maxminddb.MODE_MMAP)
    except Exception as exc:  # noqa: BLE001 — counting must never fail over the geo file
        print(f"[geo] could not open {GEOIP_PATH}: {exc}")
        _reader = None
    return _reader


def lookup(ip: str) -> Country:
    reader = _reader if _opened else _open()
    if reader is None:
        return UNKNOWN
    try:
        if ipaddress.ip_address(ip).is_private:
            return UNKNOWN
        record = reader.get(ip) or {}
    except (ValueError, TypeError):
        return UNKNOWN
    country = record.get("country") or {}
    code = (country.get("iso_code") or "").upper()
    if len(code) != 2:
        return UNKNOWN
    return Country(code, (country.get("names") or {}).get("en"), (record.get("continent") or {}).get("code"))
```

The `bad` address case: `ipaddress.ip_address("bad")` raises `ValueError` before the reader is called. Both paths
end as `UNKNOWN`.

`apps/api/app/jobs/geoip.py`:

```python
"""geoip-update job: monthly download of the free DB-IP Lite country file.
DB-IP publishes each month's file early in the month, so the previous month
is tried when this month's isn't out yet. The new file is checked before it
replaces the old one; a bad download keeps the old file and fails the run."""

from __future__ import annotations

import gzip
import os
from datetime import datetime, timezone

import requests

from app.core.settings import GEOIP_PATH
from app.services import geo

URL = "https://download.db-ip.com/free/dbip-country-lite-{month}.mmdb.gz"


def _months(now: datetime) -> list[str]:
    this = now.strftime("%Y-%m")
    year, month = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    return [this, f"{year:04d}-{month:02d}"]


def _verify(path: str) -> None:
    import maxminddb

    maxminddb.open_database(path, maxminddb.MODE_FILE).close()


def update(db, deadline, get=requests.get, verify=None, now=None) -> str:
    verify = verify or _verify
    now = now or datetime.now(timezone.utc)
    os.makedirs(os.path.dirname(GEOIP_PATH), exist_ok=True)
    last_error = None
    for month in _months(now):
        response = get(URL.format(month=month), timeout=60)
        if response.status_code == 404:
            last_error = f"{month} not published yet"
            continue
        response.raise_for_status()
        partial = GEOIP_PATH + ".partial"
        try:
            with open(partial, "wb") as out:
                out.write(gzip.decompress(response.content))
            verify(partial)
        except Exception as exc:  # noqa: BLE001
            if os.path.exists(partial):
                os.unlink(partial)
            raise RuntimeError(f"geoip-update: the {month} download is not a usable database ({exc}); "
                               "kept the previous file") from exc
        os.replace(partial, GEOIP_PATH)
        geo.reset()
        return f"GeoIP database {month} installed"
    raise RuntimeError(f"geoip-update: no file available ({last_error})")
```

Register it in `apps/api/app/jobs/__init__.py`:

```python
from app.jobs import geoip as _geoip
...
JOBS["geoip-update"] = Job("geoip-update", _geoip.update, 44640)
```

In `apps/api/app/jobs/selfcheck.py`:
- Import `GEOIP_PATH` from `app.core.settings` and `time`.
- Add `"geoip-update": 44640` to `JOB_INTERVALS`.
- In `run_checks`, before the SMTP block, add:

```python
    fresh = os.path.exists(GEOIP_PATH) and (time.time() - os.path.getmtime(GEOIP_PATH)) < 60 * 86400
    add("GeoIP file present and recent", fresh, GEOIP_PATH if fresh else f"{GEOIP_PATH} missing or older than 60 days")
```

In `deploy/crontab.txt`, add (05:00 server time, 03:00 UTC, on the 3rd of each month):

```
0 5 3 * *     cd ~/asi/apps/api && ~/virtualenv/asi/apps/api/3.11/bin/python -m app.jobs geoip-update >> ~/asi-data/logs/cron-output.log 2>&1
```

- [ ] **Step 4: Run to verify they pass**

Run: `docker compose run --rm api pytest tests/test_geo.py tests/test_deploy_kit.py tests/test_jobs.py -o addopts= -q -p no:cacheprovider`
Expected: PASS. `test_every_job_has_exactly_one_cron_line` stays green.

- [ ] **Step 5: Commit**

```bash
git add apps/api deploy/crontab.txt
git commit -m "feat: offline GeoIP country lookup with monthly DB-IP Lite update"
```

---

### Task 3: The beacon on every page

**Files:**
- Modify:
  - `apps/api/app/services/audience.py` (adds `record_page_view`)
  - `apps/api/app/api/public/views.py` (rewrite)
  - `apps/api/app/core/rate_limit.py`
  - `apps/api/app/site/static/js/site.js`
  - `apps/api/app/site/templates/base.html`
  - `apps/api/app/site/context.py`
  - `apps/api/app/site/templates/article.html` (drop `data-view-slug`)
  - `apps/api/app/services/newsletter.py` (link marker)
- Delete: `apps/api/app/services/views.py`
- Test:
  - `apps/api/tests/test_audience_beacon.py`
  - `apps/admin/src/__tests__/siteBeacon.test.js`
  - replaces `apps/api/tests/test_views.py`

**Interfaces:**
- Consumes: Task 1 classification and tables; Task 2 `geo.lookup`.
- Produces:
  - `audience.record_page_view(db, *, path, ref, from_marker, first_today, visitor, ip, user_agent, site_host) -> bool`
  - `window.ASI.beaconPayload(loc, referrer, nav, storage, today, flagsAllowed) -> object`
  - `newsletter.mark_links(html: str) -> str`

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_audience_beacon.py`:

```python
from sqlalchemy import text

from app.services import geo

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0"


def _ping(client, body, ip="203.0.113.77", ua=UA):
    import json

    return client.post("/api/v1/views", content=json.dumps(body),
                       headers={"User-Agent": ua, "X-Forwarded-For": ip, "Content-Type": "text/plain"})


def _rows(db):
    return db.execute(text("SELECT * FROM analytics_traffic_daily")).mappings().all()


def _stub_geo(monkeypatch):
    monkeypatch.setattr("app.services.audience.geo.lookup", lambda ip: geo.Country("NG", "Nigeria", "AF"))


def test_a_ping_counts_view_visitor_and_source(client, db_session, monkeypatch):
    _stub_geo(monkeypatch)
    r = _ping(client, {"path": "/markets", "ref": "https://www.google.com/", "first_today": True, "visitor": "new"})
    assert r.status_code == 204
    row = _rows(db_session)[0]
    assert (row["path"], row["page_type"], row["country_code"], row["source"], row["source_domain"], row["device"]) == \
        ("/markets", "section", "NG", "search", "google.com", "desktop")
    assert (row["views"], row["visitors"], row["new_visitors"], row["returning_visitors"]) == (1, 1, 1, 0)


def test_second_page_same_day_adds_a_view_not_a_visitor(client, db_session, monkeypatch):
    _stub_geo(monkeypatch)
    _ping(client, {"path": "/markets", "ref": "", "first_today": True, "visitor": "returning"})
    _ping(client, {"path": "/markets", "ref": "", "first_today": False})
    row = _rows(db_session)[0]
    assert (row["views"], row["visitors"], row["returning_visitors"]) == (2, 1, 1)


def test_bots_junk_paths_and_dead_stories_are_ignored(client, db_session, monkeypatch):
    _stub_geo(monkeypatch)
    _ping(client, {"path": "/markets"}, ua="Googlebot/2.1")
    _ping(client, {"path": "/wp-login.php"})
    _ping(client, {"path": "/markets/no-such-story"})
    assert _rows(db_session) == []


def test_old_slug_ping_is_ignored(client, db_session):
    assert _ping(client, {"slug": "some-story"}).status_code == 204
    assert _rows(db_session) == []


def test_story_rows_carry_the_story_id_and_feed_most_read(client, db_session, publish, monkeypatch):
    _stub_geo(monkeypatch)
    slug = publish("Counted story")
    _ping(client, {"path": f"/markets/{slug}", "ref": ""})
    row = _rows(db_session)[0]
    story_id = db_session.execute(text("SELECT id FROM content_articles WHERE slug=:s"), {"s": slug}).scalar()
    assert row["article_id"] == story_id and row["page_type"] == "story"
    assert db_session.execute(text("SELECT views FROM content_article_daily_views WHERE article_id=:i"),
                              {"i": story_id}).scalar() == 1


def test_countries_seen_are_remembered_for_the_dimension(client, db_session, monkeypatch):
    monkeypatch.setattr("app.services.audience.geo.lookup", lambda ip: geo.Country("GB", "United Kingdom", "EU"))
    _ping(client, {"path": "/"})
    row = db_session.execute(text("SELECT name, continent FROM analytics_countries WHERE code='GB'")).first()
    assert tuple(row) == ("United Kingdom", "EU")


def test_no_table_keeps_the_readers_ip(client, db_session, monkeypatch):
    _stub_geo(monkeypatch)
    _ping(client, {"path": "/", "ref": "", "first_today": True, "visitor": "new"}, ip="203.0.113.77")
    columns = db_session.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = DATABASE() "
        "AND data_type IN ('varchar','char','text','mediumtext','longtext')")).all()
    from app.core.db import engine
    with engine.connect() as committed:  # rate-limit rows are committed on their own connection
        for table, column in columns:
            for conn in (db_session, committed):
                found = conn.execute(text(f"SELECT COUNT(*) FROM `{table}` WHERE `{column}` LIKE :ip"),
                                     {"ip": "%203.0.113.77%"}).scalar()
                assert found == 0, (table, column)


def test_rate_limit_buckets_never_store_addresses(db_session):
    from app.core import rate_limit
    from app.core.db import engine

    rate_limit.hit("login:198.51.100.23", 8, 900)
    with engine.connect() as conn:
        buckets = [r[0] for r in conn.execute(text("SELECT bucket FROM ops_rate_limits"))]
    assert buckets and not any("198.51.100.23" in b for b in buckets)


def test_newsletter_links_carry_the_marker():
    from app.core.settings import SITE_URL
    from app.services import newsletter

    html = f'<a href="{SITE_URL}/markets/x">story</a> <a href="{SITE_URL}/about#team">team</a> ' \
           f'<a href="https://other.example/x">other</a>'
    marked = newsletter.mark_links(html)
    assert f'href="{SITE_URL}/markets/x#from=newsletter"' in marked
    assert f'href="{SITE_URL}/about#team"' in marked and 'href="https://other.example/x"' in marked


def test_pages_tell_the_browser_whether_visitor_flags_are_on(client):
    assert 'data-visitor-flags="on"' in client.get("/").text
```

Delete `apps/api/tests/test_views.py`. Its "every module is ported" assertion moves into
`test_audience_beacon.py`:

```python
def test_every_module_is_ported():
    from tests.test_dialect import NOT_YET_PORTED

    assert NOT_YET_PORTED == set()
```

`apps/admin/src/__tests__/siteBeacon.test.js`:

```js
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";

new Function(readFileSync(resolve(__dirname, "../../../api/app/site/static/js/site.js"), "utf8"))();

function memoryStorage(initial = {}) {
  const data = { ...initial };
  return { getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v); }, data };
}
const loc = (path, hash = "") => ({ pathname: path, hash });
const nav = (extra = {}) => ({ ...extra });

describe("beacon payload", () => {
  let store;
  beforeEach(() => { store = memoryStorage(); });

  it("first visit ever: new visitor, first page today", () => {
    const p = window.ASI.beaconPayload(loc("/markets"), "", nav(), store, "2026-10-09", true);
    expect(p).toEqual({ path: "/markets", ref: "", first_today: true, visitor: "new" });
    expect(store.data["asi-v-day"]).toBe("2026-10-09");
  });
  it("came back another day: returning visitor", () => {
    store = memoryStorage({ "asi-v-day": "2026-10-01", "asi-v-last": "2026-10-01" });
    const p = window.ASI.beaconPayload(loc("/"), "", nav(), store, "2026-10-09", true);
    expect(p.visitor).toBe("returning");
  });
  it("second page today: not a new visitor", () => {
    store = memoryStorage({ "asi-v-day": "2026-10-09", "asi-v-last": "2026-10-09" });
    const p = window.ASI.beaconPayload(loc("/"), "", nav(), store, "2026-10-09", true);
    expect(p.first_today).toBe(false);
    expect(p).not.toHaveProperty("visitor");
  });
  it("Global Privacy Control or Do Not Track: page view only, nothing stored", () => {
    for (const n of [nav({ globalPrivacyControl: true }), nav({ doNotTrack: "1" })]) {
      const s = memoryStorage();
      const p = window.ASI.beaconPayload(loc("/"), "", n, s, "2026-10-09", true);
      expect(p).toEqual({ path: "/", ref: "" });
      expect(s.data).toEqual({});
    }
  });
  it("flags switched off on the server: page view only", () => {
    const p = window.ASI.beaconPayload(loc("/"), "", nav(), store, "2026-10-09", false);
    expect(p).toEqual({ path: "/", ref: "" });
  });
  it("newsletter marker in the fragment", () => {
    const p = window.ASI.beaconPayload(loc("/markets/x", "#from=newsletter"), "", nav(), store, "2026-10-09", true);
    expect(p.from).toBe("newsletter");
  });
  it("storage that throws still counts the page view", () => {
    const broken = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
    const p = window.ASI.beaconPayload(loc("/"), "", nav(), broken, "2026-10-09", true);
    expect(p).toEqual({ path: "/", ref: "" });
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_audience_beacon.py -o addopts= -q -p no:cacheprovider` and
`cd apps/admin && npx vitest run src/__tests__/siteBeacon.test.js`
Expected: FAIL.

- [ ] **Step 3: Implement**

`apps/api/app/core/rate_limit.py`: store the bucket hashed. In `hit()`, replace
`bucket, start = bucket[:200], _window_start(window_seconds)` with:

```python
    # Buckets often contain an address ("login:<ip>"); only a hash is ever stored.
    bucket, start = hashlib.sha256(bucket.encode()).hexdigest(), _window_start(window_seconds)
```

Then add `import hashlib`.

Append to `apps/api/app/services/audience.py`:

```python
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.services import geo  # noqa: E402
from app.services.articles import PUBLIC_PREDICATE  # noqa: E402

BOTS = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|curl|wget|python-requests|headless",
                  re.IGNORECASE)


def record_page_view(db: Session, *, path: str, ref: str | None, from_marker: str | None, first_today: bool | None,
                     visitor: str | None, ip: str, user_agent: str | None, site_host: str) -> bool:
    """One anonymous page view. The IP is used for the country lookup and then
    dropped; only the day's counts are stored."""
    if not user_agent or BOTS.search(user_agent):
        return False
    page = classify_path(path)
    if page is None:
        return False
    page_type, story_slug = page
    article_id = None
    if story_slug:
        article_id = db.execute(text(f"SELECT a.id FROM content_articles a WHERE a.slug = :s AND {PUBLIC_PREDICATE}"),
                                {"s": story_slug}).scalar()
        if article_id is None:
            return False
    country = geo.lookup(ip)
    source, source_domain = classify_source(ref, from_marker, site_host)
    db.execute(text(
        """INSERT INTO analytics_traffic_daily (day, path, page_type, article_id, country_code, source, source_domain,
                                                device, views, visitors, new_visitors, returning_visitors)
           VALUES (UTC_DATE(), :path, :type, :article, :country, :source, :domain, :device, 1, :v, :n, :r)
           ON DUPLICATE KEY UPDATE views = views + 1, visitors = visitors + VALUES(visitors),
               new_visitors = new_visitors + VALUES(new_visitors),
               returning_visitors = returning_visitors + VALUES(returning_visitors)"""),
        {"path": path, "type": page_type, "article": article_id, "country": country.code, "source": source,
         "domain": source_domain, "device": classify_device(user_agent), "v": 1 if first_today else 0,
         "n": 1 if visitor == "new" else 0, "r": 1 if visitor == "returning" else 0})
    if country.code != "ZZ" and country.name:
        db.execute(text("INSERT IGNORE INTO analytics_countries (code, name, continent, first_seen) "
                        "VALUES (:c, :n, :k, UTC_DATE())"),
                   {"c": country.code, "n": country.name[:100], "k": country.continent})
    if article_id is not None:  # "Most read"
        db.execute(text("""INSERT INTO content_article_daily_views (article_id, day, views) VALUES (:a, UTC_DATE(), 1)
                           ON DUPLICATE KEY UPDATE views = views + 1"""), {"a": article_id})
        db.execute(text("UPDATE content_articles SET view_count = view_count + 1 WHERE id = :a"), {"a": article_id})
    db.commit()
    return True
```

Move the import block to the top of the module if the linter prefers. Circular imports aren't a risk: `articles`
doesn't import `audience`.

`apps/api/app/api/public/views.py` (replace):

```python
"""The page-view beacon (site.js, every public page). Answers 204 whatever it
receives, so it can't be used to probe. No address is stored: see
app/services/audience.py."""

import json
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.rate_limit import client_ip, hit
from app.core.settings import SITE_URL
from app.services import audience

router = APIRouter(prefix="/api/v1", tags=["public"])
BEACONS_PER_ADDRESS_PER_HOUR = 120
SITE_HOST = urlparse(SITE_URL).hostname or ""


class PingIn(BaseModel):
    path: str = Field(min_length=1, max_length=300)
    ref: str | None = Field(default=None, max_length=2000)
    first_today: bool | None = None
    visitor: str | None = Field(default=None, pattern="^(new|returning)$")
    from_: str | None = Field(default=None, alias="from", max_length=20)


@router.post("/views", status_code=204)
async def record_view(request: Request, db: Session = Depends(get_db)) -> Response:
    # navigator.sendBeacon posts text/plain, so read the raw body.
    try:
        body = PingIn(**json.loads((await request.body()) or b"{}"))
    except (ValueError, TypeError, ValidationError):
        body = None
    ip = client_ip(request)
    if body and not hit(f"views:{ip}", BEACONS_PER_ADDRESS_PER_HOUR, 3600):
        audience.record_page_view(db, path=body.path, ref=body.ref, from_marker=body.from_,
                                  first_today=body.first_today, visitor=body.visitor, ip=ip,
                                  user_agent=request.headers.get("user-agent"), site_host=SITE_HOST)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
```

Delete `apps/api/app/services/views.py` (`git rm`). Fix any import of `views` in `app/main.py` or elsewhere; grep
`services import .*views` and `services.views`.

`apps/api/app/site/context.py`: where the Jinja environment is created (`templates = Jinja2Templates(...)`), add:

```python
from app.core.settings import ANALYTICS_VISITOR_FLAGS
templates.env.globals["visitor_flags"] = "on" if ANALYTICS_VISITOR_FLAGS else "off"
```

`apps/api/app/site/templates/base.html`: change `<body>` to `<body data-visitor-flags="{{ visitor_flags }}">`.

`apps/api/app/site/templates/article.html`: remove the ` data-view-slug="{{ a.slug }}"` attribute.

`apps/api/app/site/static/js/site.js`: replace the whole `setupViewBeacon` function with:

```js
  /* ---------- audience beacon (every page; no cookies, no identifiers) ----------
     Two on-device notes hold dates only. Global Privacy Control, Do Not Track or
     the server switch (data-visitor-flags="off") turn them off: page view only. */
  function beaconPayload(loc, referrer, nav, storage, today, flagsAllowed) {
    var p = { path: loc.pathname, ref: referrer || '' };
    if (/(^|&)from=newsletter(&|$)/.test(String(loc.hash || '').replace(/^#/, ''))) p.from = 'newsletter';
    var optOut = nav.globalPrivacyControl === true || nav.doNotTrack === '1';
    if (!flagsAllowed || optOut) return p;
    try {
      var day = storage.getItem('asi-v-day');
      var last = storage.getItem('asi-v-last');
      if (day === today) {
        p.first_today = false;
      } else {
        p.first_today = true;
        p.visitor = last ? 'returning' : 'new';
        storage.setItem('asi-v-day', today);
        storage.setItem('asi-v-last', today);
      }
    } catch (e) {
      delete p.first_today;
      delete p.visitor;
    }
    return p;
  }
  window.ASI = window.ASI || {};
  window.ASI.beaconPayload = beaconPayload;

  function setupViewBeacon() {
    if (!navigator.sendBeacon) return;
    var allowed = document.body.getAttribute('data-visitor-flags') !== 'off';
    var storage;
    try { storage = window.localStorage; } catch (e) { storage = null; }
    var safe = storage || { getItem: function () { throw new Error('no storage'); }, setItem: function () {} };
    var today = new Date().toISOString().slice(0, 10);
    var payload = beaconPayload(window.location, document.referrer, navigator, safe, today, allowed);
    navigator.sendBeacon('/api/v1/views', JSON.stringify(payload));
  }
```

Notes on `site.js`:
- `window.ASI` is already defined by the live-freshness helpers. Make sure both assignments keep each other: use
  `window.ASI = window.ASI || {}` before adding keys in both places. Update the existing
  `window.ASI = { liveIsFresh…, withFreshness… }` to
  `window.ASI = Object.assign(window.ASI || {}, { liveIsFresh: liveIsFresh, withFreshness: withFreshness })`.
- `setupViewBeacon()` is already called from the `DOMContentLoaded` handler.
- The `last && last < today` case: a stored last date that is today while the day flag isn't can't happen, because
  both are written together. The plain `last ? 'returning' : 'new'` is correct.

`apps/api/app/services/newsletter.py`: add after `_absolute`:

```python
def mark_links(html: str) -> str:
    """Links back to the site get #from=newsletter — a fragment, so clicks still hit
    the page cache and the beacon (not the server) reads it. Links that already
    have a fragment, and links elsewhere, are left alone."""
    import re

    pattern = re.compile(r'href="(' + re.escape(SITE_URL) + r'[^"#]*)"')
    return pattern.sub(lambda m: f'href="{m.group(1)}#from=newsletter"', html)
```

In `render_issue`, apply it to the HTML and to `web_url`:

```python
    web_url = f"{SITE_URL}/newsletter/issues/{issue['slug']}#from=newsletter"
    ...
    html = mark_links(_render("issue", ...))
```

The `#team` case in the test: `[^"#]*` stops at `#`, so `/about#team` is not matched. It stays unchanged.

- [ ] **Step 4: Run to verify they pass**

Run:
- `docker compose run --rm api pytest tests/test_audience_beacon.py tests/test_newsletter.py tests/test_ops_tables.py tests/test_site_articles.py -o addopts= -q -p no:cacheprovider`
- `cd apps/admin && npx vitest run`

Expected: PASS. `test_ops_tables` still passes: hashing is transparent to `hit()`.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api apps/admin
git commit -m "feat: anonymous audience beacon on every page; hashed rate-limit buckets; newsletter link marker"
```

---

### Task 4: Counting errors

**Files:**
- Modify: `apps/api/app/services/audience.py` (`record_error`), `apps/api/app/core/middleware.py`
- Test: `apps/api/tests/test_audience_errors.py`

**Interfaces:**
- Produces: `audience.record_error(path: str, status: int) -> None`, which writes on its own connection and never
  raises.

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_audience_errors.py`:

```python
from sqlalchemy import text

from app.core.db import engine


def _errors():
    with engine.connect() as conn:
        return {(r.path, r.status): r.hits for r in conn.execute(text("SELECT path, status, hits FROM analytics_errors_daily"))}


def test_missing_story_counts_a_404(client):
    client.get("/markets/no-such-story")
    client.get("/markets/no-such-story")
    assert _errors()[("/markets/no-such-story", 404)] == 2


def test_scanner_paths_are_grouped(client):
    client.get("/wp-login.php")
    client.get("/.env")
    assert _errors()[("(other)", 404)] >= 2


def test_successful_pages_are_not_counted(client):
    client.get("/")
    assert _errors() == {}
```

In `tests/conftest.py`, add `analytics_errors_daily` to the tables `_clean_ops_tables` empties (errors are committed
on their own connection).

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_audience_errors.py -o addopts= -q -p no:cacheprovider`
Expected: FAIL.

- [ ] **Step 3: Implement**

Append to `apps/api/app/services/audience.py`:

```python
def record_error(path: str, status: int) -> None:
    """Counts a 404 or 5xx by page. Paths that aren't real page addresses are
    grouped as "(other)", so scanners can't flood the table."""
    from app.core.db import engine

    key = path if classify_path(path) else "(other)"
    try:
        with engine.begin() as conn:
            conn.execute(text("""INSERT INTO analytics_errors_daily (day, path, status, hits) VALUES (UTC_DATE(), :p, :s, 1)
                                 ON DUPLICATE KEY UPDATE hits = hits + 1"""), {"p": key[:300], "s": status})
    except Exception as exc:  # noqa: BLE001 — counting must never break a response
        print(f"[audience] could not count an error: {exc}")
```

In `apps/api/app/core/middleware.py`, inside `request_context` after `response = await call_next(request)`:

```python
        if (response.status_code == 404 or response.status_code >= 500) and \
                getattr(request.state, "site", "public") == "public" and request.method in ("GET", "HEAD"):
            from app.services import audience

            audience.record_error(request.url.path, response.status_code)
```

- [ ] **Step 4: Run to verify they pass**

Run: `docker compose run --rm api pytest tests/test_audience_errors.py tests/test_site_base.py -o addopts= -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api
git commit -m "feat: count 404 and 5xx responses per page"
```

---

### Task 5: The nightly export job

**Files:**
- Create: `apps/api/app/jobs/analytics.py`
- Modify:
  - `apps/api/app/jobs/__init__.py`
  - `apps/api/app/jobs/__main__.py` (`--rebuild`)
  - `apps/api/app/jobs/runner.py` (`options`)
  - `apps/api/app/jobs/selfcheck.py`
  - `apps/api/app/jobs/tasks.py` (backup exports)
  - `apps/api/app/services/newsletter.py` (`failed_at`)
  - `deploy/crontab.txt`
- Test: `apps/api/tests/test_analytics_export.py`

**Interfaces:**
- Consumes: Task 1 tables, `EXPORTS_DIR`, `ANALYTICS_START`.
- Produces:
  - `analytics.FACTS: dict[str, tuple[list[str], str]]`, mapping a table name to `(columns, sql)`
  - `analytics.DIMENSIONS: tuple[str, ...]`
  - `analytics.export(db, deadline, rebuild: str | None = None, today: date | None = None) -> str`
  - `analytics.fact_files(table: str) -> list[pathlib.Path]`, sorted by date
  - `analytics.dimension_file(name: str) -> pathlib.Path`
  - `analytics.meta_file() -> pathlib.Path`
  - `runner.run(name, session_factory=None, options=None)`
  - job `analytics-export` (`every_minutes=1440`)

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_analytics_export.py`:

```python
import csv
import io
from datetime import date

import pytest
from sqlalchemy import text

from app.jobs import analytics


@pytest.fixture()
def exports(tmp_path, monkeypatch):
    monkeypatch.setattr(analytics, "EXPORTS_DIR", str(tmp_path))
    monkeypatch.setattr(analytics, "ANALYTICS_START", date(2026, 10, 6))
    return tmp_path


def _read(path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf8"))))


def _traffic(db, day, path="/markets", views=3):
    db.execute(text("""INSERT INTO analytics_traffic_daily (day, path, page_type, country_code, source, device, views,
                       visitors, new_visitors, returning_visitors) VALUES (:d, :p, 'section', 'NG', 'direct', 'mobile',
                       :v, 1, 1, 0)"""), {"d": day, "p": path, "v": views})
    db.commit()


def test_export_writes_only_that_days_rows(db_session, exports):
    _traffic(db_session, date(2026, 10, 8), views=3)
    _traffic(db_session, date(2026, 10, 9), views=99)        # today: not exported yet
    analytics.export(db_session, None, today=date(2026, 10, 9))
    rows = _read(exports / "page_traffic" / "2026-10-08.csv")
    assert [(r["date"], r["path"], r["views"]) for r in rows] == [("2026-10-08", "/markets", "3")]
    assert not (exports / "page_traffic" / "2026-10-09.csv").exists()


def test_missing_days_are_filled_from_the_start(db_session, exports):
    analytics.export(db_session, None, today=date(2026, 10, 9))
    for table in analytics.FACTS:
        assert sorted(p.name for p in (exports / table).glob("*.csv")) == \
            ["2026-10-06.csv", "2026-10-07.csv", "2026-10-08.csv"]


def test_empty_day_still_gets_a_file_with_a_header(db_session, exports):
    analytics.export(db_session, None, today=date(2026, 10, 7))
    header = (exports / "page_traffic" / "2026-10-06.csv").read_text(encoding="utf8").splitlines()
    assert header == [",".join(analytics.FACTS["page_traffic"][0])]


def test_existing_days_are_never_rewritten_except_by_rebuild(db_session, exports):
    analytics.export(db_session, None, today=date(2026, 10, 9))
    _traffic(db_session, date(2026, 10, 8), path="/regulation", views=5)
    analytics.export(db_session, None, today=date(2026, 10, 9))
    assert len(_read(exports / "page_traffic" / "2026-10-08.csv")) == 0
    analytics.export(db_session, None, rebuild="2026-10-08", today=date(2026, 10, 9))
    assert len(_read(exports / "page_traffic" / "2026-10-08.csv")) == 1


def test_dimensions_and_meta(db_session, exports, publish):
    publish("Dimension story", countries=["NG", "KE"])
    db_session.execute(text("INSERT INTO analytics_countries (code, name, continent, first_seen) "
                            "VALUES ('GB', 'United Kingdom', 'EU', '2026-10-08')"))
    db_session.commit()
    analytics.export(db_session, None, today=date(2026, 10, 9))
    countries = {r["country_code"]: r for r in _read(exports / "dim_country.csv")}
    assert countries["NG"]["is_africa"] == "1" and countries["GB"]["is_africa"] == "0"
    assert countries["ZZ"]["name"] == "Unknown" and len([c for c in countries.values() if c["is_africa"] == "1"]) == 54
    stories = _read(exports / "dim_story.csv")
    assert any(s["title"] == "Dimension story" for s in stories)
    pairs = {(r["country_code"]) for r in _read(exports / "story_country.csv")}
    assert {"NG", "KE"} <= pairs
    dates = _read(exports / "dim_date.csv")
    assert dates[0]["date"] == "2026-10-06" and dates[-1]["date"] == "2030-12-31"
    meta = _read(exports / "meta.csv")[0]
    assert meta["last_export_date"] == "2026-10-08" and meta["start_date"] == "2026-10-06"


def test_newsletter_facts(db_session, exports):
    db_session.execute(text("""INSERT INTO newsletter_subscribers (email, status, source_page, created_at, confirmed_at,
                               unsubscribe_token) VALUES ('a@example.com','confirmed','home','2026-10-08 10:00',
                               '2026-10-08 11:00','t-a'), ('b@example.com','unsubscribed','article','2026-10-01',
                               '2026-10-02','t-b')"""))
    db_session.execute(text("UPDATE newsletter_subscribers SET unsubscribed_at='2026-10-08 12:00' WHERE email='b@example.com'"))
    db_session.commit()
    analytics.export(db_session, None, today=date(2026, 10, 9))
    rows = {r["source_page"]: r for r in _read(exports / "newsletter_daily" / "2026-10-08.csv")}
    assert (rows["home"]["signups"], rows["home"]["confirmations"]) == ("1", "1")
    assert rows["article"]["unsubscribes"] == "1"


def test_pruning_keeps_unexported_days(db_session, exports):
    _traffic(db_session, date(2026, 5, 1))      # older than 90 days, but no file: kept
    analytics.export(db_session, None, today=date(2026, 10, 9))
    assert db_session.execute(text("SELECT COUNT(*) FROM analytics_traffic_daily WHERE day='2026-05-01'")).scalar() == 1


def test_selfcheck_reports_yesterdays_export(db_session, exports, monkeypatch):
    from app.jobs import selfcheck

    monkeypatch.setattr(selfcheck, "EXPORTS_DIR", str(exports))
    rows = {r["check"]: r for r in selfcheck.run_checks(
        db_session, http_get=lambda url: (200, {"x-asi-instance": "a", "x-asi-cache": "file"}), smtp=False)}
    assert rows["yesterday's analytics export exists"]["ok"] is False


def test_rebuild_from_the_command_line(db_session, exports, monkeypatch):
    from app.jobs import JOBS, runner

    seen = {}
    monkeypatch.setitem(JOBS, "analytics-export", runner.Job(
        "analytics-export", lambda db, deadline, **opts: seen.update(opts) or "ok", 1440))
    from app.jobs.__main__ import main

    monkeypatch.setattr(runner, "SessionLocal", lambda: db_session)
    assert main(["app.jobs", "analytics-export", "--rebuild", "2026-10-08"]) == 0
    assert seen == {"rebuild": "2026-10-08"}
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_analytics_export.py -o addopts= -q -p no:cacheprovider`
Expected: FAIL (`app.jobs.analytics` missing).

- [ ] **Step 3: Implement**

`apps/api/app/jobs/analytics.py`:

```python
"""analytics-export job: one CSV per fact table per UTC day (never rewritten,
except by --rebuild), current dimension snapshots, and meta.csv — the files
Power BI downloads through /admin/exports (spec §3)."""

from __future__ import annotations

import csv
import io
import os
import pathlib
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from app.core.settings import ANALYTICS_START, EXPORTS_DIR
from app.services import audience
from app.services.articles import PUBLIC_PREDICATE, article_url

FACTS = {
    "page_traffic": (
        ["date", "path", "page_type", "story_id", "country_code", "source", "source_domain", "device", "views",
         "visitors", "new_visitors", "returning_visitors"],
        """SELECT day, path, page_type, article_id, country_code, source, source_domain, device, views, visitors,
                  new_visitors, returning_visitors
           FROM analytics_traffic_daily WHERE day = :d
           ORDER BY path, country_code, source, source_domain, device"""),
    "newsletter_daily": (
        ["date", "source_page", "signups", "confirmations", "unsubscribes"],
        """SELECT :d, COALESCE(source_page, ''),
                  SUM(DATE(created_at) = :d), SUM(DATE(confirmed_at) <=> :d), SUM(DATE(unsubscribed_at) <=> :d)
           FROM newsletter_subscribers
           WHERE DATE(created_at) = :d OR DATE(confirmed_at) = :d OR DATE(unsubscribed_at) = :d
           GROUP BY COALESCE(source_page, '') ORDER BY 2"""),
    "newsletter_sends": (
        ["date", "issue_number", "subject", "sent", "failed"],
        """SELECT :d, i.issue_number, i.subject, SUM(DATE(d.sent_at) <=> :d), SUM(DATE(d.failed_at) <=> :d)
           FROM newsletter_deliveries d JOIN newsletter_issues i ON i.id = d.issue_id
           WHERE DATE(d.sent_at) = :d OR DATE(d.failed_at) = :d
           GROUP BY i.issue_number, i.subject ORDER BY i.issue_number"""),
    "errors": (
        ["date", "path", "status", "count"],
        "SELECT day, path, status, hits FROM analytics_errors_daily WHERE day = :d ORDER BY path, status"),
}
DIMENSIONS = ("dim_date", "dim_country", "dim_story", "story_country", "dim_source")
KEEP_RAW_DAYS = 90


def _root() -> pathlib.Path:
    return pathlib.Path(EXPORTS_DIR)


def fact_files(table: str) -> list[pathlib.Path]:
    folder = _root() / table
    return sorted(folder.glob("????-??-??.csv")) if folder.is_dir() else []


def dimension_file(name: str) -> pathlib.Path:
    return _root() / f"{name}.csv"


def meta_file() -> pathlib.Path:
    return _root() / "meta.csv"


def _write(path: pathlib.Path, header: list[str], rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if v is None else (v.isoformat() if hasattr(v, "isoformat") else v) for v in row])
    partial = path.with_name(path.name + ".partial")
    partial.write_text(buffer.getvalue(), encoding="utf8")
    os.replace(partial, path)


def _write_day(db, table: str, day: date) -> None:
    columns, sql = FACTS[table]
    rows = db.execute(text(sql), {"d": day}).all()
    _write(_root() / table / f"{day.isoformat()}.csv", columns, rows)


def _dimensions(db, last_day: date) -> None:
    days = []
    d = ANALYTICS_START
    while d <= date(2030, 12, 31):
        days.append((d, d.year, (d.month - 1) // 3 + 1, d.month, d.strftime("%B"), d.isocalendar()[1],
                     d.isoweekday(), d.strftime("%A"), 1 if d.isoweekday() >= 6 else 0))
        d += timedelta(days=1)
    _write(dimension_file("dim_date"), ["date", "year", "quarter", "month", "month_name", "week", "weekday",
                                        "weekday_name", "is_weekend"], days)

    african = db.execute(text("SELECT code, name, region, coverage FROM content_countries ORDER BY name")).all()
    african_codes = {r[0] for r in african}
    others = db.execute(text("SELECT code, name, continent FROM analytics_countries ORDER BY name")).all()
    rows = [(c, n, region, 1, coverage) for c, n, region, coverage in african]
    rows += [(c, n, "", 1 if continent == "AF" else 0, "") for c, n, continent in others if c not in african_codes]
    rows.append(("ZZ", "Unknown", "", 0, ""))
    _write(dimension_file("dim_country"), ["country_code", "name", "region", "is_africa", "coverage"], rows)

    stories = db.execute(text(f"""SELECT a.id, a.slug, a.tag, a.title, a.tag, u.name, DATE(a.published_at),
                                          a.word_count, a.status
                                   FROM content_articles a JOIN auth_users u ON u.id = a.author_id
                                   WHERE {PUBLIC_PREDICATE} ORDER BY a.id""")).all()
    _write(dimension_file("dim_story"), ["story_id", "slug", "url", "title", "section", "author", "published_date",
                                         "word_count", "status"],
           [(i, slug, article_url(tag, slug), title, section, author, published, words, status)
            for i, slug, tag, title, section, author, published, words, status in stories])

    pairs = db.execute(text(f"""SELECT ac.article_id, ac.country_code FROM content_article_countries ac
                                JOIN content_articles a ON a.id = ac.article_id
                                WHERE {PUBLIC_PREDICATE} ORDER BY 1, 2""")).all()
    _write(dimension_file("story_country"), ["story_id", "country_code"], pairs)
    _write(dimension_file("dim_source"), ["source", "label", "description"], audience.SOURCES)
    _write(meta_file(), ["generated_at", "last_export_date", "start_date", "tables"],
           [(datetime.now(timezone.utc).isoformat(timespec="seconds"), last_day.isoformat(),
             ANALYTICS_START.isoformat(), " ".join(list(FACTS) + list(DIMENSIONS)))])


def _prune(db, today: date) -> None:
    cutoff = today - timedelta(days=KEEP_RAW_DAYS)
    exported = {p.stem for p in fact_files("page_traffic")} & {p.stem for p in fact_files("errors")}
    for day in db.execute(text("SELECT DISTINCT day FROM analytics_traffic_daily WHERE day < :c "
                               "UNION SELECT DISTINCT day FROM analytics_errors_daily WHERE day < :c"),
                          {"c": cutoff}).scalars():
        if day.isoformat() in exported:
            db.execute(text("DELETE FROM analytics_traffic_daily WHERE day = :d"), {"d": day})
            db.execute(text("DELETE FROM analytics_errors_daily WHERE day = :d"), {"d": day})
    db.commit()


def export(db, deadline, rebuild: str | None = None, today: date | None = None) -> str:
    today = today or datetime.now(timezone.utc).date()
    last_day = today - timedelta(days=1)
    written = 0
    if rebuild:
        day = date.fromisoformat(rebuild)
        for table in FACTS:
            _write_day(db, table, day)
        written = len(FACTS)
    else:
        day = ANALYTICS_START
        while day <= last_day:
            for table in FACTS:
                if not (_root() / table / f"{day.isoformat()}.csv").exists():
                    _write_day(db, table, day)
                    written += 1
            day += timedelta(days=1)
    _dimensions(db, last_day)
    _prune(db, today)
    return f"{written} daily file(s) written" + (f" (rebuilt {rebuild})" if rebuild else "")
```

Register the job (`apps/api/app/jobs/__init__.py`):

```python
from app.jobs import analytics as _analytics
JOBS["analytics-export"] = Job("analytics-export", _analytics.export, 1440)
```

Make the runner accept options (`apps/api/app/jobs/runner.py`):
- Change the signature to `def run(name: str, session_factory=None, options: dict | None = None) -> dict:`.
- Change the call to `detail = str(job.fn(db, deadline, **(options or {})) or "")[:2000]`.

`apps/api/app/jobs/__main__.py` `main()`: accept `--rebuild <date>` after the job name:

```python
def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 2
    if argv[1] == "--list":
        print("\n".join(sorted(JOBS)))
        return 0
    name, options = argv[1], {}
    if name not in JOBS:
        print(f"unknown job {name!r}; try --list")
        return 2
    if len(argv) == 4 and argv[2] == "--rebuild":
        options["rebuild"] = argv[3]
    elif len(argv) != 2:
        print(__doc__)
        return 2
    result = run(name, options=options)
    print(f"[{name}] {result['status']}: {result['detail']}")
    return 0 if result["status"] in ("ok", "skipped") else 1
```

Update the module docstring with the line
`python -m app.jobs analytics-export --rebuild YYYY-MM-DD   — rewrite one day's files`.

In the test, `run(name, options=…)` uses `SessionLocal` when `session_factory` is None, which is why the test
monkeypatches `runner.SessionLocal`. The runner closes sessions not marked `owned_by_test`; the fixture marks
`db_session`.

`apps/api/app/jobs/selfcheck.py`:
- Add `"analytics-export": 1440` to `JOB_INTERVALS`.
- Import `EXPORTS_DIR` and `datetime`/`timedelta`/`timezone`.
- Add to `run_checks`:

```python
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    exported = os.path.exists(os.path.join(EXPORTS_DIR, "page_traffic", f"{yesterday}.csv"))
    add("yesterday's analytics export exists", exported, yesterday)
```

`apps/api/app/jobs/tasks.py` `_backup()`: after the database dump, archive the exports folder:

```python
    if os.path.isdir(EXPORTS_DIR):
        archive = os.path.join(BACKUP_DIR, f"exports-{stamp}.tar.gz")
        with tarfile.open(archive + ".partial", "w:gz") as tar:
            tar.add(EXPORTS_DIR, arcname="exports")
        os.replace(archive + ".partial", archive)
        kept = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("exports-") and f.endswith(".tar.gz"))
        for old in kept[:-BACKUP_KEEP_DAILY]:
            os.unlink(os.path.join(BACKUP_DIR, old))
```

Import `EXPORTS_DIR` in the settings import. In `tests/test_hardening.py` `backup_dirs`, add
`monkeypatch.setattr(tasks, "EXPORTS_DIR", str(tmp_path / "exports"))` so the existing backup tests don't archive a
real folder.

`apps/api/app/services/newsletter.py`, failure time: in `_send_locked`, change the delivery update to

```sql
UPDATE newsletter_deliveries SET status = :status, error = :error,
       sent_at = CASE WHEN :status = 'sent' THEN UTC_TIMESTAMP(6) END,
       failed_at = CASE WHEN :status = 'failed' THEN UTC_TIMESTAMP(6) END
WHERE issue_id = :id AND subscriber_id = :sid
```

Also set `d.failed_at = UTC_TIMESTAMP(6)` in the "unsubscribed since queued" update.

`deploy/crontab.txt`: add

```
15 4 * * *    cd ~/asi/apps/api && ~/virtualenv/asi/apps/api/3.11/bin/python -m app.jobs analytics-export >> ~/asi-data/logs/cron-output.log 2>&1
```

Then update the header comment: the three daily jobs run at 04:15, 04:00 and 04:30 server time (02:15, 02:00 and
02:30 UTC).

- [ ] **Step 4: Run to verify they pass**

Run: `docker compose run --rm api pytest tests/test_analytics_export.py tests/test_jobs.py tests/test_hardening.py tests/test_deploy_kit.py tests/test_newsletter.py -o addopts= -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api deploy/crontab.txt
git commit -m "feat: nightly analytics export — daily fact files, dimensions, meta; in the backup"
```

---

### Task 6: Export downloads and export keys

**Files:**
- Create: `apps/api/app/api/admin/exports.py`, `apps/admin/src/pages/DataExports.jsx`, `apps/admin/src/pages/exportRules.js`
- Modify: `apps/api/app/main.py` (router), `apps/admin/src/App.jsx`, `apps/admin/src/components/Layout.jsx`
- Test: `apps/api/tests/test_exports_api.py`, `apps/admin/src/__tests__/exportRules.test.js`

**Interfaces:**
- Consumes: Task 5 `analytics.FACTS`, `DIMENSIONS`, `fact_files`, `dimension_file`, `meta_file`.
- Produces:
  - `GET /admin/exports` returns `{"tables": [{"name", "kind", "url"}], "last_export_date"}`
  - `GET /admin/exports/{name}.csv`
  - `GET /admin/export-keys`, `POST /admin/export-keys {"label"}` (returns `{"id", "label", "key"}`; the key is
    returned only here), `DELETE /admin/export-keys/{id}`
  - `exportRules.keyState(key) -> "active" | "revoked"`
  - `exportRules.exportUrl(origin, name) -> string`

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_exports_api.py`:

```python
import base64

import pytest

from app.jobs import analytics


@pytest.fixture()
def exports(tmp_path, monkeypatch):
    monkeypatch.setattr(analytics, "EXPORTS_DIR", str(tmp_path))
    header = ",".join(analytics.FACTS["page_traffic"][0])
    (tmp_path / "page_traffic").mkdir()
    (tmp_path / "page_traffic" / "2026-10-07.csv").write_text(header + "\n2026-10-07,/,home,,NG,direct,,mobile,1,1,1,0\n")
    (tmp_path / "page_traffic" / "2026-10-08.csv").write_text(header + "\n2026-10-08,/,home,,KE,direct,,mobile,2,1,0,1\n")
    (tmp_path / "dim_source.csv").write_text("source,label,description\ndirect,Direct,x\n")
    (tmp_path / "meta.csv").write_text("generated_at,last_export_date,start_date,tables\nx,2026-10-08,2026-10-06,y\n")
    return tmp_path


def _basic(key):
    return {"Authorization": "Basic " + base64.b64encode(f"powerbi:{key}".encode()).decode()}


def _new_key(client, admin):
    return client.post("/admin/export-keys", json={"label": "Laptop"}, headers=admin).json()


def test_fact_table_streams_with_one_header_in_date_order(client, make_user, exports):
    _, admin = make_user("admin")
    key = _new_key(client, admin)["key"]
    r = client.get("/admin/exports/page_traffic.csv", headers=_basic(key))
    lines = r.text.splitlines()
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert lines[0].startswith("date,path") and [l[:10] for l in lines[1:]] == ["2026-10-07", "2026-10-08"]
    assert r.headers["cache-control"] == "no-store" and r.headers["x-robots-tag"] == "noindex"


def test_stream_with_no_files_is_header_only(client, make_user, exports):
    _, admin = make_user("admin")
    key = _new_key(client, admin)["key"]
    r = client.get("/admin/exports/errors.csv", headers=_basic(key))
    assert r.text.splitlines() == [",".join(analytics.FACTS["errors"][0])]


def test_dimension_and_meta_downloads(client, make_user, exports):
    _, admin = make_user("admin")
    key = _new_key(client, admin)["key"]
    assert "Direct" in client.get("/admin/exports/dim_source.csv", headers=_basic(key)).text
    assert "2026-10-08" in client.get("/admin/exports/meta.csv", headers=_basic(key)).text


def test_wrong_revoked_or_missing_keys_are_refused(client, make_user, exports):
    _, admin = make_user("admin")
    made = _new_key(client, admin)
    assert client.get("/admin/exports/meta.csv", headers=_basic("wrong")).status_code == 401
    assert client.get("/admin/exports/meta.csv").status_code == 401
    client.delete(f"/admin/export-keys/{made['id']}", headers=admin)
    r = client.get("/admin/exports/meta.csv", headers=_basic(made["key"]))
    assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Basic")


def test_an_export_key_opens_nothing_else(client, make_user, exports):
    _, admin = make_user("admin")
    key = _new_key(client, admin)["key"]
    assert client.get("/admin/me", headers=_basic(key)).status_code == 401
    assert client.get("/admin/export-keys", headers=_basic(key)).status_code == 401


def test_admins_can_download_with_their_session_and_list_keys_without_secrets(client, make_user, exports):
    _, admin = make_user("admin")
    _new_key(client, admin)
    assert client.get("/admin/exports/meta.csv", headers=admin).status_code == 200
    keys = client.get("/admin/export-keys", headers=admin).json()
    assert keys[0]["label"] == "Laptop" and "key" not in keys[0] and "key_hash" not in keys[0]


def test_only_admins_manage_keys(client, make_user):
    _, editor = make_user("editor")
    assert client.post("/admin/export-keys", json={"label": "x"}, headers=editor).status_code == 403


def test_unknown_export_name_is_404(client, make_user, exports):
    _, admin = make_user("admin")
    assert client.get("/admin/exports/../../etc.csv", headers=admin).status_code == 404
    assert client.get("/admin/exports/nope.csv", headers=admin).status_code == 404


def test_exports_are_not_served_on_the_public_host(client, monkeypatch, exports, make_user):
    from app.core import hosts

    _, admin = make_user("admin")
    monkeypatch.setattr(hosts, "ENABLED", True)
    monkeypatch.setattr(hosts, "PUBLIC_HOST", "asi.test")
    monkeypatch.setattr(hosts, "ADMIN_HOST", "admin.asi.test")
    r = client.get("/admin/exports/meta.csv", headers={**admin, "Host": "asi.test"})
    assert r.status_code == 404
```

`apps/admin/src/__tests__/exportRules.test.js`:

```js
import { describe, expect, it } from "vitest";
import { exportUrl, keyState } from "../pages/exportRules";

describe("export rules", () => {
  it("builds the download address on the current admin origin", () => {
    expect(exportUrl("https://admin.asi.test", "page_traffic")).toBe("https://admin.asi.test/admin/exports/page_traffic.csv");
  });
  it("a key with a revocation date is revoked", () => {
    expect(keyState({ revoked_at: "2026-10-09T10:00:00Z" })).toBe("revoked");
    expect(keyState({ revoked_at: null })).toBe("active");
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker compose run --rm api pytest tests/test_exports_api.py -o addopts= -q -p no:cacheprovider` and
`cd apps/admin && npx vitest run src/__tests__/exportRules.test.js`
Expected: FAIL.

- [ ] **Step 3: Implement**

`apps/api/app/api/admin/exports.py`:

```python
"""Analytics downloads for Power BI (spec §4). Fact tables stream every daily
file as one CSV (header once, date order); dimensions and meta.csv stream their
snapshot. Access: an export key over HTTP Basic (any username) — which opens
these addresses and nothing else — or an admin's own session."""

from __future__ import annotations

import base64
import binascii
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.db import get_db
from app.core.rate_limit import hit
from app.core.security import get_session_user, require_role
from app.jobs import analytics

router = APIRouter(tags=["admin:exports"])
KEY_REQUESTS_PER_HOUR = 120
_REFUSED = HTTPException(status_code=401, detail="An export key or an admin session is required",
                         headers={"WWW-Authenticate": 'Basic realm="ASI exports"'})


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def export_access(request: Request, db: Session = Depends(get_db)) -> dict:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("basic "):
        try:
            key = base64.b64decode(auth[6:]).decode().split(":", 1)[1]
        except (binascii.Error, UnicodeDecodeError, IndexError):
            raise _REFUSED
        row = db.execute(text("SELECT id FROM ops_export_keys WHERE key_hash = :h AND revoked_at IS NULL"),
                         {"h": _hash(key)}).first()
        if row is None:
            raise _REFUSED
        if hit(f"export-key:{row.id}", KEY_REQUESTS_PER_HOUR, 3600):
            raise HTTPException(status_code=429, detail="Too many downloads with this key — try again in an hour")
        db.execute(text("UPDATE ops_export_keys SET last_used_at = UTC_TIMESTAMP(6) WHERE id = :i"), {"i": row.id})
        db.commit()
        return {"export_key_id": row.id}
    bearer = auth[7:] if auth.lower().startswith("bearer ") else None
    try:
        user = get_session_user(request, bearer, db)
    except HTTPException:
        raise _REFUSED
    if user["role"] != "admin" or user.get("_scope") != "full":
        raise _REFUSED
    return {"user_id": user["id"]}


def _names() -> dict[str, str]:
    names = {name: "fact" for name in analytics.FACTS}
    names.update({name: "dimension" for name in analytics.DIMENSIONS})
    names["meta"] = "meta"
    return names


def _stream_fact(table: str):
    yield (",".join(analytics.FACTS[table][0]) + "\n").encode()
    for path in analytics.fact_files(table):
        with open(path, "rb") as handle:
            handle.readline()  # each daily file repeats the header
            while chunk := handle.read(64 * 1024):
                yield chunk


def _stream_file(path):
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not exported yet — the nightly export creates it")
    with open(path, "rb") as handle:
        while chunk := handle.read(64 * 1024):
            yield chunk


_HEADERS = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}


@router.get("/admin/exports")
def list_exports(request: Request, access: dict = Depends(export_access)):
    meta = analytics.meta_file()
    last = None
    if meta.exists():
        lines = meta.read_text(encoding="utf8").splitlines()
        last = lines[1].split(",")[1] if len(lines) > 1 else None
    return {"tables": [{"name": n, "kind": k, "url": f"/admin/exports/{n}.csv"} for n, k in _names().items()],
            "last_export_date": last}


@router.get("/admin/exports/{name}.csv")
def download(name: str, access: dict = Depends(export_access)):
    kind = _names().get(name)
    if kind is None:
        raise HTTPException(status_code=404, detail="No such export")
    if kind == "fact":
        body = _stream_fact(name)
    else:
        path = analytics.meta_file() if kind == "meta" else analytics.dimension_file(name)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Not exported yet — the nightly export creates it")
        body = _stream_file(path)
    return StreamingResponse(body, media_type="text/csv; charset=utf-8", headers=_HEADERS)


class KeyIn(BaseModel):
    label: str = Field(min_length=1, max_length=100)


@router.get("/admin/export-keys")
def list_keys(user: dict = Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = db.execute(text("""SELECT k.id, k.label, k.created_at, k.last_used_at, k.revoked_at, u.name AS created_by
                              FROM ops_export_keys k LEFT JOIN auth_users u ON u.id = k.created_by
                              ORDER BY k.revoked_at IS NULL DESC, k.created_at DESC""")).mappings().all()
    return [dict(r) for r in rows]


@router.post("/admin/export-keys")
def create_key(body: KeyIn, user: dict = Depends(require_role("admin")), db: Session = Depends(get_db)):
    key = secrets.token_urlsafe(32)  # 43 characters
    key_id = db.execute(text("INSERT INTO ops_export_keys (label, key_hash, created_by) VALUES (:l, :h, :u) RETURNING id"),
                        {"l": body.label.strip(), "h": _hash(key), "u": user["id"]}).scalar()
    log_action(db, user["id"], "export_key.create", "export_key", key_id, {"label": body.label.strip()})
    db.commit()
    return {"id": key_id, "label": body.label.strip(), "key": key}


@router.delete("/admin/export-keys/{key_id}")
def revoke_key(key_id: int, user: dict = Depends(require_role("admin")), db: Session = Depends(get_db)):
    done = db.execute(text("UPDATE ops_export_keys SET revoked_at = UTC_TIMESTAMP(6) WHERE id = :i AND revoked_at IS NULL"),
                      {"i": key_id}).rowcount
    if not done:
        raise HTTPException(status_code=404, detail="No active key with that id")
    log_action(db, user["id"], "export_key.revoke", "export_key", key_id)
    db.commit()
    return {"status": "revoked"}
```

Notes:
- **The `../../etc.csv` test:** the path doesn't match `{name}.csv` with a known name, and Starlette normalises it,
  so the request ends in 404 either way. The `_names()` lookup is the guard.
- **The `export_key` test:** `/admin/me` and `/admin/export-keys` use `get_current_user`/`require_role`, which read
  Bearer tokens and cookies only. A Basic header is invisible to them, so they answer 401.

Register in `app/main.py`: add `exports` to the `from app.api.admin import (...)` list and to the router loop.

`apps/admin/src/pages/exportRules.js`:

```js
/** Data exports page helpers. */
export function exportUrl(origin, name) {
  return `${origin.replace(/\/$/, "")}/admin/exports/${name}.csv`;
}

export function keyState(key) {
  return key.revoked_at ? "revoked" : "active";
}
```

`apps/admin/src/pages/DataExports.jsx`:

```jsx
import { useState } from "react";
import { api, del, post } from "../api";
import { Badge, ConfirmDialog, ErrorNotice, Field, formatDateTime, Loading, PageHead, useLoad, useToast } from "../components/ui";
import { exportUrl, keyState } from "./exportRules";

export default function DataExports() {
  const keys = useLoad(() => api("/admin/export-keys"));
  const tables = useLoad(() => api("/admin/exports"));
  const notify = useToast();
  const [label, setLabel] = useState("");
  const [created, setCreated] = useState(null);
  const [revoking, setRevoking] = useState(null);
  const [error, setError] = useState(null);

  async function create(event) {
    event.preventDefault();
    setError(null);
    try {
      setCreated(await post("/admin/export-keys", { label }));
      setLabel("");
      keys.reload();
    } catch (err) { setError(err); }
  }

  async function revoke() {
    try {
      await del(`/admin/export-keys/${revoking.id}`);
      notify("Key revoked");
      keys.reload();
    } catch (err) { setError(err); } finally { setRevoking(null); }
  }

  if (keys.loading || tables.loading) return <Loading />;
  return (
    <>
      <PageHead title="Data exports" subtitle="Daily audience files for Power BI. Each key can only download these files." />
      <ErrorNotice error={error || keys.error || tables.error} />
      <div className="card">
        <h2>Export keys</h2>
        <form onSubmit={create} style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          <Field label="New key for…" hint="e.g. Analyst laptop">
            <input value={label} onChange={(e) => setLabel(e.target.value)} required maxLength={100} />
          </Field>
          <button className="btn brand" type="submit">Create key</button>
        </form>
        {created && (
          <div className="notice warn" style={{ marginTop: 12 }}>
            Copy this key now — it won't be shown again. In Power BI choose <b>Basic</b>, any user name, and this as the password:
            <pre className="mono">{created.key}</pre>
            <button className="btn small" onClick={() => { navigator.clipboard.writeText(created.key); notify("Copied"); }}>Copy</button>
          </div>
        )}
        <div className="table-wrap" style={{ border: 0, marginTop: 12 }}>
          <table>
            <thead><tr><th>Label</th><th>Created</th><th>Last used</th><th>State</th><th /></tr></thead>
            <tbody>
              {keys.data.map((k) => (
                <tr key={k.id}>
                  <td>{k.label}<div className="small muted">{k.created_by}</div></td>
                  <td className="small">{formatDateTime(k.created_at)}</td>
                  <td className="small">{k.last_used_at ? formatDateTime(k.last_used_at) : "never"}</td>
                  <td><Badge kind={keyState(k) === "active" ? "ok" : "alert"}>{keyState(k)}</Badge></td>
                  <td>{keyState(k) === "active" && <button className="btn small danger" onClick={() => setRevoking(k)}>Revoke</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <h2>Download addresses</h2>
        <p className="small muted">Last export: {tables.data.last_export_date || "not yet"} · In Power BI: Get Data → Web → paste an address.</p>
        <div className="table-wrap" style={{ border: 0 }}>
          <table>
            <tbody>
              {tables.data.tables.map((t) => {
                const url = exportUrl(window.location.origin, t.name);
                return (
                  <tr key={t.name}>
                    <td><b>{t.name}</b><div className="small muted">{t.kind}</div></td>
                    <td className="mono small">{url}</td>
                    <td><button className="btn small" onClick={() => { navigator.clipboard.writeText(url); notify("Copied"); }}>Copy</button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      {revoking && (
        <ConfirmDialog title="Revoke this key?" danger confirmLabel="Revoke"
          message={`Power BI using "${revoking.label}" will stop refreshing until it gets a new key.`}
          onConfirm={revoke} onCancel={() => setRevoking(null)} />
      )}
    </>
  );
}
```

Before writing this file, check the exact `ui.jsx` exports (`Field`, `ConfirmDialog`, `useToast`, `Badge`) and their
props in `apps/admin/src/components/ui.jsx`. Adjust prop names to match; this shape follows `Settings.jsx`.

`App.jsx`: import `DataExports` and add
`<Route path="exports" element={<RequireAuth min="admin"><DataExports /></RequireAuth>} />`. `Layout.jsx`: add
`{ to: "/exports", label: "Data exports", min: "admin" }` after System health.

- [ ] **Step 4: Run to verify they pass**

Run:
- `docker compose run --rm api pytest tests/test_exports_api.py tests/test_hosts.py -o addopts= -q -p no:cacheprovider`
- `cd apps/admin && npx vitest run && npm run build`

Expected: PASS; the build succeeds.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api apps/admin
git commit -m "feat: Power BI download addresses with revocable export keys; Data exports page"
```

---

### Task 7: Deploy, docs and the end-to-end check

**Files:**
- Modify:
  - `deploy/deploy.sh` (first GeoIP fetch)
  - `deploy/env.example` (three settings)
  - `deploy/test_deploy.sh` (stub handles `geoip-update`)
  - `docs/DEPLOYMENT.md`, `docs/LAUNCH_CHECKLIST.md`, `docs/ARCHITECTURE.md`
- Create: `docs/POWER_BI.md`
- Test: the existing kit tests, plus an end-to-end script run

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Deploy kit**

In `deploy/deploy.sh`, after the "Migrating the database" step, add:

```bash
step "GeoIP database"
if [ ! -f "$DATA/geoip/dbip-country-lite.mmdb" ]; then
  (cd "$release/apps/api" && ASI_ENV_FILE="$ENV_FILE" "$PY" -m app.jobs geoip-update) \
    || echo "!! GeoIP download failed — countries show as Unknown until the monthly job succeeds."
fi
```

In `deploy/test_deploy.sh`, the stub Python handles every `-m app.jobs …` call: change the selfcheck case to
`*"-m app.jobs"*) exit 0 ;;`.

Append to `deploy/env.example`:

```
# Audience analytics (Power BI). The first day of the exported history (YYYY-MM-DD).
ANALYTICS_START=2026-10-01
# "off" stops the two on-device visitor notes (page views are still counted).
ANALYTICS_VISITOR_FLAGS=on
GEOIP_PATH=/home/africast/asi-data/geoip/dbip-country-lite.mmdb
```

Run: `python deploy/test_check_env.py && bash deploy/test_htaccess.sh && docker run --rm -v "$PWD:/repo" -w /repo alpine:3.20 sh -c "apk add -q bash git coreutils findutils python3 >/dev/null && bash deploy/test_deploy.sh"`
(from Git Bash on Windows, prefix `MSYS_NO_PATHCONV=1` and use `$(cygpath -m "$PWD")`).
Expected: all pass.

- [ ] **Step 2: `docs/POWER_BI.md`**

Write the analyst's guide with these sections and exactly this DAX:

1. **What you get:**
   - the tables (from spec §3.2–3.3)
   - fact tables grow by one day each night
   - `meta.csv` holds the last export date
2. **Connect (once per table):**
   1. Admin → Data exports → create a key.
   2. Get Data → Web → paste the address.
   3. Choose **Basic**: any user name, the key as password. Power BI stores it.
   4. In Power Query, set the types: `date` as Date; counts as Whole number; `story_id` as Whole number.
3. **Model:**
   - **Fact to dimension relationships:**
     - `dim_date[date]` 1→* to every fact's `date`
     - `dim_country[country_code]` 1→* `page_traffic[country_code]`
     - `dim_story[story_id]` 1→* `page_traffic[story_id]`
     - `dim_source[source]` 1→* `page_traffic[source]`
   - **The story–country bridge:**
     - `dim_story[story_id]` 1→* `story_country[story_id]`
     - `dim_country[country_code]` 1→* `story_country[country_code]`
     - the bridge filters both ways for "stories about Kenya"
   - Mark `dim_date` as the date table.
4. **Measures:**

```DAX
Views = SUM ( page_traffic[views] )
Visitors = SUM ( page_traffic[visitors] )
New visitors = SUM ( page_traffic[new_visitors] )
Returning visitors = SUM ( page_traffic[returning_visitors] )
Returning share = DIVIDE ( [Returning visitors], [New visitors] + [Returning visitors] )
Views per visitor = DIVIDE ( [Views], [Visitors] )
Views MoM % =
VAR prev = CALCULATE ( [Views], DATEADD ( dim_date[date], -1, MONTH ) )
RETURN DIVIDE ( [Views] - prev, prev )
Views YoY % =
VAR prev = CALCULATE ( [Views], SAMEPERIODLASTYEAR ( dim_date[date] ) )
RETURN DIVIDE ( [Views] - prev, prev )
Views 7-day avg =
AVERAGEX ( DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -7, DAY ), [Views] )
Views 30-day avg =
AVERAGEX ( DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -30, DAY ), [Views] )
Africa share of views =
DIVIDE ( CALCULATE ( [Views], dim_country[is_africa] = 1 ), [Views] )
Newsletter net growth =
SUM ( newsletter_daily[confirmations] ) - SUM ( newsletter_daily[unsubscribes] )
Error count = SUM ( errors[count] )
Data as of = "Data to " & FORMAT ( MAX ( meta[last_export_date] ), "d mmm yyyy" )
```

5. **Starter visuals:**
   - views trend with the 30-day average
   - top stories table (`dim_story[title]`, Views, Visitors)
   - map or bar of Views by `dim_country[name]`, with an Africa filter
   - source mix donut
   - device split
   - newsletter growth line
   - the "Data as of" card
6. **Daily routine:** Home → Refresh. If a refresh fails, check the export key (Admin → Data exports) and
   `meta.csv`'s date.
7. **The file layout is a contract:** columns are only ever added, at the end, and announced. Renames don't happen
   silently.
8. **Privacy:** aggregates only; nothing in these files identifies a person. Keep the `.pbix` and the key private all
   the same.

- [ ] **Step 3: Ops docs**

- **`docs/DEPLOYMENT.md`:**
  - the cron table gains `analytics-export` (04:15 server time) and `geoip-update` (monthly, the 3rd at 05:00)
  - a new "Analytics for Power BI" section points to `POWER_BI.md` and says to approve and publish the privacy-notice
    paragraph (spec §5) in **Site text → Privacy**
  - the Day-to-day table gains "Rebuild one day's export: `python -m app.jobs analytics-export --rebuild YYYY-MM-DD`"
- **`docs/LAUNCH_CHECKLIST.md`:**
  - [ ] privacy-notice paragraph approved and published
  - [ ] the day after launch, `meta.csv` shows yesterday and Power BI refreshes
  - [ ] DB-IP attribution on the Methodology page
- **`docs/ARCHITECTURE.md`:** add an "Audience analytics" key-behaviours bullet: beacon, daily files, export keys.

- [ ] **Step 4: End-to-end against the dev stack**

```bash
docker compose up -d
docker compose run --rm api alembic upgrade head
MSYS_NO_PATHCONV=1 docker compose exec -T -e EXPORTS_DIR=/tmp/exports api python -c "
import json, urllib.request
req = urllib.request.Request('http://localhost:8000/api/v1/views', data=json.dumps({'path': '/', 'ref': '', 'first_today': True, 'visitor': 'new'}).encode(), headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'text/plain'})
print(urllib.request.urlopen(req).status)"
docker compose exec -T api python -c "
from sqlalchemy import text; from app.core.db import engine
with engine.begin() as c: c.execute(text('UPDATE analytics_traffic_daily SET day = UTC_DATE() - INTERVAL 1 DAY'))"
MSYS_NO_PATHCONV=1 docker compose exec -T -e EXPORTS_DIR=/tmp/exports api python -m app.jobs analytics-export
MSYS_NO_PATHCONV=1 docker compose exec -T -e EXPORTS_DIR=/tmp/exports api sh -c "ls /tmp/exports /tmp/exports/page_traffic | tail -5; tail -2 /tmp/exports/page_traffic/*.csv | tail -1"
```

Expected:
- the ping answers `204`
- the export reports files written
- the newest `page_traffic` file contains the `/` row with `ZZ` (no GeoIP file in development)

Then, in the running dev app, create an export key in Admin → Data exports, and download a file through the API:

```bash
curl -s -u powerbi:<the key> http://localhost:8000/admin/exports/meta.csv
```

(The dev container uses its own `EXPORTS_DIR`; restart it with `-e EXPORTS_DIR=/tmp/exports`, or copy the files, to
see real content.)

- [ ] **Step 5: Whole suite and commit**

Run: `docker compose run --rm api pytest -o addopts= -q -p no:cacheprovider && (cd apps/admin && npx vitest run)`
Expected: all pass.

```bash
git add -A deploy docs apps
git commit -m "docs: Power BI guide; deploy fetches GeoIP; analytics settings and checklist"
```

---

## Self-review notes (for the plan author)

- **Spec coverage:**
  - §2.1 browser → T3
  - §2.2 server steps 1–7 → T1 (classification), T2 (country), T3 (upsert, Most read)
  - §2.3 newsletter marker → T3
  - §2.4 errors → T4
  - §3.1 job, schedule, rebuild, pruning, self-check, backup → T5
  - §3.2 facts → T5 (including `failed_at` for `newsletter_sends`)
  - §3.3 dimensions → T5
  - §3.4 phase 2 → out of plan, as the spec says "later"
  - §4.1–4.2 → T6
  - §4.3 guide → T7
  - §5 privacy → T3 (hashed buckets, no-IP test), T7 (notice in docs)
  - §6 server changes → T1, T2, T5, T6, T7
  - §7 tests → each task
- **Names used across tasks:**
  - `audience.classify_*` (T1 → T3, T4)
  - `geo.lookup` / `geo.Country` (T2 → T3)
  - `analytics.FACTS`, `DIMENSIONS`, `fact_files`, `dimension_file`, `meta_file` (T5 → T6)
  - `runner.run(..., options=)` (T5)
  - `EXPORTS_DIR` (T1 → T5, T6)
