"""
SafeData Python Engine — main application entry point.

Registers FastAPI app with:
  - Security middleware (headers with nonce CSP, CSRF, session enforcement)
  - All route blueprints
  - Background scheduler tasks:
      * Retention engine + housekeeping (from original)
      * Backup cron (Gap 6)
      * Disposal dispatch cron (Gap 7)
      * Intake queue processor (Gap 8)
  - Custom error handlers (404, 500)
  - Static file serving
"""
import uvicorn
import traceback
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware
import os
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

from app.database import engine, Base, SessionLocal
from app.auth import get_session, build_session_data
from app.config import APP_ENV, IS_PRODUCTION, IS_TEST, ALLOWED_HOSTS

# ── Patch TemplateResponse to inject common context (incl. CSP nonce) ──
_original_template_response = Jinja2Templates.TemplateResponse


def _patched_template_response(self, request, name, context=None, *args, **kwargs):
    if context is None:
        context = {}
    context["request"] = request
    session = get_session(request)
    if session and "user_id" in session:
        context["is_platform_admin"] = session.get("is_platform_admin", False)
        # Dynamically query unread notifications count for logged-in user
        # B5 fix: use try/finally to guarantee db_s.close() even on exceptions
        try:
            from app.models import Notification
            db_s = SessionLocal()
            try:
                unread_count = db_s.query(Notification).filter(
                    Notification.organization_id == session.get("org_id", 1),
                    Notification.recipient_id == session["user_id"],
                    Notification.read_at == None
                ).count()
                context["unread_notifications_count"] = unread_count
            finally:
                db_s.close()
        except Exception:
            context.setdefault("unread_notifications_count", 0)
    else:
        context["is_platform_admin"] = False
        context.setdefault("unread_notifications_count", 0)
    # Inject CSRF token/field for templates
    context.setdefault("csrf_token", getattr(request.state, "csrf_token", ""))
    context.setdefault("csrf_field", getattr(request.state, "csrf_field", ""))
    # Inject CSP nonce for templates (Gap 9)
    context.setdefault("csp_nonce", getattr(request.state, "csp_nonce", ""))
    return _original_template_response(self, request, name, context, *args, **kwargs)


Jinja2Templates.TemplateResponse = _patched_template_response

from app.routes import (
    public, dashboard, categories, records, api_v1, app_pages, platform,
    integrations_routes, recalculations, import_records, ropa
)
from app.engine import run_retention_checks, run_housekeeping
from app.models import Organization

# Ensure missing columns exist on pre-existing database tables
from sqlalchemy import inspect, text

def ensure_schema_columns(bind_engine):
    try:
        inspector = inspect(bind_engine)
        with bind_engine.connect() as conn:
            if inspector.has_table("organizations"):
                cols = [c["name"] for c in inspector.get_columns("organizations")]
                if "trial_ends_at" not in cols:
                    conn.execute(text("ALTER TABLE organizations ADD COLUMN trial_ends_at DATETIME NULL"))
                    conn.commit()
            if inspector.has_table("notifications"):
                cols = [c["name"] for c in inspector.get_columns("notifications")]
                if "follow_up_sent_at" not in cols:
                    conn.execute(text("ALTER TABLE notifications ADD COLUMN follow_up_sent_at DATETIME NULL"))
                    conn.commit()
            if inspector.has_table("data_categories"):
                cols = [c["name"] for c in inspector.get_columns("data_categories")]
                if "processing_role" not in cols:
                    conn.execute(text("ALTER TABLE data_categories ADD COLUMN processing_role VARCHAR(20) DEFAULT 'controller' NOT NULL"))
                    conn.commit()
                if "processor_name" not in cols:
                    conn.execute(text("ALTER TABLE data_categories ADD COLUMN processor_name VARCHAR(255) NULL"))
                    conn.commit()
                if "processor_contact" not in cols:
                    conn.execute(text("ALTER TABLE data_categories ADD COLUMN processor_contact VARCHAR(255) NULL"))
                    conn.commit()
                if "dpa_reference" not in cols:
                    conn.execute(text("ALTER TABLE data_categories ADD COLUMN dpa_reference VARCHAR(255) NULL"))
                    conn.commit()
                if "processor_retention_status" not in cols:
                    conn.execute(text("ALTER TABLE data_categories ADD COLUMN processor_retention_status VARCHAR(50) DEFAULT 'compliant' NULL"))
                    conn.commit()
            if inspector.has_table("data_records"):
                cols = [c["name"] for c in inspector.get_columns("data_records")]
                if "processor_name" not in cols:
                    conn.execute(text("ALTER TABLE data_records ADD COLUMN processor_name VARCHAR(255) NULL"))
                    conn.commit()
                if "processor_sync_status" not in cols:
                    conn.execute(text("ALTER TABLE data_records ADD COLUMN processor_sync_status VARCHAR(50) DEFAULT 'synced' NULL"))
                    conn.commit()
            # ROPA enhancements: add role_type, processor_name, processor_contact
            if inspector.has_table("ropa_entries"):
                cols = [c["name"] for c in inspector.get_columns("ropa_entries")]
                if "role_type" not in cols:
                    conn.execute(text("ALTER TABLE ropa_entries ADD COLUMN role_type VARCHAR(20) DEFAULT 'controller' NOT NULL"))
                    conn.commit()
                if "processor_name" not in cols:
                    conn.execute(text("ALTER TABLE ropa_entries ADD COLUMN processor_name VARCHAR(255) NULL"))
                    conn.commit()
                if "processor_contact" not in cols:
                    conn.execute(text("ALTER TABLE ropa_entries ADD COLUMN processor_contact VARCHAR(255) NULL"))
                    conn.commit()
    except Exception as e:
        print(f"Auto column migration warning: {e}")

ensure_schema_columns(engine)

# Ensure DB tables exist
Base.metadata.create_all(bind=engine)

# Seed default organization if table is empty
db = SessionLocal()
try:
    if not db.query(Organization).first():
        org = Organization(
            id=1,
            name="Default Organisation",
            slug="default",
            primary_domain="default.local",
            country="NG",
            tier="core",
            status="active"
        )
        db.add(org)
        db.commit()
finally:
    db.close()


# ══════════════════════════════════════════════════════════════════════
#   Background Schedulers
# ══════════════════════════════════════════════════════════════════════

async def retention_scheduler_task():
    """Run retention engine checks every 10 minutes."""
    while True:
        await asyncio.sleep(600)  # 10 minutes
        db = SessionLocal()
        try:
            orgs = db.query(Organization).all()
            for org in orgs:
                run_retention_checks(db, org.id)
        except Exception as e:
            print(f"[{datetime.now()}] Scheduler error: {e}")
        finally:
            db.close()


async def housekeeping_scheduler_task():
    """Run housekeeping once per hour."""
    while True:
        await asyncio.sleep(3600)  # 1 hour
        db = SessionLocal()
        try:
            result = run_housekeeping(db)
            print(f"[{datetime.now()}] Housekeeping: {result}")
        except Exception as e:
            print(f"[{datetime.now()}] Housekeeping error: {e}")
        finally:
            db.close()


async def backup_scheduler_task():
    """Run database backup once per day (Gap 6)."""
    while True:
        await asyncio.sleep(86400)  # 24 hours
        db = SessionLocal()
        try:
            from app.backups import backup_database, prune_backups
            from app.config import BACKUP_PATH
            result = backup_database(db, BACKUP_PATH)
            print(f"[{datetime.now()}] Backup: {result['status']} — {result['file']}")
            pruned = prune_backups(db, BACKUP_PATH, days=30)
            if pruned:
                print(f"[{datetime.now()}] Pruned {pruned} old backup(s)")
        except Exception as e:
            print(f"[{datetime.now()}] Backup error: {e}")
        finally:
            db.close()


async def disposal_dispatch_scheduler_task():
    """Process outbound disposal dispatches every 10 minutes (Gap 7)."""
    while True:
        await asyncio.sleep(600)  # 10 minutes
        db = SessionLocal()
        try:
            from app.engine import get_setting
            if get_setting(db, "SafeData_tier", "core") == "enterprise":
                from app.enterprise import process_disposal_dispatches
                result = process_disposal_dispatches(db, 50)
                if result["sent"] or result["failed"]:
                    print(f"[{datetime.now()}] Disposal dispatch: sent {result['sent']}, failed {result['failed']}")
        except Exception as e:
            print(f"[{datetime.now()}] Disposal dispatch error: {e}")
        finally:
            db.close()


async def intake_queue_scheduler_task():
    """Process intake queue every 5 minutes (Gap 8)."""
    while True:
        await asyncio.sleep(300)  # 5 minutes
        db = SessionLocal()
        try:
            from app.engine import get_setting
            if get_setting(db, "SafeData_tier", "core") == "enterprise":
                from app.enterprise import process_intake_queue
                result = process_intake_queue(db, 100)
                if result["processed"]:
                    print(f"[{datetime.now()}] Intake: processed {result['processed']}, "
                          f"created {result['created']}, dup {result['duplicate']}, "
                          f"failed {result['failed']}")
        except Exception as e:
            print(f"[{datetime.now()}] Intake queue error: {e}")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task1 = asyncio.create_task(retention_scheduler_task())
    task2 = asyncio.create_task(housekeeping_scheduler_task())
    task3 = asyncio.create_task(backup_scheduler_task())
    task4 = asyncio.create_task(disposal_dispatch_scheduler_task())
    task5 = asyncio.create_task(intake_queue_scheduler_task())
    yield
    task1.cancel()
    task2.cancel()
    task3.cancel()
    task4.cancel()
    task5.cancel()


# Gap 14: Only enable debug in local dev mode — never in production or staging
app = FastAPI(
    title="SafeData — Data Retention & Governance Platform",
    version="3.0.0",
    docs_url="/api/docs" if not IS_PRODUCTION else None,
    redoc_url="/api/redoc" if not IS_PRODUCTION else None,
    debug=(APP_ENV == "local"),
    lifespan=lifespan
)


# ── Register Security Middleware (order matters: outermost first) ──
from app.middleware import (
    SecurityHeadersMiddleware,
    CSRFMiddleware,
    SessionEnforcementMiddleware,
    RequestSizeLimitMiddleware,
)

# Middleware is applied in reverse order — last added = outermost
app.add_middleware(SessionEnforcementMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)

# Gap 9: Trusted Host validation — prevent Host header attacks in production
if ALLOWED_HOSTS and ALLOWED_HOSTS != "*":
    _hosts = [h.strip() for h in ALLOWED_HOSTS.split(",") if h.strip()]
    if _hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)


# ── Mount Static Files ──
static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


# ── Register Routers ──
app.include_router(public.router)
app.include_router(dashboard.router)
app.include_router(categories.router)
app.include_router(records.router)
app.include_router(app_pages.router)
app.include_router(platform.router)
app.include_router(integrations_routes.router)
app.include_router(recalculations.router)
app.include_router(import_records.router)
app.include_router(ropa.router)
app.include_router(api_v1.router, prefix="/api/v1")


# ── Health Check ──
@app.get("/healthz")
def system_healthz():
    return JSONResponse(content={
        "status": "ok",
        "service": "SafeData Python Engine",
        "env": APP_ENV,
    })


# ── Custom Error Handlers ──
templates_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "templates")
_error_templates = Jinja2Templates(directory=templates_path)


def _is_api_request(request: Request) -> bool:
    """True if the request targets an API endpoint (expects JSON)."""
    return request.url.path.startswith("/api/")


# Gap 7: Sanitised global exception handler — prevents stack traces leaking via API
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if _is_api_request(request):
        # In local/test mode, include error detail for debugging
        detail = str(exc) if APP_ENV in ("local", "test") else "Internal server error"
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "detail": detail},
        )
    # Web pages: render HTML error template
    try:
        return _error_templates.TemplateResponse(
            request=request, name="500.html",
            context={"page_title": "Server Error — SafeData"},
            status_code=500,
        )
    except Exception:
        return HTMLResponse(
            content="<h1>500 — Internal Server Error</h1><p>Something went wrong. Please try again later.</p>",
            status_code=500,
        )


# Gap 7: Sanitised validation error handler — prevents field/type leaks via API in production
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if _is_api_request(request):
        if APP_ENV in ("local", "test"):
            # Full detail for development debugging
            return JSONResponse(
                status_code=422,
                content={"error": "validation_error", "detail": exc.errors()},
            )
        else:
            # Sanitised: only field names and error types, no internal Python types
            safe_errors = []
            for err in exc.errors():
                safe_errors.append({
                    "field": ".".join(str(loc) for loc in err.get("loc", [])),
                    "message": err.get("msg", "Invalid value"),
                })
            return JSONResponse(
                status_code=422,
                content={"error": "validation_error", "detail": safe_errors},
            )
    # Web pages: default FastAPI handling is fine (returns HTML form errors)
    return HTMLResponse(
        content="<h1>422 — Invalid Request</h1><p>The submitted data was invalid. Please go back and try again.</p>",
        status_code=422,
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if _is_api_request(request):
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "detail": "The requested resource was not found."},
        )
    try:
        return _error_templates.TemplateResponse(
            request=request, name="404.html",
            context={"page_title": "Page Not Found — SafeData"},
            status_code=404,
        )
    except Exception:
        return HTMLResponse(
            content="<h1>404 — Page Not Found</h1><p>The page you're looking for doesn't exist.</p>",
            status_code=404,
        )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    if _is_api_request(request):
        detail = str(exc) if APP_ENV in ("local", "test") else "Internal server error"
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "detail": detail},
        )
    try:
        return _error_templates.TemplateResponse(
            request=request, name="500.html",
            context={"page_title": "Server Error — SafeData"},
            status_code=500,
        )
    except Exception:
        return HTMLResponse(
            content="<h1>500 — Internal Server Error</h1><p>Something went wrong. Please try again later.</p>",
            status_code=500,
        )


@app.exception_handler(303)
async def redirect_exception_handler(request: Request, exc):
    return RedirectResponse(url="/login", status_code=303)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8200, reload=True)
