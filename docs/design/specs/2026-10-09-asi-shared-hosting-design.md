# ASI on WhoGoHost shared hosting — design

Status: draft for review · Date: 2026-10-09 · Branch: `shared-hosting` (cut from `launch-build`)

## 1. Why this exists

The launch build (`docs/design/specs/2026-10-08-asi-launch-build-design.md`) targets a cloud VM with
Docker, PostgreSQL + TimescaleDB, Redis, Airflow and Caddy. The client's only infrastructure is the domain
`africastablecoinintelligence.com` and a WhoGoHost **Premium 8GB DA Web Hosting** account. The product must run
there, built "in the best recommended way given what's available", with Python at its centre.

This design keeps every reader- and editor-facing feature of the launch build and replaces the
infrastructure beneath it (approach A, chosen by the user over full static generation and over an external
managed Postgres).

### 1.1 Verified facts about the host

From the user's DirectAdmin screenshots and a terminal session on 2026-10-09:

| Item | Value |
|---|---|
| Panel | DirectAdmin (Evolution skin) on CloudLinux, server `da17.host-ww.net`, user `africast` |
| Python | CloudLinux "Setup Python App" (Phusion Passenger, WSGI entry point); Python **3.11.16** (also 3.7, 3.5) |
| Database | **MariaDB 11.4.13** (phpMyAdmin); no PostgreSQL, no Redis, no Docker |
| Limits (LVE) | 1 CPU core (SPEED 100%), **1 GB physical memory**, **15 entry processes**, 50 processes, 16 MB/s IO, 1024 IOPS |
| Space | 8 GB disk, 30 GB/month bandwidth, 150,000 inodes |
| Tools | Cron Jobs, Terminal (SSH), Git 2.43, Let's Encrypt SSL, e-mail accounts, subdomains, JetBackup |
| Network | Outbound HTTPS works (CoinGecko ping → 200) |
| Web server | `Server: nginx` on the domain — DirectAdmin nginx in front of Apache; `.htaccess` applies |
| Clock | Server shows SAST; the application must store and compare times in UTC explicitly |

### 1.2 Goals

- The public site, public JSON API and admin panel run on the account, over HTTPS, at
  `africastablecoinintelligence.com` and `admin.africastablecoinintelligence.com`.
- All launch-build features survive. They are:
  - the editorial workflow: two-person approval, checklist, scheduling, corrections, revisions, redirects
  - big story, snapshot and ticker controls, live figures
  - pictures, newsletter, SEO, all 54 countries
  - two-factor sign-in, the audit log and every honesty rule
- The site stays fast and available inside 1 GB and one core: most public requests never start Python.
- Deploys are `git pull` of a branch that has already passed the tests; the server never builds anything.
- Every behaviour that depends on the host can be verified on the host with one command.

### 1.3 Non-goals

- No external paid services. Brevo (or any SMTP provider) stays an optional settings-only swap.
- No real-time push (WebSockets or SSE). The live figures refresh by polling a static file every 60 seconds.
- No migration of existing production data. There is none, so the database starts from one clean baseline.
- No rewrite of the admin panel UI or of the public templates beyond what the new plumbing requires.

## 2. Architecture

```
            ┌──────────────── nginx (host) ────────────────┐
 reader ──▶ │ static file?  /static /media /live.json      │──▶ served directly
            │ cached page?  public_html/_cache/... (.htaccess)│──▶ served directly
            │ otherwise ──▶ Apache ──▶ Passenger ──▶ Python │
            └───────────────────────────────────────────────┘
                                   │
            passenger_wsgi.py ─ a2wsgi ─ FastAPI app (one app, both host names)
                                   │
                         MariaDB 11.4 (africast_asi)

 cron (DirectAdmin) ──▶ python -m app.jobs <job>   (pipelines, publishing, newsletter, cleanup, backup)
```

### 2.1 Runtime

- **One application.** `deploy/passenger_wsgi.py` exposes `application = ASGIMiddleware(app)` (`a2wsgi`).
- **Two host names, one app.** Both domains' `.htaccess` point Passenger at the same application root, and the app
  routes by host name:
  - **Public host:** the site, `/api/v1`, SEO files. `/admin` answers 404.
  - **Admin host:** the built admin panel (static files, with the SPA fallback to `index.html`) and the `/admin` API.
    Everything else answers 404.
  - The host names come from `SITE_URL` and `ADMIN_URL`. Requests carrying any other host get 404, which stops host-header games.
- **Fallback if the two names can't share one app:** run two Setup Python App entries from the same code. This
  costs about 120 MB more. Section 8 says how this is detected.
- **Memory budget.**
  - Each Python process uses about 115 MB (measured). Passenger's pool size is a server-wide setting on shared hosting
    (not allowed in `.htaccess`); the account's LVE limits (1 GB, 15 entry processes) bound it, and the page cache keeps
    most requests away from Python.
  - Cron jobs get about 300 MB.
  - The rest is headroom.
  - `media.MAX_PIXELS` drops from 40 MP to **24 MP**, and JPEGs are decoded with `Image.draft()` at the largest size needed.
- **Lifespan.** The FastAPI lifespan starts no background loops (Passenger may stop idle processes at any time). All
  periodic work moves to cron (section 4).
- **Security headers** move from Caddy into an app middleware:
  - HSTS
  - `nosniff`
  - the Referrer-Policy
  - on the admin host only: CSP, `X-Frame-Options: DENY` and `X-Robots-Tag: noindex`

  `.htaccess` forces HTTPS and `www` → apex.

### 2.2 Page cache (the core of the design)

Public pages are written to disk after rendering and served by the web server itself from then on.

- **What is cached:** `GET` responses with status 200 on the public host, no query string, and HTML or JSON content.
  This covers:
  - pages: home, section pages, article pages, countries list and country pages, author pages, about, newsletter archive and issues
  - SEO and feed files: `robots.txt`, sitemaps, feeds
  - the JSON endpoints under `/api/v1` without parameters
- **Never cached:**
  - query strings (search, filters, pagination)
  - non-200 responses
  - `POST`
  - anything on the admin host
  - `/healthz`
  - newsletter confirm and unsubscribe
  - any response marked `Cache-Control: no-store`
- **Where:** `public_html/_cache/<path>/index.html` (or `index.json` / `index.xml` / `index.txt` by content type).
  `/` maps to `_cache/index.html`. Writes are atomic: write to a temporary file, then `os.replace`.
- **How it is served:** `.htaccess` rules serve `/_cache%{REQUEST_URI}/index.<ext>` when the method is GET/HEAD, the
  query string is empty and the file exists. A `ForceType` sets the right content type, and `Cache-Control: public,
  max-age=60` sits on cached files.
- **Fallback if the rule doesn't run before Passenger:** the app checks the cache first and returns the file without
  touching the database.
- **Purging.**
  - A content change on one article deletes its page plus every list-type page: home, sections, countries, authors,
    feeds, sitemaps, `/api/v1/*`.
  - A site-wide change deletes the whole cache. Site-wide changes are site text, snapshot cards, ticker items, big
    story, homepage slots, breaking banner, countries and regulators, authors, and redirects.
  - The purge map lives in one module (`app/core/page_cache.py`) and is unit-tested event by event.
- **Freshness safety net.** The `tick` job deletes:
  - list-type cached pages older than 10 minutes, so "Delayed" labels and scheduled releases can't go stale for long
  - article pages older than 24 hours
- **No personal content in pages.** Public pages already carry no per-visitor content: relative times are computed in
  the browser, and there are no CSRF tokens on public forms. A test renders each cached route twice with different
  cookies and asserts the bytes are identical.
- **Live figures.** `tick` writes `public_html/live.json` every minute. `site.js` polls `/live.json` instead of
  `/api/v1/live`, and the "Delayed" state is computed in the browser from each figure's `as_of` and `stale_after`.
  `/api/v1/live` stays for API users.

### 2.3 File layout on the server

```
~/asi/                         git checkout of the `release` branch (code + built admin panel)
~/asi/.env                     secrets and settings (outside every web root)
~/asi-data/originals/          private image originals
~/asi-data/backups/            nightly database dumps + media archives (14 days)
~/asi-data/logs/               job logs (rotated by the cleanup job)
~/domains/africastablecoinintelligence.com/public_html/
    .htaccess  static/ → ~/asi/apps/api/app/site/static (symlink)  media/  _cache/  live.json  <indexnow-key>.txt
~/domains/admin.africastablecoinintelligence.com/public_html/
    .htaccess  assets/ → ~/asi/apps/admin/dist/assets (symlink)
```

If the host forbids symlinks out of `public_html`, `deploy.sh` copies the directories instead.

## 3. Data layer: MariaDB 11.4

### 3.1 Baseline

- Alembic is kept. The four Postgres migrations are replaced by one MariaDB baseline, `0001_mariadb_baseline`.
- The baseline creates every table plus the seed data: 54 countries with regions and regulators, default site text,
  default snapshot and ticker configuration.
- `db/init/*.sql` and the Postgres migrations are deleted (git history keeps them).

### 3.2 Conventions

| Postgres (today) | MariaDB (new) |
|---|---|
| schemas `content.`, `auth.`, `market_data.`, `newsletter.`, `site.`, `ops.` | one database, table prefixes `content_`, `auth_`, `market_`, `newsletter_`, `site_`, `ops_` |
| `serial` / `bigserial` | `BIGINT UNSIGNED AUTO_INCREMENT` |
| `timestamptz`, `now()`, `clock_timestamp()` | `DATETIME(6)` holding UTC; connections run `SET time_zone = '+00:00'`; SQL uses `UTC_TIMESTAMP(6)`; Python converts aware datetimes to naive UTC at the boundary (one helper) |
| `jsonb` | `JSON` (validated); Python serialises and parses |
| `unaccent` + `lower()` | default collation `utf8mb4_uca1400_ai_ci`, so comparisons and `LIKE` ignore accents and case |
| `tsvector` / `websearch_to_tsquery` / `ts_rank` | `FULLTEXT(title, dek, body_text)` + `MATCH … AGAINST (… IN BOOLEAN MODE)`; Python turns the reader's query into quoted boolean terms (operators stripped). If every term is under 3 characters, the search falls back to `LIKE` |
| `ON CONFLICT … DO UPDATE` | `INSERT … ON DUPLICATE KEY UPDATE` |
| `INSERT … RETURNING` | `INSERT … RETURNING` (supported) |
| `UPDATE … RETURNING` | `SELECT … FOR UPDATE` then `UPDATE` in the same transaction |
| `pg_try_advisory_lock` | `GET_LOCK(name, 0)` / `RELEASE_LOCK` on a dedicated connection |
| `interval '14 days'` | `INTERVAL 14 DAY` |
| `ILIKE`, `~` | `LIKE`, `REGEXP` |
| `= ANY(:list)` | SQLAlchemy expanding `IN` parameters |
| `DISTINCT ON` | `ROW_NUMBER() OVER (PARTITION BY …)` |
| partial indexes | ordinary or generated-column indexes |
| Timescale hypertables | ordinary InnoDB tables, primary key `(series_key, ts)`; about 35k rows per series per year at the 15-minute cadence |

- **Driver:** PyMySQL (pure Python, installs without compiling) through SQLAlchemy 2.
- **SQL style:** stays explicit `text()` SQL kept inside the services layer, now in MariaDB dialect.

### 3.3 Redis replacements

| Redis use | Replacement |
|---|---|
| Data cache for public reads | Removed; the page cache covers public reads |
| Rate limits (login, reset, subscribe) | `ops_rate_limits(bucket, window_start, hits)`, fixed windows; one upsert per attempt; the cleanup job prunes old rows |
| Token revocation | `auth_revoked_tokens(jti, expires_at)`; the cleanup job prunes expired rows |
| View counters | A browser beacon `POST /api/v1/views` (`navigator.sendBeacon`) with the article id. It fires once per article per browser per day (localStorage, with a try/catch). Known bots are ignored. It writes an upsert into `content_article_views_daily(article_id, day, views)`; "Most read" reads the last 7 days |

## 4. Background work: cron jobs

One runner, `python -m app.jobs <name>`, wraps every job:

- **Overlap lock:** `GET_LOCK('job:<name>')`. If the job is already running, this run exits quietly.
- **Retries:** HTTP fetches are retried 3 times with exponential backoff.
- **Run log:** each run is written to `ops_job_runs(id, job, started_at, finished_at, status, detail, error)`.
- **Alerts:** a failure sends one e-mail to `ALERT_EMAIL_TO`, de-duplicated per job until a run succeeds.
- **Time budget:** each job has a time budget (default 4 minutes) and stops cleanly when it runs out.

| Schedule | Job | Work |
|---|---|---|
| `* * * * *` | `tick` | Promote due scheduled articles (purge, IndexNow); write `live.json`; expire cached list pages older than 10 minutes and article pages older than 24 hours |
| `*/5 * * * *` | `newsletter` | Send the next batch for any issue in `sending`, up to `MAIL_MAX_PER_HOUR`, recording deliveries; resumes without duplicates |
| `*/15 * * * *` | `global-metrics` | Former `dag_global_metrics` |
| `2-59/15 * * * *` | `country-proxy` | Former `dag_country_proxy` |
| `7-59/15 * * * *` | `cross-check` | Former `dag_cross_check` |
| `20 */2 * * *` | `ng-official-rate` | Former `dag_ng_official_rate` |
| `0 4 * * *` (02:00 UTC) | `cleanup` | Prune rate limits, revoked tokens and old job runs (90 days); rotate logs; remove orphaned cache files |
| `30 4 * * *` (02:30 UTC) | `backup` | `mysqldump --single-transaction` (gzipped) plus a media archive; keep 14 daily copies; write `LAST_STATUS`; alert on failure |

- **Time zone:** DirectAdmin runs cron on the server clock (SAST, UTC+2). Interval jobs don't care; the two daily
  jobs are written in `crontab.txt` as 04:00 and 04:30 server time, which is 02:00 and 02:30 UTC. Jobs themselves
  only ever use UTC.
- **Pipeline code** moves from `pipelines/dags/` to `apps/api/app/pipelines/`. The fetch, validate and store
  functions keep their logic and tests; only the Airflow wrapper goes.
- **The admin newsletter "Send" button** queues the issue (`status = 'sending'`) instead of starting a thread. The
  issue page shows progress (sent, failed and remaining counts) and that sending starts within 5 minutes.
- **Admin "System health" page:**
  - each job's last run, status and error
  - backup status
  - mail configuration status
  - the last `selfcheck` result

## 5. Admin panel, pictures, e-mail

- **Admin build.** On every push to `main`, GitHub Actions:
  1. runs the API tests on MariaDB and the admin tests
  2. builds the admin panel
  3. publishes code plus `apps/admin/dist` to the `release` branch

  Nothing reaches `release` unless every check passes. `VITE_SITE_URL` is set for production.
- **Python dependencies.** Removed: `gunicorn`, `uvicorn` (kept as a dev-only requirement), `psycopg2-binary` and
  `redis`. Added: `a2wsgi` and `PyMySQL`. Every runtime dependency must install from a manylinux wheel; CI checks this
  with `pip install --only-binary=:all:`.
- **Pictures.**
  - The pipeline is unchanged. The storage backend writes public variants to `public_html/media/` and originals to
    `~/asi-data/originals/`.
  - `.htaccess` gives `/media` a one-year immutable cache.
  - Upload limits are 10 MB and 24 MP.
- **E-mail.**
  - Two mailboxes are created in DirectAdmin: `desk@` (transactional and alerts) and `newsletter@`.
  - Both use SMTP over TLS to the host's mail server.
  - `MAIL_MAX_PER_HOUR` (default 100, set to the host's real limit) caps all sending; newsletter batches spread across hours.
  - SPF, DKIM and DMARC records are confirmed during deployment.

## 5a. Brand colour: 3Consulting orange

Requested by the user on 2026-10-09: the parent company's colour **#ff914d** carries about a quarter of the visual
weight, as the main accent on the public site and the admin panel. It replaces the current ochre accent
(`--ochre: #c7862b`, about 24 uses).

| Token | Value | Use | Contrast |
|---|---|---|---|
| `--brand` | `#ff914d` | Fills with ink text: subscribe and primary buttons, ticker label, tags, active nav underline, big-story rule, focus rings, snapshot highlights, admin primary actions. Text on the dark bands. | ink on brand 7.9:1; brand on ink 7.9:1 |
| `--brand-ink` | `#a84d12` | Orange text on the cream page: links on hover, section labels, small accents | 4.9:1 on paper (WCAG AA) |
| `--brand-pale` | `#ffd2b3` | Soft backgrounds (highlighted rows, selected states) with ink text | ink on pale ≥ 12:1 |

- **Rules:**
  - Never white text on `--brand` (2.2:1).
  - Never `--brand` as text on the cream page (1.9:1).
  - Green and rust stay reserved for up and down figures.
- **Brand-colour test:** a test computes these contrast ratios from the CSS tokens and fails below 4.5:1 for any
  pairing the stylesheet uses for text.
- **Logo:** the social card and favicon pick up `--brand` where they used ochre.

## 6. Deploy and operations

- **`deploy/deploy.sh`** runs on the server after `git pull`. It is idempotent and stops on the first error:
  1. `pip install -r requirements.txt`
  2. `alembic upgrade head`
  3. link or copy the static and admin assets
  4. purge the page cache
  5. `touch tmp/restart.txt` (Passenger restart)
  6. `selfcheck`
- **`deploy/crontab.txt`:** the exact lines for DirectAdmin → Cron Jobs (section 4), each using the virtual
  environment's Python and appending to `~/asi-data/logs/<job>.log`.
- **`deploy/htaccess.public` / `deploy/htaccess.admin`:** Passenger directives, HTTPS and `www` redirects, the
  page-cache rules, cache headers, and a block on dotfiles.
- **`python -m app.jobs selfcheck`** checks:
  - the database connection, `time_zone = +00:00` and the migration level
  - that `media`, `_cache` and `originals` are writable
  - an SMTP login
  - that each cron job ran within twice its interval
  - a live request to the public home page twice, with the second answered from the cache file (response header `X-ASI-Cache: file`, set by `.htaccess`)

  It prints a pass/fail table and stores the result for the System health page.
- **`docs/DEPLOYMENT.md`** is rewritten as a numbered checklist keyed to the DirectAdmin screens:
  1. database and user
  2. mailboxes
  3. `admin.` subdomain
  4. Let's Encrypt for both names
  5. SSH deploy key and clone
  6. `.env`
  7. Setup Python App (3.11, application root `~/asi/apps/api`, startup file `passenger_wsgi.py`, entry point `application`)
  8. `deploy.sh`
  9. bootstrap admin and two-factor
  10. cron lines
  11. `selfcheck`
  12. search engine verification and sitemap submission
  13. e-mail DNS records
  14. Lighthouse pass
- **Local development:** `docker-compose.yml` shrinks to MariaDB 11.4 and MailHog. The API runs with
  `uvicorn --reload`, and `make test` runs pytest against MariaDB.
- **Removed:**
  - `infra/docker-compose.prod.yml`, `infra/caddy/`, `infra/backup/`
  - the Airflow image and DAG wrappers
  - Postgres init SQL and the matching checks (`infra/scripts/test_compose.py`)

  `docs/reference/README.md` records why they went. `infra/scripts/check_env.py` is kept and moved to `deploy/`,
  adapted to the new `.env` keys; `deploy.sh` runs it first.

## 7. Testing

- The whole existing API suite runs on MariaDB 11.4 (Docker locally, a service container in CI) with the same
  transactional isolation (savepoints). Every launch-build behaviour test must pass unchanged in intent.
- **New tests:**
  - page cache: write on render; skip query strings, non-200 responses, the admin host and `no-store`; atomic writes;
    purge map per event; identical bytes across visitors
  - `.htaccess` generation (rules present, admin host never cached)
  - host routing (public vs admin vs unknown host)
  - the job runner (lock, retries, run log, alert de-duplication, time budget)
  - each job's effect
  - newsletter queueing and the hourly cap
  - the view beacon (bots ignored, upsert)
  - `passenger_wsgi.application` served through `wsgiref`, an end-to-end request through the real adapter
  - search: accents, short words, boolean-operator stripping
  - UTC handling against a non-UTC server time zone
- The admin tests (vitest) run as now. CI also checks the wheel-only install and builds the admin panel.

## 8. Risks and how each is checked

| Risk | Check | Fallback |
|---|---|---|
| `.htaccess` rewrite may not run before Passenger | `selfcheck` cache test on the host | App-level cache hit (no database work) |
| Two host names may not share one Passenger app | During deployment, both hosts answer with the same `X-ASI-Instance` id | A second Setup Python App entry (+~120 MB) |
| Symlinks out of `public_html` may be disallowed | `deploy.sh` tests link creation | Copy instead of link |
| Host's outbound mail limit unknown | User checks with WhoGoHost; set `MAIL_MAX_PER_HOUR` | Brevo via settings |
| Passenger idle shutdown makes the first request slow (~2 s) | Cached pages hide it for readers | Optional external uptime ping |
| MariaDB `FULLTEXT` ignores words under 3 characters and stopwords | Search tests | `LIKE` fallback for short queries |
| 1 GB limit during image processing plus cron | Memory budget, 24 MP cap, `draft()` decoding to the 1600 px size actually kept, staggered cron | Ask WhoGoHost to lower the account's Passenger pool size |

## 9. Acceptance criteria

1. All API tests pass on MariaDB 11.4, all admin tests pass, CI publishes `release`.
2. On the host, `selfcheck` passes every line, including the cache-file test.
3. The public home page served from cache responds in under 200 ms from Lagos, measured with `curl -w`.
4. Publishing, editing and unpublishing a story is reflected on the home page within one request.
5. A scheduled story appears within 60 seconds of its time.
6. Live figures refresh from `/live.json` without loading Python.
7. `admin.` serves the panel with two-factor sign-in, and `/admin` on the public host answers 404.
8. A newsletter issue to a test list is delivered within the hourly cap, and an interrupted send resumes without duplicates.
9. Lighthouse on the live home page: Performance ≥ 90, Accessibility ≥ 95, SEO 100.
10. Google Search Console accepts the sitemaps.

## 10. Implementation notes

Decisions taken while building (each with its reasoning):

- **Files and columns**
  - `passenger_wsgi.py` lives in `apps/api/` (the Passenger application root), not `deploy/`.
  - Search columns are `search_title` / `search_body`, folded in Python: the body column holds the dek plus plain body
    text. Apostrophe words are stored both split and joined, so "ivoire", "d'ivoire" and "divoire" all match.
  - Country-code columns are `VARCHAR(2)`: MariaDB won't build a generated column from a `CHAR` column.
  - The views table keeps its existing name, `content_article_daily_views`.
- **Live figures:** `live.json` carries the same payload as `/api/v1/live`, with server-computed "Delayed" flags that
  are at most one minute old. The browser does not compute staleness itself.
- **Backups:** database dumps are daily with 14 kept. Media archives are weekly with 2 kept, because 14 daily copies of
  every picture would not fit in 8 GB.
- **Database connections:** every connection releases its named locks when it returns to the pool.
- **Brand colour:** to reach the requested share of orange, rust used as a decorative accent (highlighted country card,
  section tags, eyebrows) became the brand colour. Rust remains for the breaking-news banner and regulation thumbnails.
- **Pipelines:** `ng-official-rate` reads CBN's JSON endpoint (`/api/GetAllNFEM_Rates`), because the rates page
  builds its table in the browser. The NFEM closing rate becomes Nigeria's row in `market_official_rates`, so every
  later P2P reading uses it; previously only the latest reading was patched, and the next one fell back to the
  placeholder. A response without a sane rate fails the run, which alerts once.
- **Final review fixes:**
  - `PassengerMaxPoolSize` removed from `.htaccess`: it is server-config only and would have returned 500.
  - Pictures use an absolute `MEDIA_PUBLIC_BASE_URL`, and the admin host forwards `/media/*` to the public site.
  - Rate limits trust only the last `X-Forwarded-For` hop.
  - The browser marks figures *Delayed* when `live.json` is over 3 minutes old. This reverses the earlier "no browser
    staleness" note, which removed the only safeguard when cron stops.
  - The page cache drops a page whose write raced a purge.
  - Pages served from the cache carry the app's CSP, X-Frame-Options and Permissions-Policy.
  - The newsletter uses at most 80% of the hourly mail limit, and treats sender refusals and 4xx replies as "stop and
    resume", never as failed readers.
- **Hardening (the review's minor findings, all fixed):**
  - Each deploy unpacks into `~/asi-releases/<commit>`, installs and migrates there, then switches `~/asi` in one step.
    The last three releases are kept for `deploy.sh --rollback`. Settings moved to `~/asi-data/.env`. Every CloudLinux
    `.htaccess` block is preserved, and the cache is cleared after the restart.
  - Backups stream to disk, leave nothing on failure, include photo originals and skip privileged dump options.
  - Job alerts reach ops even when the database is down.
  - The live premium reads one indexed row per country. Cron jobs no longer load FastAPI: services raise
    `DomainError`, which the web layer converts.
  - Responses carry an instance id, and the self-check compares it across both addresses. It also reports the full-text
    and timeout settings; search uses the server's real minimum word length, and lock connections raise their own idle
    timeout.
  - The self-check uses the sender's own SMTP connection. Each job keeps its own rotating log.
  - Versioned assets get one-year cache headers. Trailing slashes redirect. The admin folder answers 404 on the public
    address. `/.well-known/` is reachable.
  - CI is read-only except the release step, checks that packages install on the host's Linux, and builds `release` from
    `shared-hosting`.

