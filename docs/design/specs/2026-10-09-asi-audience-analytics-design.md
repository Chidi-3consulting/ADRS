# ASI audience analytics for Power BI — design

Status: draft for review · Date: 2026-10-09 · Branch: `shared-hosting`

## 1. Purpose

The ASI team's analyst wants a Power BI Desktop report on **audience and content performance**:
- which stories, sections and countries are read
- where readers come from
- on which devices
- how the newsletter grows

It must be built on fine-grained daily facts that accumulate into long-term time series.

The ASI market data (global supply, premiums, official and P2P rates, report figures) joins the same model later as
phase 2. It is already stored, so it needs only an export.

### 1.1 Decisions taken with the user

| Question | Decision |
|---|---|
| What the report answers | Audience and content performance first; market series as phase 2 when there is room |
| How traffic is counted | **Approach A:** ASI's own first-party beacon on every page, aggregated on arrival. Rejected: parsing the host's access logs (log access and retention unknown, nginx in front of Apache, bot filtering) and a paid analytics service (cost) |
| How Power BI gets the data | A secure download address per table on the admin host, using Power BI's Web connector with Basic sign-in and an export key. Rejected: syncing files to the laptop, and opening the database to the internet |
| On-device visitor flags | On by default, disclosed in the privacy notice, honouring Global Privacy Control and Do Not Track (user: "use the best recommended option"). Recorded here as the data-protection lead's documented decision; a setting can switch it off |

### 1.2 Constraints

- **Hosting:** everything runs on the WhoGoHost shared-hosting build: MariaDB 11.4, cron jobs through
  `python -m app.jobs`, 1 GB memory, and public pages mostly served from the disk page cache (so the server never sees
  most page views).
- **No personal data:** no IP address, full user agent, persistent identifier or e-mail is stored, logged or exported.
- **Wheels only:** new Python packages must install from ready-made wheels on the host (CI checks this).
- **Fixed files:** the daily files are the permanent record. Once written, a day is not rewritten except by an explicit
  rebuild.

## 2. Counting traffic

### 2.1 In the browser (`site.js`)

On every public page (not the admin panel), after load, one `navigator.sendBeacon('/api/v1/views', …)` sends:

```json
{"path": "/markets/naira-premium-widens", "ref": "https://www.google.com/", "from": "newsletter",
 "first_today": true, "visitor": "returning"}
```

- **`path`:** `location.pathname` only (never the query string or fragment).
- **`ref`:** `document.referrer`, sent as is. The server keeps only its category and host name.
- **`from`:** read from the fragment marker `#from=newsletter`; absent otherwise.
- **`first_today`:** `true` when this browser has not sent a ping today. On-device flag `asi-v-day` holds today's date
  (UTC, `YYYY-MM-DD`).
- **`visitor`:** taken from on-device flag `asi-v-last` (date of the last visit):

  | Flag | `visitor` |
  |---|---|
  | absent | `new` |
  | earlier than today | `returning` |
  | today | not sent (only the first ping of the day carries it) |

**Privacy signals:** when `navigator.globalPrivacyControl === true` or `navigator.doNotTrack === "1"`, the flags are
never read or written, and `first_today`/`visitor` are omitted. The ping then counts a page view only. The same applies
when `ANALYTICS_VISITOR_FLAGS` is off; the page is told through a `data-visitor-flags="off"` attribute on `<body>`.

**Storage access:** wrapped in try/catch. If storage is blocked, the ping counts a page view only.

**Story-only beacon:** the existing story-view beacon (`data-view-slug`) is replaced by this one.

### 2.2 On the server (`POST /api/v1/views`)

The endpoint keeps its current contract:
- the body is read raw (sendBeacon sends `text/plain`)
- it always answers `204`
- it is rate-limited at 120 per address per hour
- `Cache-Control: no-store`

It then:

1. **Drops** the ping if the user agent matches the bot pattern or is missing.
2. **Validates the path:**
   - It must match a public page pattern: `/`, `/markets`, `/regulation`, a story under either, `/countries`,
     `/countries/<slug>`, `/authors/<slug>`, `/newsletter`, `/newsletter/issues/<slug>`, `/about`, or one of the
     editorial pages.
   - Story paths must name a live story.
   - Anything else is dropped.
   - The page type (`home`, `section`, `story`, `country`, `author`, `newsletter`, `page`) and the story id are derived
     here.
3. **Country:** looks up the request's client address (the last `X-Forwarded-For` hop, as for rate limits) in the
   offline GeoIP file:
   - The result is an ISO country code, or `ZZ` when unknown or when the file is missing.
   - The address is used for this lookup only and never stored or logged.
4. **Source:** classified from `from` and `ref`, in this order:
   1. `from=newsletter` → `newsletter`
   2. empty referrer → `direct`
   3. referrer host equal to the site's own host → `internal`
   4. search engines (google.\*, bing.com, duckduckgo.com, yahoo.\*, yandex.\*, ecosia.org, baidu.com) → `search`
   5. social (facebook.com, m.facebook.com, l.facebook.com, instagram.com, linkedin.com, lnkd.in, x.com,
      twitter.com, t.co, whatsapp.com, wa.me, web.whatsapp.com, t.me, telegram.org, reddit.com, youtube.com,
      tiktok.com) → `social`
   6. otherwise → `referral`

   `source_domain` keeps the referrer's host without `www.` for `search`, `social` and `referral`, and is empty
   otherwise.
5. **Device:** classified from the user agent as `mobile`, `tablet` or `desktop`. Only the class is kept.
6. **Upsert** into `analytics_traffic_daily` (UTC day):

```sql
INSERT INTO analytics_traffic_daily (day, path, page_type, article_id, country_code, source, source_domain, device,
                                     views, visitors, new_visitors, returning_visitors)
VALUES (UTC_DATE(), …, 1, :first, :new, :returning)
ON DUPLICATE KEY UPDATE views = views + 1, visitors = visitors + VALUES(visitors),
  new_visitors = new_visitors + VALUES(new_visitors), returning_visitors = returning_visitors + VALUES(returning_visitors)
```

   The flag values come from the ping:
   - `visitors`: 1 when `first_today` is true
   - `new_visitors`: 1 when `visitor=new`
   - `returning_visitors`: 1 when `visitor=returning`

   The primary key is (day, path, country_code, source, source_domain, device).

7. **Story pages** also update `content_article_daily_views` and `content_articles.view_count`, which drive "Most
   read".

### 2.3 Newsletter marker

When an issue is rendered for e-mail, every link to the public site gets `#from=newsletter` appended, unless it already
has a fragment. A query parameter would send every newsletter click past the page cache into Python. A fragment never
reaches the server, so cached pages still serve.

### 2.4 Errors

The app counts its own error responses: middleware upserts into `analytics_errors_daily` (day, path, status, count) for
status 404 and every 5xx on the public host.

- **Paths:** paths that don't match a public page pattern are recorded as `(other)`, so scanners can't flood the table.
- **Coverage:** pages served from the cache are 200 by construction, so nothing is missed.

## 3. Daily files

### 3.1 The job

`analytics-export` is a new job in `app/jobs`.
- **Schedule:** daily at 02:15 UTC (`15 4 * * *` server time), before the 02:30 UTC backup.
- **Target day:** for the previous UTC day, plus any earlier day since `ANALYTICS_START` (the launch date) that has no
  file yet. Every day must have exactly one file per fact table, even if empty.
- **Where:** each fact table is written to `<DATA_DIR>/exports/<table>/<YYYY-MM-DD>.csv`.
- **How:**
  - UTF-8 with a header row, comma separated, ISO dates, and `.` as the decimal separator.
  - Written to `<file>.partial`, then renamed.
- **Never rewritten:** an existing day is not rewritten. `python -m app.jobs analytics-export --rebuild <date>`
  rewrites one day on purpose and records that in the run log.
- **Dimensions:** rewritten in full each run (`<DATA_DIR>/exports/<dim>.csv`) as current snapshots.
- **Pruning:** removes `analytics_traffic_daily` and `analytics_errors_daily` rows older than 90 days, but only for days
  whose files exist.
- **Self-check line:** "yesterday's analytics export exists".
- **Backup:** the nightly backup also writes `exports-<stamp>.tar.gz` of the exports folder (14 kept).

### 3.2 Fact tables

| File | Columns |
|---|---|
| `page_traffic` | `date, path, page_type, story_id, country_code, source, source_domain, device, views, visitors, new_visitors, returning_visitors` |
| `newsletter_daily` | `date, source_page, signups, confirmations, unsubscribes`. Sign-ups are subscribers created that day, by `source_page`; confirmations come from `confirmed_at`; unsubscribes from `unsubscribed_at` |
| `newsletter_sends` | `date, issue_number, subject, sent, failed` (deliveries by `sent_at` day) |
| `errors` | `date, path, status, count` |

### 3.3 Dimension tables

| File | Columns |
|---|---|
| `dim_date` | `date, year, quarter, month, month_name, week, weekday, weekday_name, is_weekend`, from `ANALYTICS_START` to 2030-12-31 |
| `dim_country` | `country_code, name, region, is_africa, coverage`: the 54 African countries from `content_countries`, plus ISO 3166 countries outside Africa (a static list in the code), plus `ZZ` "Unknown" |
| `dim_story` | `story_id, slug, url, title, section, author, published_date, word_count, status` (live stories) |
| `story_country` | `story_id, country_code` |
| `dim_source` | `source, label, description` |

`meta.csv` holds `generated_at, last_export_date, start_date, tables`.

### 3.4 Phase 2 (later, same job)

Add these, with no change to anything above:
- `market_global_daily`: supply, USDT/USDC share (daily close)
- `market_premium_daily`: per country and pair: open, close, min, max premium, P2P and official rate
- `market_report_figures`: the verified stats as a dimension

## 4. Getting the data into Power BI

### 4.1 Export addresses (admin host only)

`GET /admin/exports/{name}.csv` for every table above and `meta.csv`. `GET /admin/exports` lists them as JSON.

- **Fact tables:** streamed as one CSV, with the header once, then every daily file in date order. Memory stays
  constant.
- **Dimensions:** stream their snapshot file.
- **Headers:** `Content-Type: text/csv; charset=utf-8`, `Cache-Control: no-store`, `X-Robots-Tag: noindex`.
- **Never public:** never page-cached. The public host already answers 404 for `/admin`.

### 4.2 Export keys

| Aspect | Rule |
|---|---|
| Sign-in | HTTP Basic: any username, the export key as password |
| Storage | `ops_export_keys(id, label, key_hash, created_by, created_at, last_used_at, revoked_at)`; keys are 40+ random characters, shown once, stored as SHA-256 hashes |
| Scope | the key works **only** on `/admin/exports*`, never on any other admin route; admin sessions also work on the export addresses |
| Rate limit | 120 requests per key per hour |
| Admin page | **Admin → Data exports** (admin role): create a key with a label, see its last use, revoke it, and copy the export addresses |

### 4.3 The analyst's guide

`docs/POWER_BI.md` covers:
- **Connecting:** Get Data → Web, the address, Basic sign-in with the export key, once per table.
- **Model:**
  - relationships, all single-direction from dimension to fact except `story_country`, which is a bridge with
    both-direction filtering on `dim_country`
  - marking `dim_date` as the date table
- **Starter DAX measures:**
  - Views, Visitors, New visitors, Returning share
  - Views MoM %, Views YoY %
  - Views (rolling 7 / 30 days)
  - Top stories by country
  - Newsletter net growth
  - Error rate
- **A "Data as of" card** from `meta.csv`.
- **The daily routine:** Home → Refresh.
- **Handling changes:** what to do if a column is ever added, since the layout is a contract changed only on purpose.

## 5. Privacy

- **Nothing personal stored or logged:** no IP address, user agent, persistent identifier or e-mail is stored or
  logged by any part of this. Exports contain only aggregates and public content metadata. Subscriber e-mails never
  leave the database.
- **On-device flags:** two flags hold dates only, no identifiers. They are skipped under Global Privacy Control, Do Not
  Track, or `ANALYTICS_VISITOR_FLAGS=off`.
- **Privacy notice wording** to approve and publish in Site text (privacy page):

  > **Audience measurement.** To understand which stories are read, our site counts page views without cookies and
  > without storing your IP address or any identifier. When a page loads, your browser tells us the page, where you
  > came from, and whether this is your first visit today; our server looks up your country from your IP address and
  > then discards the address. Your browser keeps two small notes on your device (today's date and the date of your
  > last visit) so we can count daily and returning readers; they contain no identifier and never leave your device
  > except as a yes/no. If your browser sends a Global Privacy Control or Do Not Track signal, we keep no notes and
  > count only the page view. IP geolocation by [DB-IP](https://db-ip.com) (CC BY 4.0).

- **Licence:** DB-IP Lite is CC BY 4.0, so the attribution above is required. It also goes on the Methodology page.

## 6. Server changes

| Area | Change |
|---|---|
| Migration `0002_audience_analytics` | `analytics_traffic_daily`, `analytics_errors_daily`, `ops_export_keys` |
| Packages | `maxminddb` (manylinux wheels; the CI host-wheel check covers it) |
| GeoIP | `<DATA_DIR>/geoip/dbip-country-lite.mmdb`, opened once per process in memory-mapped mode |
| `geoip-update` job | monthly (day 3, 05:00 server time): downloads `https://download.db-ip.com/free/dbip-country-lite-<YYYY-MM>.mmdb.gz`, verifies it opens, swaps it atomically; failure keeps the old file and alerts |
| Deploy | `deploy.sh` runs `geoip-update` once if the file is missing |
| Settings | `ANALYTICS_START` (launch date), `ANALYTICS_VISITOR_FLAGS` (`on`/`off`), `GEOIP_PATH` |
| Cron | two new lines in `deploy/crontab.txt` |
| Self-check | "yesterday's analytics export exists"; "GeoIP file present and under 60 days old" |
| Admin panel | Data exports page and nav link |
| Docs | `docs/POWER_BI.md`; DEPLOYMENT and LAUNCH_CHECKLIST updated |

## 7. Testing

Tests come first, as in the rest of the build.

- **Pure functions:**
  - source classification, including Google country domains, `t.co`, `lnkd.in`, `l.facebook.com`, the newsletter
    marker, internal links and IP-address referrers
  - device classification
  - path validation and page type
- **Browser logic** (vitest over `site.js`):
  - first-today, new versus returning
  - no flags under GPC, DNT or flags-off
  - storage throwing
- **Ping:**
  - the right row is upserted
  - bots, junk and dead-story paths are ignored
  - story pages also feed "Most read"
  - **no table contains the client's IP after a ping** (scan every text column)
- **Country:** behind a `Geo` interface, so tests use a stand-in. The self-check line proves the real file on the
  server.
- **Export job:**
  - one file per table per day, even when empty
  - atomic writes
  - missing days are filled
  - existing days are untouched
  - `--rebuild` rewrites one day
  - pruning only of exported days
- **Export addresses:**
  - an export key works on `/admin/exports*` only
  - revoked and wrong keys get 401
  - fact streams have one header and rows in date order
  - `meta.csv` is correct
  - nothing is served on the public host
- **Newsletter:** rendered links carry `#from=newsletter`.
- **End to end against the dev stack:** a ping, then `analytics-export`, then a download parsed as CSV.

## 8. Out of scope

- Search Console data (needs a Google API credential; can be a later job)
- Newsletter open and click tracking (needs tracking pixels and redirects, a separate privacy decision)
- Cross-day visitor identity, cohorts, funnels
- Publishing to the Power BI Service
