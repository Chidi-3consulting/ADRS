# Graph Report - SafeData  (2026-08-17)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 777 nodes · 2468 edges · 40 communities (35 shown, 5 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 361 edges (avg confidence: 0.51)
- Token cost: 2,548 input · 434 output

## Graph Freshness
- Built from commit: `2a8604fa`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Data Disposal Management
- Enterprise Integration Logic
- Compliance Reporting Engine
- User Account Management
- Data Governance Helpers
- ROPA and Integrations
- Database Migrations
- Authentication Flow
- Database Schema Definitions
- Database Backup System
- Organization Billing Logic
- Public API Endpoints
- Email Verification System
- Login Rate Limiting
- Audit Chain Verification
- Security Middleware
- Auth Configuration and Testing
- System Setup Wizard
- Data Housekeeping Tasks
- Core Data Models
- Application Entry Point
- Background Task Scheduler
- Password Policy Enforcement
- Session and CSRF Middleware
- Platform Administration
- Organization Invitations
- Dashboard UI Views
- Data Import Testing
- PDF Documentation Generator
- Governance UI Components
- Admin UI Templates
- Public UI Templates
- System Branding
- Product Tiers
- System Documentation
- Category Management UI
- Bulk Data Import
- Compliance Reports

## God Nodes (most connected - your core abstractions)
1. `get_session()` - 109 edges
2. `DataRecord` - 98 edges
3. `DataCategory` - 87 edges
4. `log_audit()` - 73 edges
5. `get_country_regulation_labels()` - 57 edges
6. `User` - 55 edges
7. `Organization` - 42 edges
8. `SystemSetting` - 27 edges
9. `ConnectedSystem` - 25 edges
10. `execute_disposal()` - 20 edges

## Surprising Connections (you probably didn't know these)
- `_seed_category()` --uses--> `DataCategory`  [INFERRED]
  retention_py/tests/test_import.py → retention_py/app/models.py
- `run_retention_checks()` --uses--> `CategoryRetentionRule`  [INFERRED]
  retention_py/app/engine.py → retention_py/app/models.py
- `clone_category_retention_rules()` --uses--> `CategoryRetentionRule`  [INFERRED]
  retention_py/app/helpers.py → retention_py/app/models.py
- `provision_org_categories()` --uses--> `CategoryRetentionRule`  [INFERRED]
  retention_py/app/helpers.py → retention_py/app/models.py
- `view_category_details()` --uses--> `CategoryRetentionRule`  [INFERRED]
  retention_py/app/routes/categories.py → retention_py/app/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **API & External Systems Integration** — app_templates_integrations_html, app_templates_import_html, app_templates_help_html [EXTRACTED 0.90]
- **Data Lifecycle Management Flow** — app_templates_categories_html, app_templates_records_html, app_templates_recalculations_html, app_templates_dashboard_html [EXTRACTED 0.95]
- **Administrative Management Interface** — retention_py_app_templates_settings, retention_py_app_templates_users, retention_py_app_templates_ropa_view [INFERRED 0.80]
- **Authentication & Identity Templates** — retention_py_app_templates_twofa_challenge, retention_py_app_templates_verify_email, retention_py_app_templates_setup [INFERRED 0.80]

## Communities (40 total, 5 thin omitted)

### Community 0 - "Data Disposal Management"
Cohesion: 0.06
Nodes (75): approve_disposal(), calculate_retention_end_date(), execute_disposal(), lift_legal_hold(), log_consent_withdrawal(), Execute disposal of a single record. Transactional, idempotent, legal-hold-…, Lift legal hold from a record. Returns True if lifted, False if not held., Record consent withdrawal on a record (B1). The engine will auto-dispose after… (+67 more)

### Community 1 - "Enterprise Integration Logic"
Cohesion: 0.06
Nodes (66): api_key_can(), auto_categorize(), _compute_retention_end(), create_api_key(), enqueue_intake(), generate_api_key(), _get_setting(), intake_is_duplicate() (+58 more)

### Community 2 - "Compliance Reporting Engine"
Cohesion: 0.05
Nodes (70): build_compliance_report(), build_ndpr_report(), compliance_metrics(), compliance_report_to_csv_rows(), compliance_score(), compliance_scorecard_details(), create_notification(), dismiss_onboarding_notifications() (+62 more)

### Community 3 - "User Account Management"
Cohesion: 0.10
Nodes (55): consume_recovery_code(), generate_recovery_codes(), totp_code(), totp_generate_secret(), totp_uri(), User, clear_read_notifications(), create_user() (+47 more)

### Community 4 - "Data Governance Helpers"
Cohesion: 0.08
Nodes (48): parametrize, clone_category_retention_rules(), detect_visitor_currency(), email_layout(), email_password_reset(), email_team_invite(), _escape_html(), get_country_regulations() (+40 more)

### Community 5 - "ROPA and Integrations"
Cohesion: 0.17
Nodes (49): current_user(), get_session(), Request, get_country_regulation_labels(), ConnectedSystem, FieldMapping, Linked processor sub-entries for a ROPA entry (third-party processors)., RopaEntry (+41 more)

### Community 6 - "Database Migrations"
Cohesion: 0.08
Nodes (32): SafeData Alembic Migration Environment. Connects Alembic to the SQLAlchemy models…, Run migrations in 'offline' mode — generates SQL script without DB connection., Run migrations in 'online' mode — connects to DB and applies directly., run_migrations_offline(), run_migrations_online(), get_db(), get_framework_badge(), PendingRecalculation (+24 more)

### Community 7 - "Authentication Flow"
Cohesion: 0.18
Nodes (29): build_session_data(), Build the canonical session dict from a User + Organization ORM row. Includes…, email_verification(), Email verification for new registrations. Returns (subject, html)., send_system_email(), totp_verify(), handle_2fa(), handle_forgot_password() (+21 more)

### Community 8 - "Database Schema Definitions"
Cohesion: 0.26
Nodes (20): `api_keys`, `attachments`, `audit_log`, `auto_categorization_rules`, `connected_systems`, `consent_signals`, `data_categories`, `data_records` (+12 more)

### Community 9 - "Database Backup System"
Cohesion: 0.15
Nodes (18): backup_database(), prune_backups(), Session, SafeData Backup System Provides: logical database dump (pure-Python, no external…, Delete backup files (and their log rows) older than `days`. Returns count…, Dump the whole database to a .sql file in backup_dir. Returns {'file': str,…, BackupLog, Test backups. Tests database backup and pruning. (+10 more)

### Community 10 - "Organization Billing Logic"
Cohesion: 0.15
Nodes (16): Organization, Test billing. Tests organization access + trial expiry logic., Active subscription should have access., Suspended org should not have normal access., Trial with future ends_at should have access., Trial with past ends_at should be expired., Trial with no ends_at should have indefinite access., test_active_subscription_has_access() (+8 more)

### Community 11 - "Public API Endpoints"
Cohesion: 0.27
Nodes (18): BaseModel, api_consent_withdraw(), api_health(), api_ingest(), api_ingest_batch(), api_list_categories(), api_record_status(), api_records_disposed() (+10 more)

### Community 12 - "Email Verification System"
Cohesion: 0.21
Nodes (16): issue_email_verification_token(), Generate a random verification token, store its SHA-256 hash as a PasswordReset…, Validate an email verification token, mark the user's email as verified (clear…, verify_email_token(), _create_user(), Test email verification. Tests token generation, verification, and expiry., Should generate a verification token and store its hash., Valid token should verify and mark user as email verified. (+8 more)

### Community 13 - "Login Rate Limiting"
Cohesion: 0.19
Nodes (13): login_throttle_seconds(), Session, Record a login attempt (success or failure). Never throws — throttling must not…, Seconds the caller must wait before retrying, or 0 if not throttled. Locks…, record_login_attempt(), Test login throttle. Tests brute-force login prevention., Should not throttle when under 5 attempts., Should throttle after 5 failed attempts. (+5 more)

### Community 14 - "Audit Chain Verification"
Cohesion: 0.15
Nodes (16): audit_norm_details(), Normalise details to a canonical, key-sorted JSON string ., Walk the audit_log hash chain and verify integrity. Returns {'ok': bool,…, verify_audit_chain(), Test audit chain integrity. Tests the SHA-256 hash chain write + verification., Single audit log entry should verify correctly., Multiple sequential audit log entries should all verify., Tampering with a row hash should break the chain. (+8 more)

### Community 15 - "Security Middleware"
Cohesion: 0.13
Nodes (14): BaseHTTPMiddleware, _constant_time_compare(), _csrf_field_html(), CSRFMiddleware, _generate_csrf_token(), Request, Hidden input for Jinja2 templates., - On every request: ensure the session contains a CSRF token. - On mutating… (+6 more)

### Community 16 - "Auth Configuration and Testing"
Cohesion: 0.19
Nodes (10): fixture, hash_password(), SafeData Authentication Provides: password hashing/verification, session management…, verify_password(), auth_header(), auth_user(), client(), db() (+2 more)

### Community 17 - "System Setup Wizard"
Cohesion: 0.19
Nodes (14): Check if initial setup has been completed (system_settings key)., setup_is_complete(), SystemSetting, Test setup wizard. Tests setup_is_complete, and the POST /setup flow., Setup should not be complete without the system setting., Setup should be complete after setting the flag., Setup should not be complete if value is not '1'., GET /setup should return 200 when setup is not complete. (+6 more)

### Community 18 - "Data Housekeeping Tasks"
Cohesion: 0.26
Nodes (13): Daily housekeeping: prune rows that would otherwise grow unbounded. Returns…, run_housekeeping(), LoginAttempt, PasswordReset, Housekeeping prunes old login attempts, password resets, and read notifications., test_housekeeping(), Test housekeeping. Tests pruning of stale login_attempts, password_resets, and…, Login attempts older than 30 days should be pruned. (+5 more)

### Community 19 - "Core Data Models"
Cohesion: 0.27
Nodes (11): Base, AuditLog, BreachIncident, ConsentReceipt, DpiaAssessment, DsarRequest, EnterpriseLicenceKey, ImportJob (+3 more)

### Community 20 - "Application Entry Point"
Cohesion: 0.23
Nodes (9): exception_handler, not_found_handler(), _patched_template_response(), get, Request, SafeData Python Engine — main application entry point. Registers FastAPI app with:…, redirect_exception_handler(), server_error_handler() (+1 more)

### Community 21 - "Background Task Scheduler"
Cohesion: 0.17
Nodes (12): FastAPI, backup_scheduler_task(), disposal_dispatch_scheduler_task(), housekeeping_scheduler_task(), intake_queue_scheduler_task(), lifespan(), Run retention engine checks every 10 minutes., Run housekeeping once per hour. (+4 more)

### Community 22 - "Password Policy Enforcement"
Cohesion: 0.29
Nodes (10): password_policy_error(), Returns an error message if password fails policy, else None. Policy: min 10…, Test password policy. Tests password strength enforcement., test_empty_password(), test_minimum_length(), test_no_letters(), test_no_numbers(), test_too_short() (+2 more)

### Community 23 - "Session and CSRF Middleware"
Cohesion: 0.27
Nodes (8): clear_session(), Response, set_session(), _path_is(), SafeData Security Middleware Provides: 1. Security response headers (CSP with…, True if path matches or starts with any of the given prefixes., Register csrf_token() and csrf_field() as Jinja2 global functions so templates…, register_csrf_template_globals()

### Community 24 - "Platform Administration"
Cohesion: 0.36
Nodes (9): PaymentTransaction, handle_set_org_status(), get, post, Request, Session, require_platform_admin(), view_platform_dashboard() (+1 more)

### Community 25 - "Organization Invitations"
Cohesion: 0.31
Nodes (8): OrganizationInvitation, Test invitations. Tests invite create, accept, and revoke., Should create an invitation record., Expired invitation should be detectable., Revoked invitation should have revoked_at timestamp set., test_create_invitation(), test_invitation_expiry(), test_revoke_invitation()

### Community 26 - "Dashboard UI Views"
Cohesion: 0.32
Nodes (8): Billing & Subscription Template, Categories & Schedules List, View Data Category Details, Compliance Dashboard, Integrations & API Hub, Main Application Layout, Data Retention Register, Record of Processing Activities (ROPA)

### Community 27 - "Data Import Testing"
Cohesion: 0.29
Nodes (6): Test import records. Tests CSV import validation + processing., CSV upload endpoint should be accessible., Import job should be created and tracked., _seed_category(), test_import_csv_endpoint(), test_import_job_model()

### Community 28 - "PDF Documentation Generator"
Cohesion: 0.50
Nodes (4): convert_md_to_pdf(), main(), SafeData Documentation — Markdown to PDF Converter Converts all .md files in this…, Convert a single markdown file to PDF.

### Community 29 - "Governance UI Components"
Cohesion: 0.50
Nodes (4): Create Data Category Form, Pending Recalculations, Record Details & Governance, Four-Eyes (Dual-Approval) Safeguard

### Community 30 - "Admin UI Templates"
Cohesion: 0.50
Nodes (4): Layout Template, ROPA View Template, Settings Template, User Management Template

### Community 31 - "Public UI Templates"
Cohesion: 0.50
Nodes (4): Public Layout Template, Setup Template, 2FA Challenge Template, Email Verification Template

### Community 32 - "System Branding"
Cohesion: 0.67
Nodes (3): SafeData (SafeData), SafeData Core, SafeData Enterprise

## Knowledge Gaps
- **21 isolated node(s):** ``password_resets``, ``system_settings``, `Billing & Subscription Template`, `View Data Category Details`, `Record of Processing Activities (ROPA)` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DataRecord` connect `Data Disposal Management` to `Enterprise Integration Logic`, `Compliance Reporting Engine`, `User Account Management`, `Data Governance Helpers`, `Database Migrations`, `Organization Billing Logic`, `Public API Endpoints`, `Auth Configuration and Testing`, `Core Data Models`, `Platform Administration`, `Data Import Testing`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Why does `DataCategory` connect `Data Governance Helpers` to `Data Disposal Management`, `Enterprise Integration Logic`, `Compliance Reporting Engine`, `User Account Management`, `ROPA and Integrations`, `Database Migrations`, `Authentication Flow`, `Organization Billing Logic`, `Public API Endpoints`, `Auth Configuration and Testing`, `Core Data Models`, `Data Import Testing`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Why does `get_session()` connect `ROPA and Integrations` to `Data Disposal Management`, `Compliance Reporting Engine`, `User Account Management`, `Data Governance Helpers`, `Database Migrations`, `Authentication Flow`, `Security Middleware`, `Auth Configuration and Testing`, `Application Entry Point`, `Session and CSRF Middleware`, `Platform Administration`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Are the 72 inferred relationships involving `DataRecord` (e.g. with `approve_disposal()` and `build_compliance_report()`) actually correct?**
  _`DataRecord` has 72 INFERRED edges - model-reasoned connections that need verification._
- **Are the 59 inferred relationships involving `DataCategory` (e.g. with `build_compliance_report()` and `calculate_retention_end_date()`) actually correct?**
  _`DataCategory` has 59 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `log_audit()` (e.g. with `AuditLog` and `api_records_terminate()`) actually correct?**
  _`log_audit()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects ``password_resets``, ``system_settings``, `Billing & Subscription Template` to the rest of the system?**
  _21 weakly-connected nodes found - possible documentation gaps or missing edges._