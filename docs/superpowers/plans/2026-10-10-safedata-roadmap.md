# SafeData Launch Programme — Plan Roadmap

**Spec:** `docs/superpowers/specs/2026-10-10-safedata-launch-programme-design.md`

This file indexes every implementation plan for the programme and fixes their order.
Plans for Phases 2–6 are written in full when their predecessor is merged, so they are
written against the code as it then exists (the Phase 1 refactor changes file layout,
names and fixtures that later plans depend on). Their scope, task list and exit criteria
are fixed here so nothing in the spec is lost.

## Order and dependencies

```
Phase 0  Audit & decision pack ─────────────┐ (documents; runs in parallel with 1A)
Phase 1A Platform foundations ──► 1B Tenancy & permissions ──► 1C Compliance core
                                                                   │
                     ┌─────────────────────────────────────────────┘
                     ▼
Phase 2  Design system, shell, onboarding, help ──► Phase 3 Billing
                                                       │
                     Phase 4 Consent & Requests ◄──────┘
                     Phase 5 Governance modules
                     Phase 6 Re-audit, pen test, docs, go-live
```

| Plan file | Status |
|---|---|
| `2026-10-10-phase0-audit-decision-pack.md` | Written |
| `2026-10-10-phase1a-platform-foundations.md` | Written |
| `2026-10-10-phase1b-tenancy-permissions.md` | Written |
| `2026-10-10-phase1c-compliance-core.md` | Written |
| Phase 2 – 6 plans | Outlined below; full plan written when predecessor merges |

## Phase 2 — Design system, shell, onboarding, help (outline)

Exit: every role × level journey renders, keyboard-complete, visual review approved.

1. Brand assets: Lifecycle Ring SVG (lockup, mark, favicons 16/32/180/512, light/dark/mono), wordmark; `app/static/brand/`.
2. Self-hosted fonts (Geist, Geist Mono, Fraunces) + `tokens.css` (light/dark), base + component CSS; remove Bootstrap theme overrides that conflict.
3. Vendored HTMX + Alpine.js (pinned, SRI) and CSP update (no `unsafe-inline` styles once inline styles are gone).
4. Jinja component macros: button, badge/status (icon + word), card, table, empty state, form field with guidance, ring countdown, modal/confirm with consequence text, toast.
5. App shell: collapsible sidebar (full ↔ rail, persisted via user preference), mobile drawer with focus trap, org/scope switcher, nav built from permission map + entitlements, Ctrl+K palette (routes + records search endpoint), notifications drawer, theme toggle, help drawer.
6. Role homes (Owner/Admin, Privacy Officer, Data Owner, Contributor, Auditor evidence room, Viewer) + "Next best step" service with tests per role.
7. Onboarding flow (one question per screen, branching, live preview, resumable) + industry packs in `app/content/industries/` + 30-day plan + setup checklist.
8. Help layers 1–6: glossary (jurisdiction-aware), page help drawer from restructured manual articles (`app/content/help/`), guided tours, field guidance with cited recommended values, smart warnings, teaching empty states; shared-responsibility map page.
9. Redesign retention screens: inventory/records list + detail, categories/schedules, disposals queue, legal holds, imports, reports, audit ledger; replace all 251 inline styles.
10. Public site: landing, product pages, pricing (auto currency, D10), Trust Centre, Help Centre, legal page shells; static export command for optional shared hosting.
11. Accessibility pass (axe-core in Playwright), reduced motion, contrast checks both themes.
12. Playwright visual journey suite: screenshot every role × level home and key page.
13. Entity & unit management screens (create/rename/archive entities and units, assign entity DPO, entity timezone) and the scope switcher wired to `/context/switch` and entity filters.
14. Support access (spec §9): `support_access_grants` (customer-granted, time-boxed, read-only by default), platform "request access" flow, banner inside the tenant while support is present, every support action written to the tenant's audit chain.
15. System health page for Admins (last `job_runs` per job, backup status) and missed-job alert job.

## Phase 3 — Billing (outline)

Exit: test-mode purchases in ≥4 currencies via Paystack and Stripe; lifecycle simulated to deletion.

1. Catalogue models + admin: products, plans, limits, features, services (versioned).
2. `country_bands` seed (World Bank groups) + `price_books` generator command (USD × band × reference FX → rounded, frozen) + review UI.
3. Entitlements service (`ctx.entitlements`), 80% warning / 100% block, never blocking reads/exports/holds/approvals.
4. `subscriptions`, `billing_events` (idempotent), `invoices` models; lifecycle state machine with tests for every transition incl. internal/complimentary (§6.4a).
5. `BillingGateway` interface + `PaystackGateway` (checkout, plans, webhook signature, customer manage link) + `StripeGateway` (Checkout, Customer Portal, Stripe Tax, webhook) + routing by billing country; Paddle adapter only if Phase 0 confirms Nigerian payouts.
6. Billing-country verification (card country, tax ID) + review queue.
7. Reminder schedules (§6.5) as worker jobs with email templates; banners.
8. Invoice PDF with sequential numbering per selling entity; tax lines.
9. Equity programmes: application form, evidence upload, approval → coupon.
10. Super Admin: plans, price books, bands, coupons, comp grants, billing review, MRR/churn.
11. Pricing page wired to price books; checkout UX in local currency with "≈ USD".

## Phase 4 — Consent & Requests (outline)

Exit: capture → withdraw → disposal clock end-to-end; DSAR deadlines correct per jurisdiction.

1. Models: purposes, notices (versioned), collection points, consent records (HMAC subject ref), receipts (chained), encrypted contact store with purge job.
2. Capture: REST endpoints (API key scoped), JS snippet (served from `/c/v1/snippet.js`, CSP-safe, no cookies), CSV import, paper-form upload.
3. Preference centre (per entity branding, magic link, toggles) + public receipt verify page.
4. Withdrawal pipeline: webhook to customer systems, link to retention `consent_withdrawal` trigger, audit.
5. Children: jurisdiction age thresholds, parental flag. Refresh/expiry job.
6. Consent reports + regulator proof pack export.
7. DSAR inbox: public form, email-in address, identity verification, jurisdiction deadlines + extension, task assignment, erasure via retention engine with exemptions, response pack.

## Phase 5 — Governance modules (outline)

Exit: modules complete per spec §8.3 with tests.

1. DPIA (screening → full, scoring, mitigations, sign-off, review date, RoPA links).
2. Gap assessment: question banks per law (`app/content/gap/`), scoring by 8 areas, remediation tasks; public 15-question version with consent-captured email.
3. Breach register with jurisdiction clocks, decision log, notification templates.
4. RoPA polish + Vendors register (migrate processor fields from categories).
5. Retention policy generator (PDF/DOCX from live schedule).
6. Expert-service entry points (quote/checkout via Phase 3 catalogue).
7. Help layers 7–9 (contact with page context, public Help Centre build, release notes).

## Phase 6 — Re-audit and go-live (outline)

Exit: all Critical/High closed; go-live checklist signed.

1. Re-run the Phase 0 audit checklist; record closure evidence per finding.
2. Load test (Locust) at 10× expected launch volume; fix hotspots.
3. External penetration test; fix findings.
4. Restore drill from off-site backup to a fresh environment; record RPO/RTO achieved.
5. Legal pack finalised after counsel review; Trust Centre published.
6. Developer, admin and customer documentation complete and accurate.
7. Production deploy to `safedata.3consult-ng.com`: Cloudflare, Render (Frankfurt), Postgres, R2, email DNS (SPF/DKIM/DMARC), Sentry, status page; Platform Owner bootstrap; smoke test; go-live checklist.
