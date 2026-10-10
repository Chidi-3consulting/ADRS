# SafeData by 3Consulting — Launch Programme Design

- **Date:** 2026-10-10
- **Status:** Draft for review
- **Branch:** `safedata-launch` (from `Just-python-II`)
- **Scope:** Take SafeData (formerly ADRS) from a working multi-tenant FastAPI application to a
  globally sellable, production-grade SaaS: full audit, fixes, organisation hierarchy,
  permissions, two product lines, fair global pricing and billing, redesigned experience,
  brand, deployment, legal pack and documentation.

---

## 1. Intent

### 1.1 What we are building and for whom
SafeData helps **organisations** — both *established* ones (existing systems, existing data,
audit pressure) and *establishing* ones (new, often unsure what personal data they hold) —
keep personal and corporate data exactly as long as the law requires, prove consent, answer
data-subject requests, and show a regulator evidence on demand.

Two product lines, sold alone or together:

| Product | What it does |
|---|---|
| **SafeData Retention** | Data inventory, retention schedules per jurisdiction, statutory clocks, reviews, dual-approval disposal, legal holds, disposal evidence, outbound deletion instructions to source systems. |
| **SafeData Consent** | Purposes, versioned notices, consent capture (snippet/API/preference centre/import), receipts, withdrawal that automatically starts the retention clock, preference centre. |
| **SafeData Suite** | Both, 20% cheaper than buying separately. |

Governance modules (Requests/DSAR, DPIA, Gap Assessment, Breach register, RoPA, Vendors,
Retention-policy generator) are included across products per plan (see §6.2).

### 1.2 Success criteria
1. An organisation anywhere can self-serve: discover → free gap check → sign up → onboard in
   under 3 minutes → trial → pay in its own currency via a gateway that works in its country.
2. A multinational can model **Group → Entity → Unit**, with each entity under its own law,
   its own verified domains, and users scoped to what they should see.
3. Every role at every level sees a deliberately designed experience; nothing a user cannot
   do is shown, and everything hidden is also blocked server-side.
4. The audit report's Critical and High findings are all closed and re-verified (Phase 6).
5. Moving from `safedata.3consult-ng.com` to a standalone domain is a configuration change.
6. Stakeholders can make the hosting/domain/pricing decisions from the decision pack alone.

### 1.3 Non-goals (this programme)
- Website cookie banner / CMP (script blocking, IAB TCF, Google Consent Mode) — later phase.
- AI help assistant — later, opt-in, help-content-only (help is structured to allow it).
- SSO/SAML — Enterprise follow-up after launch (data model leaves room for it).
- Languages other than English at launch (app is translation-ready).
- Custom roles — possible Enterprise feature later.
- Running the application on shared hosting (marketing site may be static on shared hosting).

---

## 2. Decisions log

| # | Area | Decision |
|---|---|---|
| D1 | Brand | **SafeData by 3Consulting**. Tagline **"Keep what you must. Release what you should."** Secondary line: "We govern your data without hoarding it." |
| D2 | Logo | **The Lifecycle Ring**: open ink-navy timer arc ending in a 3Consulting-orange dot (record); the gap is lawful release. Same arc used in-product for countdowns and the compliance gauge. No shields/padlocks. |
| D3 | Structure | **Group → Entity → Unit** (3 fixed levels). Entity = legal entity with own country, laws, DPO and verified domains/subdomains. |
| D4 | Identity | One login per person, may belong to several Groups (consultants, auditors, DPO-as-a-service), with an organisation switcher. |
| D5 | Roles | Owner, Admin, Privacy Officer, Data Owner, Contributor, Auditor (time-limited), Viewer — each assigned **at a scope**. Platform: Super Admin, Support. |
| D6 | Platform admin | One **Platform Owner** (the product lead, @3consult-ng.com) created at deploy via one-time command; personal Super Admin logins invited later; platform roles restricted to @3consult-ng.com; mandatory 2FA; offline break-glass codes. No shared passwords. Platform staff cannot open tenant compliance data without customer-approved, time-boxed, audited support access. |
| D7 | Consent product | Consent hub + hosted preference centre + JS snippet/API; DSAR inbox. Cookie CMP deferred. |
| D8 | DPIA / Gap | In-app tools **and** paid 3Consulting expert services; a free public gap check as lead magnet. |
| D9 | Pricing shape | Product × plan (Starter/Growth/Enterprise, sized by entities/users/records/data subjects) × **regional band** (A 100%, B 60%, C 40%, D 25%, World Bank income groups). Fixed, rounded per-currency price books. Monthly and yearly (yearly = 10× monthly). Equity programmes (NGO/education/public sector; establishing-org discount). **Never price on number of categories.** |
| D10 | Currency | Visitor currency auto-detected from IP (Cloudflare `CF-IPCountry`, trusted only from Cloudflare; GeoLite2 fallback); display "local · ≈ USD"; optional override picker. Charged band = verified billing country. |
| D11 | Payments | Gateway-agnostic billing layer. **Paystack** for African billing countries (NGN/GHS/KES/ZAR/USD); **Stripe** elsewhere. Stripe does not onboard Nigeria-registered companies, so: **launch on Paystack** (existing Nigerian entity, international cards enabled) to sell worldwide from day one; **in parallel register a UK private limited company** to own the Stripe account (trust signal for a privacy product, UK/EU buyers prefer UK/EU contracting entities, Stripe UK supports 135+ currencies and Stripe Tax). Use **Stripe Atlas (US Delaware)** instead only if raising US venture capital or targeting US buyers first. Routing switches by configuration once Stripe is live. Tax structure confirmed by an accountant before trading through the UK entity. **The seller is always a company, never an individual**: a personal/sole-trader Stripe account in a director's name is not used (eligibility depends on residence; it mixes personal and company revenue, weakens B2B/DPA trust, and creates a single point of failure). The director's identity verifies the company account instead. **Merchant of Record (e.g. Paddle)** is evaluated in Phase 0 as an alternative to the UK entity, subject to confirming payouts to Nigeria; supported as a third gateway adapter if adopted. |
| D12 | Trial | Free public gap check (no account) + 14-day full-Suite trial, no card. Then read-only, never data-hostage. |
| D13 | Hosting | Managed cloud, EU region (Render Frankfurt; DigitalOcean App Platform as alternative): web + worker + managed PostgreSQL + EU object storage, behind Cloudflare. Docker image for portability. |
| D14 | Domain | Launch on **safedata.3consult-ng.com**; register a standalone domain now to protect the name; domain is configuration; built-in 301 migration mode. |
| D15 | Data minimisation | Retention stores metadata only (never record contents). Consent stores a keyed-hash subject reference; email stored encrypted only while a purpose needs it. 3Consulting acts as processor under a DPA. |
| D16 | Design | "Calm Authority" — light + dark, ink-navy collapsible sidebar (☰ → icon rail; drawer on mobile), orange actions, teal/amber/red status always paired with icon + word, Ctrl+K command palette, self-hosted fonts. |
| D17 | Language | English at launch, every string translatable; locale-aware dates/numbers/currency. |
| D18 | AI | No AI at launch. |
| D19 | Approach | Evolve the existing FastAPI codebase in phases (no rewrite, no SPA). Server-rendered Jinja + HTMX + Alpine.js. |

---

## 3. Personas and journeys

| Persona | Typical role & scope | Primary job |
|---|---|---|
| Founder / Ops lead of an establishing company | Owner + Privacy Officer, Group | "Tell me what data I have and what the law wants; make it easy." |
| Group DPO of a multinational | Privacy Officer, Group | Posture across entities; approvals; regulator evidence. |
| Entity DPO / Compliance officer | Privacy Officer, Entity | Local law clocks, DSARs, breaches, disposals. |
| IT / Systems admin | Admin, Group or Entity | Domains, users, integrations, API keys. |
| Department head | Data Owner, Unit | Respond to reviews, request disposals, keep records current. |
| Clerk / analyst | Contributor, Unit | Add or import records. |
| External auditor / regulator liaison | Auditor, Entity (time-limited) | Read-only evidence, verify audit chain, export packs. |
| Board member / executive | Viewer, Group | Dashboard and printable reports. |
| 3Consulting staff | Platform Owner / Super Admin / Support | Tenants, catalogue, price books, approvals, support. |

Two onboarding journeys (§7.4): **Establishing** (guided inventory from industry pack, gap
assessment, policy templates) and **Established** (import, integrations, entity mapping).

---

## 4. Preliminary audit findings (Phase 0 expands these into the full report)

Evidence gathered 2026-10-10 on `Just-python-II`. Severity: C = Critical, H = High, M = Medium.

| # | Sev | Finding | Evidence |
|---|---|---|---|
| F1 | C | No payment integration exists; billing page shows hard-coded $399/yr. Only a `paystack_customer_code` column and `PaymentTransaction` model. | `app/templates/billing.html`, `app/models.py:21,511` |
| F2 | H | Write routes without role checks: category create/edit, all RoPA routes, bulk import. A Data Owner can change retention periods. | `routes/categories.py:139,241`, `routes/ropa.py`, `routes/import_records.py` |
| F3 | H | Access control and tenant scoping are hand-written per route (91 copies of session boilerplate); one omitted filter = cross-tenant leak. | `routes/*.py` |
| F4 | H | Registration marks the admin's email verified immediately (verification bypassed). | `routes/public.py:487` |
| F5 | H | Six schedulers run as asyncio tasks in the web process: duplicated per worker (no locks), silently stop on idle-suspending hosts. | `main.py:187-313` |
| F6 | H | Intake and dispatch jobs gated on a **global** `SafeData_tier == 'enterprise'` setting — wrong in multi-tenant after tiers were removed; likely never run. | `main.py:242,260` |
| F7 | H | Attachments and backups written to local disk; ephemeral on managed hosts (lost on redeploy). Backups also contain all tenants in one file. | `app/config.py`, `app/backups.py` |
| F8 | H | No real migrations: Alembic configured with zero revisions; schema changed by raw `ALTER TABLE` at startup + `create_all`. | `alembic/versions/`, `main.py:106-162` |
| F9 | H | DSAR, DPIA, Breach, Consent-receipt models exist with **no UI routes**; RoPA not in navigation. README and Documents claim these features. | `app/models.py`, `layout.html`, `README.md` |
| F10 | M | Session freshness check fails open on exception; sessions are stateless signed cookies (no revocation, no "sign out everywhere"). | `app/middleware.py:311`, `app/auth.py:173` |
| F11 | M | `past_due` and `cancelled` subscription states never enforced. | `app/middleware.py:337-362` |
| F12 | M | Geo pricing: single flat price, hand-typed FX, SE and PL wrongly mapped to EUR, several eurozone countries missing. | `app/helpers.py:107-246` |
| F13 | M | Single fixed statutory clocks (e.g. DSAR 30 days) regardless of jurisdiction (GDPR 1 month, CCPA 45 days, etc.). | `app/engine.py` |
| F14 | M | Oversized modules: `engine.py` 1,499 lines, `app_pages.py` 1,303, `helpers.py` 942 (mixes country data, pricing, audit hashing, mailer, CSRF). | `app/` |
| F15 | M | 39 broad exception swallows, 22 `print()` instead of logging, 35 deprecated naive `utcnow()`. | `app/`, `main.py` |
| F16 | M | 251 inline `style=` attributes; design debt and CSP friction. | `app/templates/` |
| F17 | M | Tests: 199 pass but take ~8 min; billing tests are tautological (assert values they just set). | `tests/test_billing.py` |
| F18 | M | Domain hard-coded as `safedata.3consulting.com` in emails; real domain is `3consult-ng.com`. | `routes/public.py:528`, `config.py` |
| F19 | M | Git history contains `.db` files and a 54 MB `cloudflared.exe` (now ignored). If DBs held real data, it persists in history. | `git log` |
| F20 | M | InMotion shared hosting has no supported FastAPI/ASGI path. | InMotion support community |

Baseline: **199 tests pass** (`python -m pytest tests`, 483 s).

---

## 5. Architecture

### 5.1 Code structure (incremental refactor, tests green at every move)
```
retention_py/
  app/core/        config, db, sessions, context (ctx), permissions, i18n, logging, storage
  app/domain/      business logic, no HTTP:
                   org/ (groups, entities, units, domains, memberships)
                   retention/ (schedules, evaluation, disposal, holds)
                   consent/ (purposes, notices, records, receipts, preference)
                   requests/ (DSAR)  governance/ (dpia, gap, breach, ropa, vendors, policy)
                   billing/ (catalogue, price books, subscriptions, entitlements, gateways/)
                   help/ (articles, tours, glossary)
  app/web/         page routes + templates per module (thin: parse → service → render)
  app/api/v1/      REST API (existing URLs preserved)
  app/worker/      scheduler + jobs
  app/content/     jurisdiction rules, retention templates, industry packs, gap question
                   banks, help articles (data files, versioned)
  migrations/      Alembic revisions
```

### 5.2 Tenancy, identity and permissions
**Tables (new):** `entities`, `units`, `entity_domains`, `memberships`, `sessions`,
`invitations` (extended), `support_access_grants`.

- `organizations` remains the **Group** (tenant root, billing owner).
- Compliance tables gain `entity_id`; `data_records` also `unit_id`.
- **Migration:** each existing organisation receives one default Entity from its `country`
  and `primary_domain`; all rows backfilled; existing users get a Group-scope membership
  equivalent to their current role (`admin`→Admin+Owner for the earliest admin,
  `dpo`→Privacy Officer, `data_owner`→Data Owner).
- **Domain verification:** DNS TXT (`safedata-verify=<token>`) or email to admin@/postmaster@
  the domain. A verified domain belongs to exactly one Group globally. Subdomains supported.
- **Membership:** `(user_id, organization_id, scope_type ∈ {group, entity, unit}, scope_id, role, expires_at)`.
  Visibility = union of scopes, each including descendants.
- **Permission map:** one module (`core/permissions.py`) mapping permission → roles, e.g.
  `records.create`, `records.dispose.request`, `records.dispose.approve`, `categories.manage`,
  `consent.purposes.manage`, `requests.handle`, `breaches.manage`, `billing.manage`,
  `users.manage`, `domains.manage`, `integrations.manage`, `audit.verify`, `evidence.export`.
  Used by route dependencies (`Depends(require("records.dispose.approve"))`), navigation
  builder, and template helper `can("…")`.
- **Request context `ctx`:** user, active group, active scope, visible entity/unit ids,
  permissions, entitlements, locale. Resolved once per request.
- **Scoped queries:** repository helpers filter by group and visible scopes automatically;
  SQLAlchemy `with_loader_criteria` global tenant filter as defence in depth; a test asserts
  every tenant-owned model is covered.
- **Sessions:** server-side table; cookie carries an opaque random id; idle (30 min) and
  absolute (8 h) timeouts kept; revocation, "sign out all devices", session list in Profile;
  all checks fail closed.
- **Email verification** enforced for every new user (fix F4).

### 5.3 Database, migrations, time
- PostgreSQL in staging/production; tests run on PostgreSQL in CI (SQLite allowed for a fast
  local subset only).
- Alembic **baseline revision** generated from current models; startup `ALTER TABLE` and
  `create_all` removed (fix F8). Every change thereafter is a reviewed, reversible revision.
- All datetimes timezone-aware (UTC stored); statutory deadlines computed in the entity's
  timezone.

### 5.4 Background worker
- Separate process `python -m app.worker`; the web process starts no jobs (fix F5).
- Each job acquires a PostgreSQL advisory lock; skipped if held.
- `job_runs` table: job, started, finished, status, counts, error. Admin "System health"
  shows last runs; alert if a job misses its window.
- Intake/dispatch run per organisation according to its entitlements (fix F6).
- Jobs: retention evaluation, reviews, consent expiry/refresh, DSAR & breach clock
  reminders, billing reminders & dunning, lifecycle transitions (read-only, deletion
  warnings, deletion), intake, dispatch, audit-chain verification, housekeeping, backups to
  object storage, FX reference refresh (for price-book review only, never live pricing).

### 5.5 Jurisdiction rules as data
`app/content/jurisdictions/<code>.yaml` per law: DSAR deadline and extension rules, breach
notification window and authority, lawful bases, child age of consent, default retention
templates with citations, regulator name, report labels. Engine and clocks read these
(fix F13). Adding a country = content change + tests.

### 5.6 Storage
Attachments and backups to S3-compatible EU object storage (Cloudflare R2 or DO Spaces),
server-side encrypted, per-tenant prefixes, signed short-lived download URLs; local
filesystem adapter for development (fix F7). Backups per tenant for export, plus whole-DB
managed backups.

### 5.7 Quality bar
Structured JSON logging with request id; no silent exception swallowing; type hints + mypy;
ruff lint/format; pre-commit; GitHub Actions CI (lint, types, tests on Postgres, pip-audit,
secret scan); suite under 2 minutes (fast hashing in tests, transaction-rollback fixtures);
Dependabot; Architecture Decision Records in `docs/adr/`.

### 5.8 Domain portability
Canonical origin, cookie domain, CSP origins, email sender domain, webhook URLs, email link
base, preference-centre host and allowed hosts all from configuration. `LEGACY_HOSTS` +
301 redirect mode for domain moves. Docker image; no host-specific code.

---

## 6. Pricing and billing

### 6.1 Catalogue (Super Admin-managed, versioned)
`products` (retention, consent, suite) → `plans` (starter, growth, enterprise) with
`limits` (entities, users, records, data_subjects, api_calls_per_day) and `features`
(api, integrations, sso_ready, white_label, priority_support, expert_discount).
`services` for one-off/retainer expert work (DPIA, gap assessment, DPO-as-a-service).

**Draft Band A monthly list prices (for stakeholder tuning in the decision pack):**

| | Starter | Growth | Enterprise |
|---|---|---|---|
| Retention | $49 · 1 entity · 5 users · 10k records | $199 · 5 entities · 25 users · 250k records | from $799 · custom |
| Consent | $39 · 5k data subjects | $149 · 100k data subjects | custom |
| Suite | 20% off combined | 20% off combined | custom |

Yearly = 10 × monthly. Categories unlimited on all plans.

### 6.2 Feature inclusion
- All plans: help layers, audit trail, evidence export, gap assessment (in-app), RoPA,
  breach register, requests (DSAR).
- Growth+: DPIA tool, REST API, integrations/intake/dispatch, multiple entities, Auditor role.
- Enterprise: white-label, SSO (when built), SLA, priority support, custom limits.
(Final matrix confirmed in the decision pack.)

### 6.3 Regional bands and price books
- `country_bands` (ISO country → A/B/C/D), sourced from World Bank income classification,
  reviewed yearly.
- `price_books` (plan, interval, currency, band) → amount in minor units. Generated as
  USD × band multiplier × reference FX, rounded to locally natural figures, then **frozen**;
  reviewed quarterly by Super Admin. Changes apply to new subscriptions and renewals with
  notice.
- Display currency from visitor country (D10). Charged band from billing country,
  cross-checked with card issuing country and tax ID; mismatches enter a review queue.
- Equity programmes via application + approval → coupon: NGO/education/public sector
  30–50%; establishing organisations (<2 years, <10 staff) 50% for the first year.

### 6.4 Gateways
`BillingGateway` interface: `create_checkout`, `customer_portal_url`, `change_plan`,
`cancel`, `parse_webhook`. Adapters: `PaystackGateway`, `StripeGateway`. Routing by billing
country (`PAYSTACK_COUNTRIES` config). Webhooks: signature verification, idempotency via
`billing_events` (unique provider event id), our `subscriptions` table is source of truth.
Stripe Tax for VAT/GST and reverse charge; Nigerian VAT on Paystack invoices. Invoices:
PDF, sequential numbering per selling entity.

### 6.4a Billing-exempt organisations
- **Internal:** 3Consulting's own Group is never billed: no checkout, no reminders, no plan
  limits, no lifecycle transitions. Used for 3Consulting's own compliance, demos and training.
- **Complimentary:** Platform Owner/Super Admin may comp any organisation (pilots, partners,
  sponsored NGOs) with a chosen plan, optional end date and reason; reminders start 14 days
  before the end date. Every grant, change and expiry is audit-logged on the platform.
- Implemented as `organizations.billing_mode ∈ {standard, internal, complimentary}` plus
  `comp_plan_id`, `comp_ends_at`, `comp_reason`, `comp_granted_by`.

### 6.5 Subscription lifecycle and reminders
States: `trialing → active → past_due (7-day grace) → read_only → cancelled → scheduled_deletion → deleted`.
- Read-only: view, export, approvals, legal holds and dual-approval safeguards keep working;
  no new records/consents. Billing never blocks safety-critical actions.
- Entitlement limits: warn at 80%, block new creation at 100% with upgrade path.

| Situation | Reminders (email + in-app banner, Owners & billing contacts only) |
|---|---|
| Trial | day 7, 11, 13, expiry day, +3, +7 |
| Yearly renewal | 30, 7, 1 days before |
| Card expiry | 30, 7 days before |
| Payment failed | day 0, 3, 7 |
| Read-only workspace | weekly ×4, then monthly |
| Before deletion | 30, 7, 1 days before |

| Workspace state | Kept for |
|---|---|
| Trial never converted | 90 days read-only → deletion after warnings |
| Lapsed paid | 12 months read-only, export always available → deletion after warnings |
| Cancelled by choice | 90 days → deletion after warnings |
| Invoices / billing records | 6 years after deletion (tax law) |
| Dormant user accounts | deactivated after 12 months inactivity (not deleted) |

All durations configurable by Super Admin.

---

## 7. Experience

### 7.1 Brand and visual system
- Lifecycle Ring mark (SVG): full lockup, mark-only, favicon (16/32/180/512), light/dark,
  monochrome; wordmark "SafeData" + "by 3Consulting".
- Type: Geist (UI), Fraunces (marketing headlines and report covers), Geist Mono (refs,
  dates, tabular figures). Self-hosted.
- Tokens on `:root` with light/dark sets: canvas warm off-white, sidebar ink-navy, action
  orange (3Consulting), status teal/amber/red with icon + label.
- Voice: calm, precise, plain-language; exact dates and consequences; legal term as
  secondary text; no fear selling, no fake urgency.
- All inline styles replaced by tokens/components (fix F16).

### 7.2 App shell
☰ toggles sidebar full ↔ icon rail (persisted per user); mobile off-canvas drawer with focus
trap; organisation switcher (Group › Entity › Unit) at top; collapsible groups
**Home · Retention · Consent · Requests & Governance · Admin**; product-aware (unpurchased
product shows one upsell card); Ctrl+K command palette; notifications drawer; theme toggle;
help drawer; breadcrumb reflecting scope.

### 7.3 Role homes
| Role | Home |
|---|---|
| Owner/Admin | Posture across entities, plan usage, setup gaps |
| Privacy Officer | Work queue: approvals, request deadlines, breach clocks, reviews |
| Data Owner | My records due, review tasks, one-click responses |
| Contributor | Add/import, recent submissions |
| Auditor | Evidence room: read-only, audit-chain verify, evidence packs |
| Viewer | Board dashboard, printable reports |
Each home has a "Next best step" card. A full role × level × product × plan visibility
matrix is produced in Phase 0 and enforced by tests.

### 7.4 Onboarding
One question per screen, in human terms, branching, smart defaults (IP country, org name
from domain, industry ordered by country prevalence), live workspace preview panel, under 3
minutes, resumable, skippable; ends with a personalised 30-day plan and a persistent setup
checklist (Lifecycle Ring progress). Questions cover: inventory maturity, industry,
countries/entities, products, data categories (from industry pack, editable). Establishing
→ starter inventory + gap assessment + policy templates. Established → import, API, entity
mapping, invites.

### 7.5 Help system (nine layers)
1 jurisdiction-aware legal-term explainers · 2 per-page help drawer (articles from the
existing manual, restructured, searchable via Ctrl+K) · 3 role-based guided tours ·
4 field guidance with recommended values and citations · 5 smart warnings · 6 teaching empty
states with "set this up for me" · 7 contact support with page context / book an expert ·
8 public Help Centre (same content) · 9 in-app release notes.
**Shared-responsibility map** per workspace: what SafeData automates vs what the
organisation must do, each linked to help and the screen where it is done.

### 7.6 Accessibility and i18n
WCAG 2.2 AA, keyboard-complete, reduced-motion respected. All strings via gettext-style
catalog (Babel); locale-aware formatting.

### 7.7 Public site
Landing, pricing (auto currency), product pages, free gap check, Trust Centre (security,
sub-processors, DPA, status), Help Centre, legal pages. Buildable as static pages for
optional hosting on shared hosting.

---

## 8. Consent hub and governance modules

### 8.1 Consent
Entities own **purposes** (lawful basis, retention link) and **notices** (versioned text).
**Collection points** describe where consent is captured. Capture via JS snippet, REST API,
hosted preference centre, CSV import, scanned paper upload. **Consent records**: subject
reference = HMAC-SHA256(normalised identifier, per-entity secret), purpose, status
(granted/withdrawn/expired), notice version, method, source, timestamp, receipt hash
(chained). Encrypted email only while needed (preference links, receipts), auto-purged.
**Receipts** downloadable/emailed, verifiable on a public verify page. **Preference centre**:
branded per entity, magic-link access, toggles create records. **Withdrawal** emits webhooks
to customer systems and starts disposal clocks for records whose basis is that consent
(existing `consent_withdrawal` trigger). **Children**: age threshold per jurisdiction,
parental-consent flag. **Refresh**: re-confirmation after configurable period. Reports:
consent rate, withdrawals, regulator proof pack.

### 8.2 Requests (DSAR)
Intake via public form (preference centre), email-in, manual. Identity verification first.
Deadline from jurisdiction rules incl. extension. Tasks to Units/Data Owners. Erasure routed
through retention engine honouring legal holds and obligations, with explained exemptions.
Response pack generation.

### 8.3 DPIA, Gap Assessment, Breach, RoPA, Vendors, Policy
- DPIA: screening → full assessment, likelihood × severity, mitigations, DPO sign-off,
  review date, links to RoPA.
- Gap Assessment: 60–80 questions per law across governance, lawful basis, rights, security,
  retention, vendors, breaches, transfers; area scores; remediation tasks. Public free
  version: 15 questions, emailed result (captured through SafeData's own consent hub).
- Breach register: jurisdiction clocks, severity, notify/not-notify decision log, templates.
- RoPA + Vendors register (processors consolidated from category fields), DPA refs, reviews.
- Retention policy generator (PDF/DOCX) from the live schedule.
- "Have 3Consulting do this" service entry points (band-priced quote/checkout).

---

## 9. Platform administration
Platform Owner bootstrap command (`python -m app.cli create-platform-owner`), interactive,
never reads a password from code/env files. Super Admin portal: tenants, plans, price books,
bands, coupons and equity approvals, billing review queue, service requests, lifecycle
settings, job health, MRR/churn dashboard. Support access: customer-granted, time-boxed,
read-only by default, logged in the tenant's audit trail.

---

## 10. Operations and security
- Environments: local (Docker Compose: app, worker, Postgres, Mailpit), staging, production
  (Render Frankfurt behind Cloudflare).
- Backups: managed Postgres PITR (7 days) + nightly encrypted logical dump to separate
  provider; quarterly restore drill; RPO minutes, RTO 4 h.
- Email: EU transactional provider (Postmark or Brevo), SPF/DKIM/DMARC on
  `mail.safedata.3consult-ng.com`.
- Monitoring: Sentry (EU), uptime monitor + public status page, missed-job alerts,
  30-day structured logs.
- Security: OWASP ASVS L2 as audit baseline; secrets only in host env; key rotation runbook;
  Dependabot; security.txt and disclosure policy; external penetration test before first
  enterprise sale.
- Estimated launch running cost: ~$70–$130/month (itemised in decision pack).

## 11. Legal pack (drafts for lawyer review)
Terms of Service, Privacy Policy, Cookie Policy, Data Processing Agreement with transfer
mechanisms (EU SCCs, UK IDTA, NDPA), sub-processor list, SLA, Acceptable Use Policy.

## 12. Documentation set
**Stakeholders:** executive decision pack; full audit report (14 dimensions, severity,
fix + phase); pricing & packaging (plans, bands, price books, unit economics, competitors);
hosting/domain/cost model; Consent Management explained; go-to-market & launch checklist;
refreshed one-pager and deck.
**Developers:** README; architecture guide with diagrams; setup & coding standards; data
model & migrations; tenancy & permissions; billing integration; API reference (OpenAPI),
webhooks, JS snippet; jurisdiction rule authoring; ops runbook (deploy, rollback, restore,
incidents, key rotation, domain migration); testing guide; ADRs.
**Customers:** role-based Help Centre; Owner billing guide; Admin guide.
Existing `Documents/01–06` rewritten to match reality.

---

## 13. Audit framework (Phase 0 deliverable, re-run in Phase 6)
1 Product & UX (every role × level × product × plan; onboarding; help) · 2 Compliance
correctness per jurisdiction · 3 SafeData's own legal posture · 4 Security (ASVS L2) ·
5 Engineering & architecture · 6 Data & database · 7 Testing & QA · 8 Performance & scale ·
9 Reliability & operations · 10 DevOps & SDLC · 11 Billing & commercial logic ·
12 Accessibility & i18n · 13 Documentation accuracy · 14 Go-to-market, support model, IP
ownership clarity.
Each finding: id, dimension, severity (Critical/High/Medium/Low), evidence (file:line or
screenshot), user/business impact, fix, phase, verification method.

---

## 14. Phases

| Phase | Deliverables | Exit criteria |
|---|---|---|
| **0 Audit & decision pack** | Full 14-dimension audit report; role×level×product×plan matrix; decision pack (pricing with price books, hosting/domain/cost, consent explainer, competitor view, legal-entity question for Stripe). | Stakeholder-readable; every finding has severity, fix and phase. |
| **1 Foundations** | Postgres + Alembic baseline; worker with locks + `job_runs`; hierarchy tables + migration; memberships + permission map + `ctx` + scoped queries; server-side sessions; fixes F2–F8, F10, F11, F15, F18; object storage; jurisdiction rules engine; i18n scaffolding; CI; fast tests; code restructure of touched modules. | All existing tests + new tenancy/permission tests pass on Postgres in CI; cross-tenant isolation tests pass. |
| **2 Design system & shell** | Brand assets; tokens; components; app shell; role homes; onboarding (both journeys); help layers 1–6; redesigned retention screens; public site & pricing page; accessibility pass. | Every role × level journey renders and is keyboard-complete; visual review approved. |
| **3 Billing** | Catalogue, bands, price books, gateways (Paystack, Stripe), webhooks, entitlements, lifecycle states, reminders, invoices, tax, Super Admin billing tools, equity programmes. | End-to-end test-mode purchases in ≥4 currencies via both gateways; lifecycle simulated through deletion. |
| **4 Consent & Requests** | Consent hub, preference centre, snippet + API, receipts and verify page, withdrawal→retention link, DSAR inbox. | Capture→withdraw→disposal-clock flow tested end-to-end; DSAR deadlines correct per jurisdiction. |
| **5 Governance** | DPIA, gap assessment (in-app + public), breach register, RoPA + vendors, policy generator, expert-service booking, help layers 7–9. | Modules complete per §8.3 with tests. |
| **6 Re-audit & go-live** | Re-run audit; pen test & fixes; restore drill; load test; legal pack reviewed; developer/customer docs; deployment to production on `safedata.3consult-ng.com`. | All Critical/High closed; go-live checklist signed. |

Each phase receives its own implementation plan (writing-plans) before work starts.
Phase 0 and Phase 1 run first; Phase 0 documents are produced while Phase 1 foundations
are built.

## 15. Stakeholder decisions still open (each with the recommended answer)

| # | Decision | Recommendation |
|---|---|---|
| S1 | Legal entity for Stripe | Form a **UK private limited company** with the director's identity verifying a Stripe **business** account (see D11); not a personal account. Stripe Atlas (US) only if US fundraising is planned. If Phase 0 confirms Paddle (Merchant of Record) pays out to Nigeria, it may replace the UK entity. Paystack covers launch meanwhile, so this does not block go-live. |
| S2 | Plan limits and Band A prices | Adopt the §6.1 drafts as launch prices; review after the first 20 paying customers or 90 days, whichever comes first, using real usage data. |
| S3 | Standalone domain | Register the best available short `.com` for SafeData now, plus defensive `.co.uk` and `.ng` variants (low annual cost). Keep it parked until migration. |
| S4 | Old `.db` files in Git history (F19) | Phase 0 inspects the blobs first. If they hold only seed/test data and the repository is private, **keep history** (no rewrite). If any real personal data is found, rewrite history with `git filter-repo`, force-push, rotate every secret, and have collaborators re-clone. |
| S5 | IP ownership | Put a written IP assignment or licence in place between 3Consulting and every contributor before selling; Phase 0 also produces a third-party dependency licence inventory. Commercial terms with contributors are a separate business matter. |
| S6 | Support model | Launch with email + in-app support requests, business hours (WAT), first response within 1 business day; Enterprise SLA with 4-hour response for critical issues; live chat after launch once volume justifies it. |

## 16. Risks (with the recommended mitigation for each)

| # | Risk | Recommended mitigation |
|---|---|---|
| R1 | Programme scope is large | Strict phase gates with written exit criteria (§14). **Launch cut-line:** Phases 0–3 plus Consent capture/withdrawal from Phase 4 form a sellable launch; the rest ships in order after go-live. Definition of done includes tests, docs and re-audit item. |
| R2 | **Retention engine disposes of data wrongly** (the highest product-liability risk) | Keep and extend the dual-approval safeguard and its regression test; dry-run mode, emergency freeze and legal holds on every disposal path; SafeData records and instructs disposal but source-system deletion is confirmed back, never assumed; disposal evidence kept; liability cap in Terms; professional indemnity insurance. |
| R3 | Cross-tenant data leak | Central scoped-query layer + global SQLAlchemy tenant filter + an automated isolation test for every tenant-owned model + penetration test before first enterprise sale. |
| R4 | SafeData itself is breached | Data minimisation (D15); app-level encryption for emails, TOTP secrets and API secrets; 2FA mandatory for Owners, Admins, Privacy Officers and platform staff; least-privilege roles; Cloudflare WAF; written incident-response plan using SafeData's own breach register and 72-hour workflow; cyber insurance. |
| R5 | Hierarchy migration corrupts tenant data | Full database snapshot before migrating; reversible Alembic revision; rehearsal on an anonymised copy of production in staging; row-count, ownership and isolation assertions; documented rollback runbook; run in a maintenance window. |
| R6 | Legal-content inaccuracy | Rules files carry citations and a review-by date; jurisdiction content and legal pack reviewed by qualified counsel before launch; help labelled "guidance, not legal advice"; disclaimer in Terms; professional indemnity insurance. |
| R7 | Laws change after launch | Rules as versioned data with owners and review dates; quarterly legal-content review; customer-facing change log and in-app notice when a rule affecting their schedule changes; affected records queued in the existing recalculation flow, never silently re-dated. |
| R8 | Stripe unavailable to the Nigerian entity | Go live on Paystack with international cards enabled (worldwide sales from day one); form a UK Ltd in parallel and connect Stripe when approved; the gateway abstraction makes the switch configuration-only. Phase 3 builds and tests both adapters regardless. |
| R9 | Pricing perceived unfair or gamed | Band from verified billing country cross-checked with card country and tax ID; review queue instead of silent blocking; equity programmes; frozen, rounded local prices; published pricing principles on the pricing page. |
| R10 | Currency volatility (e.g. naira devaluation) | Quarterly price-book review with a documented trigger (move >10% in reference FX); Paystack USD settlement option; yearly plans locked at purchase price for their term. |
| R11 | Payment fraud and chargebacks | 3-D Secure on all card payments; Stripe Radar and Paystack fraud tools; trial requires no card, so stolen cards gain nothing; clear billing descriptor ("SAFEDATA 3CONSULTING"). |
| R12 | Hosting outage or vendor lock-in | Docker image + standard PostgreSQL + S3-compatible storage; off-site encrypted backups with a separate provider; tested runbook to restore on an alternative provider within the 4-hour RTO; public status page. |
| R13 | Key-person dependency | Developer docs, ADRs, CI, runbooks and a clean architecture so a second developer can onboard from the docs alone; Platform Owner plus at least one further Super Admin with personal logins; break-glass codes stored offline. |
| R14 | Slow adoption / low conversion | Free public gap check (lead magnet and SEO), no-card trial, establishing-organisation discount, 3Consulting's existing consulting clients as first channel, funnel analytics (privacy-respecting, first-party only) reviewed monthly. |
