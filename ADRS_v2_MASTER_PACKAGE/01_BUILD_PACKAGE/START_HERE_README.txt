╔══════════════════════════════════════════════════════════════════════╗
║   3CONSULTING — AUTOMATED DATA RETENTION SYSTEM (ADRS) v2          ║
║   TWO-TIER EDITION: CORE + ENTERPRISE  |  2025  |  CONFIDENTIAL    ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  STEP 1: Open .github/copilot-instructions.md in your IDE           ║
║          Pin it as workspace context. Keep it open every session.   ║
║                                                                      ║
║  STEP 2: Install Python dependencies                                ║
║          cd retention_py                                            ║
║          pip install -r requirements.txt                            ║
║                                                                      ║
║  STEP 3: Start the development server                               ║
║          .\dev-start.ps1          (Windows PowerShell)              ║
║          python main.py           (direct, port 8200)               ║
║                                                                      ║
║  STEP 4: Register your organisation                                 ║
║          Navigate to http://localhost:8200/register                  ║
║                                                                      ║
║  STEP 5: Run the test suite                                         ║
║          python -m pytest tests/                                    ║
║                                                                      ║
║  BUILD PROMPTS (reference specifications):                          ║
║                                                                      ║
║  ── CORE TIER (build and test first) ───────────────────────────   ║
║  prompts/01-project-setup.md          Foundation + config           ║
║  prompts/02-auth-system.md            Login + password reset        ║
║  prompts/03-data-category-register.md Categories                    ║
║  prompts/04-retention-schedule-manager.md Records lifecycle         ║
║  prompts/05-automated-engine-cron.md  Daily automation              ║
║  prompts/06-audit-log-viewer.md       Audit trail                   ║
║  prompts/07-email-notifications.md    Email system                  ║
║  prompts/08-dashboard.md              Dashboard                     ║
║  prompts/09-dsar-module.md            DSAR tracking                 ║
║  prompts/10-file-attachments.md       Secure attachments            ║
║  prompts/11-bulk-import.md            CSV import                    ║
║  prompts/12-advanced-features.md      Settings + extras             ║
║                                                                      ║
║  ── ENTERPRISE TIER (build after Core is working) ──────────────   ║
║  prompts/13-enterprise-api-layer.md   REST API endpoints            ║
║  prompts/14-integration-management.md Systems, keys, mappings       ║
║  prompts/15-outbound-disposal-dispatch.md Webhook dispatch          ║
║  prompts/16-enterprise-monitoring.md  Enterprise dashboard          ║
║  prompts/17-enterprise-onboarding-wizard.md Onboarding + upgrade    ║
║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  DEFAULT LOGIN (change immediately after first deploy):             ║
║  Admin: admin@3consult-ng.com  /  password                         ║
║  DPO:   dpo@3consult-ng.com    /  password                         ║
╠══════════════════════════════════════════════════════════════════════╣
║  ENTERPRISE API TEST (after activating Enterprise tier):            ║
║  curl -X GET "http://localhost:8200/api/v1/health"                  ║
║       -H "X-API-Key: adrs_YOUR_KEY_HERE"                           ║
╠══════════════════════════════════════════════════════════════════════╣
║  TECH STACK:  Python 3.10+ · FastAPI · SQLAlchemy · Jinja2         ║
║               Pytest · Alembic · passlib[bcrypt] · APScheduler     ║
╠══════════════════════════════════════════════════════════════════════╣
║  3Consulting Limited  |  projects@3consult-ng.com                  ║
║  Lagos, Nigeria  &  Oakham, UK  |  www.3consult-ng.com             ║
╚══════════════════════════════════════════════════════════════════════╝
