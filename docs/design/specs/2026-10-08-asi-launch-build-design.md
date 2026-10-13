# ASI Launch Build — Design Spec

**Product:** Africa Stablecoin Intelligence (ASI) — AfricaStablecoinIntelligence.com, by 3Consulting
**Date:** 2026-10-08
**Status:** Draft for owner review
**Sources of truth read for this spec:** `ASI_Product_Paper.docx`, `ASI_plan_v2.xlsx`, `ASI_Presentation.pptx`,
`asi-data-source-reference.pdf`, `ASI Mock up.html`, `frontend/`, `backend/` (merged build), and the four
reference build packages (`asi_stack`, `_II`, `_III`, `_final`).

---

## 1. Purpose and success criteria

ASI is a **news and intelligence platform** for Africa's stablecoin market. The ASI team writes original news and
analysis in its own words (sources always credited), tracks regulation in every African country, shows a live public
market snapshot, and grows a newsletter audience.

Launch is successful when:

1. A visitor on a phone or desktop can read the home page (rolling live ticker → market snapshot → big story → news
   feed), Market News, Regulation News, any of the 54 country pages, and About — all served as real HTML at real URLs.
2. The ASI team can, from the admin panel and **without a developer**: write, illustrate, review, schedule, publish,
   feature, correct, unpublish and delete news; choose the big story; choose and edit every snapshot card and ticker
   item; update report figures when new reports come out; maintain countries, regulators and regulatory entries;
   send the newsletter.
3. Google, Bing and Google News can crawl and understand every page (sitemaps, RSS, structured data, canonical URLs,
   large-image previews).
4. The stack deploys to one cloud VM with HTTPS on the domain, backups, alerting, and no default secrets.
5. The two founding rules hold, tested: **no self-publishing / no publishing without cited sources**, and **never
   invent a number**.

## 2. Product model

### 2.1 Two kinds of news
Every article belongs to exactly one **section**:

| Section | Covers | Volume |
|---|---|---|
| **Markets** | The transactional side: volumes, adoption, how a country uses stablecoins, exchanges, premiums, payments, fraud and scams (e.g. CBEX) | Most content |
| **Regulation** | What regulators and watchdogs say or do about stablecoins, and how it affects the market | Less frequent |

Articles are additionally tagged with **zero or more countries** (any of the 54). That tag is what links news to
country pages. (DB column `content.articles.tag` keeps its existing values `Markets` / `Regulation`.)

### 2.2 Public pages

| Page | URL | Content |
|---|---|---|
| Home | `/` | Breaking banner (when active) → masthead → hero → **rolling live ticker** → **Market Snapshot** (metric cards + country row) → **Big Story** (lead + two secondary) → Latest intelligence feed with filters + sidebar (newsletter, Most read, About) |
| Market News | `/markets`, `/markets/{slug}` | Section lead story, paginated Markets feed; full article page |
| Regulation News | `/regulation`, `/regulation/{slug}` | Section lead story, paginated Regulation feed; full article page |
| Countries | `/countries`, `/countries/{slug}` | Directory of all 54 countries (status chips, filter by region/status); country page: status, plain-language compliance panel, regulators (with register links), regulatory entries, market figure or pending note, news about the country |
| About | `/about` | Who ASI is, coverage, methodology & data sources (Live vs Report explained), team |
| Author | `/authors/{slug}` | Byline page: name, role, bio, photo, their articles |
| Search | `/search?q=` | Full-text search across published articles |
| Newsletter | `/newsletter`, `/newsletter/issues/{slug}`, `/newsletter/confirm`, `/newsletter/unsubscribe` | Signup + archive; confirm / unsubscribe result pages |
| Policies | `/editorial-policy`, `/corrections`, `/privacy`, `/terms`, `/contact` | Required for Google News trust signals, newsletter consent, and legal review |
| Machine | `/sitemap.xml`, `/news-sitemap.xml`, `/feed.xml`, `/markets/feed.xml`, `/regulation/feed.xml`, `/robots.txt`, `/healthz` | |

Main navigation (unchanged from the current frontend): **Home · Market News · Countries · Regulation News · About**,
plus Search icon and Subscribe button. Footer: policies, methodology, contact, social links, RSS.

### 2.3 Home page layout (top to bottom)

1. **Breaking banner** — optional thin rust bar with a headline linking to an article; set and expired by editors.
2. **Masthead** — brand, nav (hamburger menu below 960px), search, Subscribe.
3. **Hero** — eyebrow, headline, intro (editable site text).
4. **Live ticker** — continuously scrolling; items chosen by admins; **pause/play button** (WCAG 2.2.2);
   no motion under `prefers-reduced-motion`. Each item shows value and ▲/▼ change vs 24h ago, computed from data.
5. **Market Snapshot** — its own visual band: row of metric cards (Live = green, Report/Survey = dark with dated
   source stamp) and the country row (one highlighted country in rust). Live cards show "Updated 12 min ago"; if a
   feed is past its stale threshold the badge turns amber **"Delayed"** with the last-updated time. A frozen number is
   never presented as live.
6. **Big Story** — full-width: **lead story** (large cover image ~60% width, section tag, headline in Fraunces at
   large size, summary, byline, time) and **two secondary stories** beside/below it with images.
7. **Latest intelligence** (two columns) — filter chips All · Markets · Regulation · Nigeria · Kenya · Ghana ·
   South Africa · More countries ▾; list items with thumbnail, tag, headline, byline/time; "Load more". Stories in the
   Big Story slots are excluded from the feed below to avoid duplicates.
   Sidebar: newsletter box ("Get the ASI briefing"), **Most read (7 days)**, About ASI.
8. **Footer.**

Live figures (ticker + live cards) refresh in place every 60 s via `GET /api/v1/live`; everything else is
server-rendered and cached.

### 2.4 Article page
Section tag + country chips → headline → summary (dek) → byline (author link, role) · published date · updated date
· reading time → **cover image with caption and credit** → body (Markdown rendered to sanitised HTML; inline
figures with captions/credits; pull quotes; tables) → **Correction/Update notice** when present (dated, shown at top
and bottom) → **Sources** list (name + link, opens in new tab, `rel="nofollow noopener"`) → share buttons
(LinkedIn, X, WhatsApp, copy link) → "Not financial advice" note on Markets articles → newsletter CTA → Related
stories (same section, overlapping countries, 3 items).

## 3. Pictures in the news

### 3.1 What editors can do
- **Cover image** per article (used on the article page, Big Story, cards, thumbnails, and social share previews).
- **Inline images** anywhere in the body via the editor's *Insert image* button (upload new or pick from library).
- **Media library**: every uploaded image is reusable across articles; searchable by alt text/caption/credit; shows
  where each image is used; an image in use cannot be deleted.
- Per image: **alt text** (required — accessibility and SEO), **caption** (optional), **credit** (required unless
  licence = Own), **licence** (`own`, `licensed`, `creative_commons`, `public_domain`, `courtesy`) and licence note,
  **focal point** (click on the image) so automatic crops keep the subject in frame.

### 3.2 Processing (server-side, on upload)
- Accept JPEG/PNG/WebP up to 10 MB; verify by actually decoding with Pillow (never trust the declared type); reject
  images over 40 megapixels (decompression-bomb guard).
- Auto-orient, **strip EXIF/GPS metadata** (photographer/location privacy).
- Generate WebP variants at 480/800/1200/1600 px wide plus a **1200×630 JPEG social card** cropped around the focal
  point. Original kept privately in storage.
- Stored in MinIO (S3-compatible), served publicly at `/media/...` through Caddy with long-lived cache headers.
- Rendered with `srcset`/`sizes`, explicit width/height (no layout shift), `loading="lazy"` except the lead image
  (`fetchpriority="high"`).
- Body references images as `![alt](media:123 "caption")`; the server renders a `<figure>` with credit. Referencing
  by ID (not URL) means variants can be regenerated without editing articles.

### 3.3 Rules
- The pre-publish checklist (§4.3) blocks publishing if any image in the article lacks alt text, licence, or required
  credit. This extends the Product Paper's copyright standard to images.
- Existing `content.article_media` rows are migrated into the library.

## 4. Admin panel — what the ASI team gets

Served at `admin.africastablecoinintelligence.com` (React SPA, same origin as its API via Caddy).

### 4.1 Roles
| Role (DB value) | Can |
|---|---|
| **Writer** (`author`) | Write/edit own drafts, upload images, submit for review, see others' drafts as titles only |
| **Editor** (`editor`) | Writer + review (approve / request changes), publish, schedule, feature, set Big Story & breaking banner, correct, unpublish, delete; manage countries, regulators, regulatory entries; data alerts |
| **Admin** (`admin`) | Editor + Market Snapshot, Live Ticker, report figures, FX rates, newsletter sending, site text, users, audit log |

Nobody can publish their own article (server-enforced).

### 4.2 Modules
1. **Dashboard** — my drafts, awaiting review, scheduled, open data alerts, subscriber count, most-read this week.
2. **Articles** — list filtered by status (draft / in review / scheduled / published), section, country, author;
   search. **Editor**: title, slug (auto from title, editable; changing a published slug creates a 301 redirect),
   summary, Markdown body with toolbar and side-by-side live preview, section, countries, cover image, SEO
   description, sources; **autosave**; full **revision history** with restore.
3. **Review** — editor sees a full preview exactly as it will appear on the site, completes the checklist, then
   **Approve & publish now**, **Schedule** (date/time, Africa/Lagos default timezone, shown in UTC+offset), or
   **Request changes** with a note back to the writer.
4. **Homepage curation** — pick the **Lead story** and **two secondary stories**, each with optional "feature until"
   expiry; pick a lead for Market News and for Regulation News; set/clear the **Breaking banner** (text, linked
   article, expiry). Empty or expired slots fall back automatically (most recent featured → most recent published),
   so the home page is never empty or stale.
5. **Media library** — §3.
6. **Market Snapshot** — ordered list of cards; for each: label, type (**Live** linked to a live feed / **Report** /
   **Survey**), show/hide, highlight, order (drag). **Country row**: choose countries (any of 54), order, highlight.
7. **Report figures** — the values behind Report/Survey cards and country figures: display value, numeric value,
   YoY %, source, period, sample note (e.g. "n=4,658"), **pending** flag + pending note. Every edit recorded
   (who, field, old → new, when) — existing `metric_edit_history`.
8. **Live Ticker** — choose live feeds, order, short label, show/hide. Live feeds only (the bar is labelled Live);
   report figures belong on snapshot cards.
9. **FX reference rates** — official CBN/SARB/CBK rates used for the premium calculation (CBN auto-scraped; others
   admin-entered).
10. **Countries & Regulators** — per country: status (In force / Developing / Researching), coverage level,
    one-line summary, **plain-language compliance panel** (Markdown), regulators (name, abbreviation, scope, website,
    public register URL, order). **Regulatory entries** per country with edit history.
11. **Newsletter** — subscriber stats (pending/confirmed/unsubscribed, growth), export CSV, issues: write → preview
    → send test to myself → send to all confirmed → publish to archive.
12. **Site text** — hero eyebrow/headline/intro, About page, newsletter pitch, footer blurb, editorial policy page,
    methodology page.
13. **Data alerts** — stale feeds, outliers, jumps, missing official rates; resolve with a note.
14. **Users** — invite (email with set-password link), change role, deactivate; **two-factor (TOTP)** required for
    admins, optional for others; password reset by email.
15. **Audit log** — every publish, unpublish, delete, feature, snapshot/ticker change, figure edit, user change,
    newsletter send: who, what, when.

### 4.3 Pre-publish checklist (from the plan's "Copyright/originality checklist" task)
Editor must tick, stored with the review record:
- Written in ASI's own words — not a close rewording of any single source
- All sources credited and linked
- Facts verified independently where possible
- Image rights cleared (alt, credit, licence present — auto-checked)
- African relevance is clear

## 5. Architecture and repository layout

```
apps/api/                 FastAPI: JSON API + server-rendered public site (Jinja2)
  app/core/               settings, db, cache, security (JWT/cookies/TOTP), email, rate limits, logging
  app/services/           shared domain logic: articles, media, snapshot, ticker, countries, newsletter, search
  app/api/public/         /api/v1/*
  app/api/admin/          /admin/*
  app/site/               page routes, templates/, static/ (css, js, self-hosted fonts, icons)
  app/seo/                sitemaps, RSS, robots, JSON-LD builders, IndexNow ping
  app/cli/                bootstrap_admin, seed_demo, migrate, send_scheduled, regenerate_media
  alembic/                forward migrations
  tests/
apps/admin/               React + Vite admin SPA
pipelines/                Airflow image + dags/
db/init/                  SQL for a fresh database volume
infra/                    docker-compose.prod.yml, Caddyfile, backup/, scripts/
docs/product/             product paper, plan, deck, data-source reference, mockup
docs/reference/           the four reference build packages (archived, not run)
docs/                     ARCHITECTURE.md, DEPLOYMENT.md, LAUNCH_CHECKLIST.md, EDITORIAL_GUIDE.md
docker-compose.yml        local dev stack (repo root)
Makefile, README.md, .github/workflows/ci.yml, .github/dependabot.yml
```

The current `frontend/` design (CSS tokens, Fraunces / IBM Plex, dark band, ticker, cards) becomes
`apps/api/app/site/` templates and static assets — same look, rendered server-side. The site and the JSON API call
the same service functions, so honesty and visibility rules are applied in exactly one place.

Request flow: Browser → Caddy (HTTPS, compression, static/media caching, security headers) → FastAPI (gunicorn +
uvicorn workers) → Redis (page/fragment cache, rate limits, view counters, token revocation) → Postgres/Timescale.
Airflow writes market data; MinIO stores media.

## 6. Data model changes (one new Alembic revision, idempotent; mirrored in `db/init`)

- **`content.countries`** — code (PK, ISO-2), name, slug, currency, region (North/West/Central/East/Southern),
  status (`in_force`/`developing`/`researching`), coverage (`active`/`monitoring`), summary, compliance_md,
  sort_order, updated_by/at. Seeded with all 54; NG, KE, GH, ZA as `active` with statuses taken from the Data Source
  Reference (flagged "verify before launch").
- **`content.regulators`** — id, country_code FK, name, abbreviation, scope, website_url, register_url, sort_order.
  Seeded from the current frontend's regulator lists.
- **`content.articles`** — add `seo_description`, `cover_media_id`, `scheduled_at`, `correction_md`,
  `correction_at`, `view_count`, generated `search_vector` (weighted title/dek/body, GIN index); status gains
  `scheduled`.
- **`content.article_revisions`** — snapshot of title/dek/body/countries on every save.
- **`content.article_reviews`** — reviewer, decision (`approved`/`changes_requested`), note, checklist JSONB, at.
- **`content.slug_redirects`** — old_slug → article_id (301s).
- **`content.media`** — id, object_key, original filename, width, height, alt_text, caption, credit, licence,
  licence_note, focal_x, focal_y, variants JSONB, uploaded_by/at. `content.article_media` becomes a link table
  (article_id, media_id, role `cover`/`inline`).
- **`content.homepage_slots`** — slot (`lead`, `secondary_1`, `secondary_2`, `markets_lead`, `regulation_lead`),
  article_id, expires_at, updated_by/at.
- **`content.breaking_banner`** — single row: text, article_id, is_active, expires_at.
- **`market_data.live_feeds`** — key, label, unit (`usd`/`pct`), country_code, source_name, stale_after_minutes.
  Seeded: `global_supply`, `usdt_share`, `usdc_share`, `premium_NG`, `premium_KE`, `premium_ZA`.
- **`market_data.verified_annual_stats`** — add `label`, `badge` (`Report`/`Survey`), `sample_note`.
- **`site.snapshot_cards`** — id, zone (`metrics`/`countries`), kind (`live`/`report`), live_feed_key or
  report_stat_id, label_override, is_visible, is_highlighted, sort_order. Seeded to reproduce today's four cards and
  four countries exactly.
- **`site.ticker_items`** — id, live_feed_key, label, is_visible, sort_order. Seeded with today's five items.
- **`site.site_text`** — key, value_md, updated_by/at.
- `market_data.metric_visibility` — superseded by `is_visible` on cards/ticker; migration copies existing flags;
  table kept read-only for one release, then dropped.
- **`auth.users`** — add `slug`, `title`, `bio`, `avatar_media_id`, `totp_secret` (encrypted), `totp_enabled`,
  `last_login_at`. **`auth.password_tokens`** (invite/reset, hashed, 24h expiry).
- **`audit.admin_log`** — user_id, action, entity, entity_id, detail JSONB, at.
- **Newsletter** — subscribers add `unsubscribe_token`, `unsubscribed_at`, `consent_text`; issues add `slug`,
  `subject`, `body_md`, `status` (`draft`/`sending`/`sent`), `sent_at`, `recipient_count`, `in_archive`;
  **`newsletter.deliveries`** (issue_id, subscriber_id, status, sent_at, unique pair) so a crashed send resumes
  without emailing anyone twice.

## 7. API surface

### Public `/api/v1`
- `GET /home` — ticker, snapshot (metrics + countries), breaking, lead, secondary, latest articles, site text.
- `GET /live` — ticker + live-card values and freshness only (60-s refresh; tiny payload).
- `GET /news?section=&country=&q=&page=&page_size=` → `{items, total, page}`; `GET /news/{slug}` (404 when missing;
  301 data when redirected); public fields only (no internal IDs).
- `GET /countries`, `GET /countries/{slug_or_code}` — all 54.
- `GET /regulatory-watch?country=` (respects visibility).
- `GET /metrics/*` — existing endpoints kept, now reading cards/feeds.
- `GET /search?q=`.
- `POST /newsletter/subscribe` (JSON `{email, source_page, consent}`), `GET /newsletter/confirm?token=`,
  `GET|POST /newsletter/unsubscribe?token=` (RFC 8058 one-click), `GET /newsletter/issues`.

### Admin `/admin`
Existing routers kept and extended: auth (cookie session + bearer for tests; TOTP; invite/reset), articles
(+ revisions, reviews, schedule, unpublish, correction, feature), media (library, upload, update metadata, usage),
homepage (slots, breaking), snapshot cards, ticker, report figures (manual-stats), live feeds (read), fx, countries,
regulators, regulatory, newsletter (stats, export, issues, test-send, send), site text, flags, users, audit log,
dashboard summary.

## 8. Pipelines (Airflow)
- Keep `dag_country_proxy`, `dag_global_metrics`, `dag_ng_official_rate`.
- `dag_cross_check`: restore what the merge dropped — **staleness checks per live feed** (using
  `live_feeds.stale_after_minutes`), **premium outlier** flag, critical **email alerts** — alongside the existing
  jump checks and trend snapshots.
- New lightweight task in the API container (cron-style loop or Airflow DAG) publishes **scheduled articles** each
  minute and expires homepage slots/banners.
- Ghana live feed: none yet (no viable P2P source per the Data Source Reference); the system shows Ghana's premium
  only once a feed is added.

## 9. SEO, performance, accessibility

- **Per page:** unique `<title>`, meta description, canonical, Open Graph + Twitter cards (1200×630 image),
  `robots: max-image-preview:large` (Google Discover), breadcrumbs.
- **JSON-LD:** `NewsArticle` (headline, images, datePublished/dateModified, author Person with URL, publisher
  Organization with logo), `Organization`, `WebSite` + `SearchAction`, `BreadcrumbList`, `CollectionPage`.
- **Sitemaps:** `sitemap.xml` (index), `news-sitemap.xml` (last 48 h, Google News format), RSS for all/markets/
  regulation. **IndexNow** ping to Bing on publish/update. Google Search Console and Bing Webmaster verification via
  env-configured meta tags.
- **Performance:** Redis-cached rendered HTML for anonymous pages (invalidated on publish/edit/curation change);
  fingerprinted static assets with immutable caching; self-hosted WOFF2 fonts (removes Google Fonts dependency and
  its privacy issue); compressed responses; responsive images. Target Lighthouse ≥ 90 on mobile for Home and Article.
- **Accessibility (WCAG 2.1 AA):** skip link, semantic headings, mobile menu, ticker pause, alt text enforced, focus
  styles, colour contrast checked against the palette, live regions not announced every refresh.
- **Analytics:** privacy-friendly, cookie-free script (Plausible or Umami) enabled by env var — no cookie banner
  needed. Server-side anonymous view counts (bots filtered) power "Most read" and the admin dashboard.

## 10. Security
- Admin session in an **httpOnly, Secure, SameSite=Strict cookie** (admin SPA and its API share an origin via Caddy);
  bearer tokens still accepted for API clients/tests. JWT revocation on logout (existing).
- TOTP 2FA (required for admins); invite/reset via emailed one-time links; login rate limit (existing); audit log.
- Markdown rendered then sanitised (`nh3`) with an allow-list; external links `rel="nofollow noopener"`.
- Strict Content-Security-Policy, HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, frame-ancestors
  none — set by Caddy and the app.
- Upload validation (§3.2). Production refuses to start with any default secret (JWT, DB, MinIO, Airflow).
- Postgres, Redis, MinIO API, Airflow not exposed publicly; Airflow UI via SSH tunnel.
- Dependabot for pip, npm, Docker, GitHub Actions.

## 11. Production deployment (single VM)
- Recommended size: 4 vCPU / 8 GB RAM / 80 GB SSD (Airflow is the heaviest component), Ubuntu 24.04 LTS.
- `infra/docker-compose.prod.yml`: caddy, api (gunicorn), admin (static build served by Caddy), postgres, redis,
  minio, airflow (webserver, scheduler), backup. Healthchecks + `restart: unless-stopped` everywhere; JSON logs with
  rotation; optional Sentry DSN.
- Caddy: automatic Let's Encrypt for `africastablecoinintelligence.com`, `www.` → apex redirect,
  `admin.` subdomain; `/media/*` from MinIO.
- **Backups:** nightly `pg_dump` + media mirror, 14 daily / 8 weekly retention, optional off-site copy to any
  S3-compatible bucket; documented restore drill.
- **Email:** transactional + newsletter via an SMTP provider (Amazon SES, Brevo or Postmark); `docs/DEPLOYMENT.md`
  lists the SPF, DKIM and DMARC DNS records and one-click unsubscribe headers that Gmail/Yahoo require of bulk senders.
- `docs/DEPLOYMENT.md`: DNS → VM → `.env` → `make prod-up` → bootstrap admin → seed countries → Search Console /
  Bing / Google News Publisher Center submission → uptime monitor on `/healthz`.

## 12. Legal and editorial pages
Draft texts (marked for legal review, per the plan's Phase 4 task) for: Privacy notice (NDPA 2023 Nigeria, Kenya DPA
2019, Ghana DPA 2012, POPIA, GDPR), Terms of use, "Not financial advice" disclaimer, Editorial policy (original
analysis, sourcing, two-person review), Corrections policy, Methodology & data sources (attribution to DefiLlama,
Chainalysis, BVNK etc.), Newsletter consent wording stored with each signup.

## 13. Defects found in the current build (all fixed by this work)
1. Frontend calls `/api/dashboard` and `/api/subscriptions`, which don't exist — site shows only hard-coded data.
2. All content rendered client-side under `#` URLs — not indexable as articles.
3. No navigation below 960 px (menu hidden, no replacement).
4. Ticker has no pause control.
5. Newsletter subscribe reads email from the query string, not a JSON body.
6. `/api/v1/news/{slug}` returns 200 `{"detail":"not found"}` instead of 404.
7. Public article detail exposes internal fields (`author_id`, `reviewed_by`, `body_md` raw).
8. `/api/v1/regulatory-watch` ignores visibility settings.
9. Country names only known for 4 countries in the API; 54-country list hard-coded in frontend JS.
10. Merge dropped staleness/outlier checks and alert email from `dag_cross_check`.
11. Merge dropped SMTP auth/TLS from `email.py` — production email can't send.
12. No unsubscribe mechanism (legal requirement) and no welcome email.
13. `test_newsletter.py::test_confirmed_subscriber_resubscribing...` references `app` without importing it.
14. CI validates a root `docker-compose.yml` that doesn't exist.
15. Hard-coded dev passwords in compose; API runs with `--reload`; no production config or HTTPS.
16. Admin panel removed in the merge — no way to write news without raw API calls.
17. Demo regulatory data out of date vs the Data Source Reference (Kenya VASP Regulations 2026 / Legal Notice 134;
    Ghana Act 1154 signed Dec 2025).
18. `__pycache__` directories present in the working tree; no root `.gitignore`.

## 14. Testing and CI
- API suite on real Postgres + Redis (existing pattern, rolled-back transactions), extended with: every public page
  renders 200 and unknown pages 404; Big Story fallback rules; scheduled publish; unpublish/correction; slug
  redirects; review checklist enforcement; image upload validation, EXIF stripping and variants; publish blocked by
  missing alt/licence; snapshot/ticker configuration reflected on Home and `/live`; stale feed → "Delayed";
  54-country API; regulatory visibility; newsletter JSON subscribe → confirm → welcome → unsubscribe; resumable
  issue sending; sitemap/news-sitemap/RSS/robots validity; JSON-LD presence; security headers; TOTP and cookie auth;
  audit log entries.
- Admin: build + lint + component tests for the editor and curation screens.
- CI: API tests, admin build, DAG compile/import check, compose validation (dev + prod), Python lint (ruff).

## 15. Out of scope (later phases)
ASI's own wallet-labelling / live country-level volumes; SARB/CBK scrapers; paid intelligence products and reader
accounts; multilingual (French/Portuguese/Arabic) editions; image galleries and video; comments. The design leaves
room for each (e.g. `live_feeds` accepts new feeds without schema changes).

## 16. Build order
1. Reorganise repo (no behaviour change) + fix CI + `.gitignore`.
2. Schema migration + services layer + public API (`/home`, `/live`, countries, news fixes, newsletter fixes).
3. Server-rendered public site with the existing design, Big Story, pictures display, mobile nav, ticker pause.
4. Media pipeline + library.
5. Admin panel (all modules), cookie auth, TOTP, audit log.
6. SEO layer, policies pages, analytics hook.
7. Pipelines fixes + scheduled publishing.
8. Production compose, Caddy, backups, deployment docs, launch checklist.
9. Full test pass, security review, Lighthouse/accessibility pass.
