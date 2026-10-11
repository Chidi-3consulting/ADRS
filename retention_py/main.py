"""
SafeData Python Engine — main application entry point.

Registers FastAPI app with:
  - Security middleware (headers with nonce CSP, CSRF, session enforcement)
  - All route blueprints
  - (Background jobs run in the separate worker: python -m app.worker)
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
import logging
from datetime import datetime
from sqlalchemy import text as _sql_text

from app.database import SessionLocal
from app.auth import get_session, build_session_data
from app.config import APP_ENV, IS_PRODUCTION, IS_TEST, ALLOWED_HOSTS, LEGACY_HOSTS
from app.core.logging import RequestIdMiddleware, configure_logging
configure_logging(json_output=IS_PRODUCTION)

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
        # Calculate dynamic trial_days remaining from trial_ends_at
        sub_status = session.get("subscription_status", "trial")
        trial_ends = session.get("trial_ends_at")
        if sub_status == "trial":
            if trial_ends:
                try:
                    ends_dt = datetime.fromisoformat(trial_ends) if isinstance(trial_ends, str) else trial_ends
                    diff = (ends_dt - datetime.utcnow()).total_seconds()
                    days_left = max(0, int(diff // 86400) + (1 if diff % 86400 > 0 else 0))
                    context["trial_days"] = days_left
                except Exception:
                    context["trial_days"] = 14
            else:
                context["trial_days"] = 14
        else:
            context["trial_days"] = None
    else:
        context["is_platform_admin"] = False
        context.setdefault("unread_notifications_count", 0)
        context["trial_days"] = None
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
# Gap 14: Only enable debug in local dev mode — never in production or staging
app = FastAPI(
    title="SafeData — Data Retention & Governance Platform",
    version="3.0.0",
    docs_url="/api/docs" if not IS_PRODUCTION else None,
    redoc_url="/api/redoc" if not IS_PRODUCTION else None,
    debug=(APP_ENV == "local"),
)


# ── Register Security Middleware (order matters: outermost first) ──
from app.middleware import (
    SecurityHeadersMiddleware,
    CSRFMiddleware,
    SessionEnforcementMiddleware,
    RequestSizeLimitMiddleware,
    CanonicalHostMiddleware,
)

# Middleware is applied in reverse order — last added = outermost
app.add_middleware(SessionEnforcementMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
# Gap 9: Trusted Host validation — prevent Host header attacks in production
# (legacy hosts are accepted so CanonicalHostMiddleware's 301 stays reachable)
if ALLOWED_HOSTS and ALLOWED_HOSTS != "*":
    _hosts = [h.strip() for h in ALLOWED_HOSTS.split(",") if h.strip()]
    if _hosts:
        _hosts += [h for h in LEGACY_HOSTS if h not in _hosts]
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)

app.add_middleware(RequestIdMiddleware)
# Outermost: redirect legacy hosts before anything else runs
app.add_middleware(CanonicalHostMiddleware)

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
def _db_ping() -> None:
    db = SessionLocal()
    try:
        db.execute(_sql_text("SELECT 1"))
    finally:
        db.close()


@app.get("/healthz")
def system_healthz():
    try:
        _db_ping()
    except Exception:
        logging.getLogger("safedata.health").exception("database ping failed")
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "error"})
    return JSONResponse(content={"status": "ok", "database": "ok", "service": "SafeData"})


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
