"""
SafeData Security Middleware

Provides:
  1. Security response headers (CSP with nonce-based script-src, HSTS, etc.)
  2. CSRF token generation / validation for form submissions
  3. Session idle + absolute timeout enforcement
  4. Password-change enforcement (must_change_password redirect)
  5. 2FA policy enforcement (require_2fa_roles redirect)
  6. Subscription/trial enforcement (redirect expired orgs to /billing)
  7. Email verification enforcement (redirect unverified to /verify_email)
  8. Setup-complete guard (redirect to /setup if not yet configured)
  9. Request body size limiting (Gap 8)
"""
import secrets
import time
import hashlib

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import (
    IS_PRODUCTION, APP_ENV, SESSION_IDLE_TIMEOUT, SESSION_ABSOLUTE_TIMEOUT,
    CSRF_TOKEN_LENGTH, SECRET_KEY, MAX_REQUEST_BODY_SIZE, APP_URL, LEGACY_HOSTS,
)
from app.auth import get_session, set_session


# ═══════════════════════════════════════════════════════════════════════════
#   1. Security Headers Middleware (Gap 9: nonce-based CSP)
# ═══════════════════════════════════════════════════════════════════════════

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Emit hardening headers on every response. 
    Uses per-request nonce for script-src ,
    replacing the weaker 'unsafe-inline' policy.
    """

    async def dispatch(self, request: Request, call_next):
        # Generate per-request CSP nonce
        csp_nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = csp_nonce

        response: Response = await call_next(request)

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        if IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Gap 13: Cache-Control for authenticated pages — prevent browser caching
        # Static files and public pages are excluded
        if not request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"

        # CSP — nonce-based script-src 
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{csp_nonce}' https://cdn.jsdelivr.net; "
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        return response


# ═══════════════════════════════════════════════════════════════════════════
#   2. CSRF Middleware
# ═══════════════════════════════════════════════════════════════════════════

# Routes exempt from CSRF checks (API endpoints use API-key auth instead)
CSRF_EXEMPT_PREFIXES = (
    "/api/",
    "/healthz",
    "/api/docs",
    "/api/redoc",
    "/openapi.json",
    "/static/",
    "/webhooks/",
)

CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _generate_csrf_token() -> str:
    """64-hex-char token, matching legacy csrf_token() length."""
    return secrets.token_hex(CSRF_TOKEN_LENGTH)


def _csrf_field_html(token: str) -> str:
    """Hidden input for Jinja2 templates."""
    return f'<input type="hidden" name="csrf_token" value="{token}">'


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    - On every request: ensure the session contains a CSRF token.
    - On mutating requests (POST/PUT/PATCH/DELETE): verify the submitted
      csrf_token matches the session token. API routes are exempt.
    - Exposes `csrf_token` and `csrf_field` as Jinja2 template globals.

    IMPORTANT: We read the raw body bytes to extract the csrf_token and then
    re-inject them via a custom `receive` callable. This avoids consuming
    the request stream (which would cause 422 errors in downstream FastAPI
    route handlers that also need to parse the form body).
    """

    async def dispatch(self, request: Request, call_next):
        session = get_session(request)
        new_token_generated = False

        # Ensure session has a CSRF token
        csrf_token = session.get("csrf_token", "")
        if not csrf_token:
            csrf_token = _generate_csrf_token()
            session["csrf_token"] = csrf_token
            new_token_generated = True

        # Store token on request.state so templates and inner middlewares can access it
        request.state.csrf_token = csrf_token
        request.state.csrf_field = _csrf_field_html(csrf_token)

        # Check CSRF on mutating methods (skip API routes and test env)
        path = request.url.path
        if request.method in CSRF_METHODS and APP_ENV != "test":
            is_exempt = any(path.startswith(p) for p in CSRF_EXEMPT_PREFIXES)
            if not is_exempt:
                submitted = ""
                content_type = request.headers.get("content-type", "")

                if "application/x-www-form-urlencoded" in content_type:
                    # Read the raw body bytes without consuming the stream
                    body_bytes = await request.body()
                    try:
                        from urllib.parse import parse_qs
                        parsed = parse_qs(body_bytes.decode("utf-8", errors="replace"))
                        submitted = parsed.get("csrf_token", [""])[0]
                    except Exception:
                        submitted = ""

                    # Re-inject the body so downstream handlers can read it
                    async def _receive():
                        return {"type": "http.request", "body": body_bytes}
                    request._receive = _receive

                elif "multipart/form-data" in content_type:
                    # For multipart, read body and re-inject
                    body_bytes = await request.body()
                    try:
                        form = await request.form()
                        submitted = form.get("csrf_token", "")
                    except Exception:
                        submitted = ""

                    async def _receive_mp():
                        return {"type": "http.request", "body": body_bytes}
                    request._receive = _receive_mp

                if not submitted:
                    submitted = request.headers.get("X-CSRF-Token", "")

                stored = session.get("csrf_token", "")
                if not stored or not _constant_time_compare(stored, submitted):
                    return HTMLResponse(
                        content="<h1>403 Forbidden</h1><p>Invalid or missing CSRF token. "
                                "Please go back and try again.</p>",
                        status_code=403,
                    )

        response: Response = await call_next(request)

        # F4 fix: Starlette MutableHeaders has no getlist() — use raw headers iteration
        if new_token_generated or not session.get("user_id"):
            raw_cookies = response.raw_headers  # list of (name_bytes, value_bytes)
            handler_already_set_session = any(
                b"SafeData_session" in v or b"safedata_session" in v
                for n, v in raw_cookies
                if n.lower() == b"set-cookie"
            )
            if not handler_already_set_session:
                set_session(response, session)

        return response


def _constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    if not a or not b:
        return False
    return secrets.compare_digest(a, b)


# ═══════════════════════════════════════════════════════════════════════════
#   3. Session Enforcement Middleware
# ═══════════════════════════════════════════════════════════════════════════

# Routes that don't require an active session
PUBLIC_PATHS = (
    "/", "/login", "/register", "/logout", "/forgot_password", "/reset_password",
    "/signup", "/legal", "/healthz", "/health", "/verify_email", "/setup",
    "/invite/accept", "/static/", "/api/", "/openapi.json",
    "/api/docs", "/api/redoc", "/webhooks/", "/landing",
)


class SessionEnforcementMiddleware(BaseHTTPMiddleware):
    """
    For authenticated users:
      - Enforce idle timeout (30 min)
      - Enforce absolute timeout (8 hr)
      - Enforce must_change_password redirect
      - Enforce email verification (Gap 2)
      - Enforce 2FA policy
      - Enforce subscription status + trial expiry (Gap 11)
      - Enforce setup-complete guard (Gap 3)
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip enforcement for public routes and static files
        if any(path == p or path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)

        # ── Setup-complete guard (Gap 3) ──
        # Redirect to /setup if not yet configured for protected routes
        try:
            from app.database import SessionLocal
            from app.auth import setup_is_complete
            _db = SessionLocal()
            try:
                if not setup_is_complete(_db):
                    if path != "/setup":
                        return RedirectResponse(url="/setup", status_code=303)
            finally:
                _db.close()
        except Exception:
            pass  # Don't block on setup check failures

        session = get_session(request)
        if not session or "user_id" not in session:
            return await call_next(request)

        now = time.time()

        # ── Idle timeout ──
        last_activity = session.get("last_activity", now)
        idle = now - last_activity
        if idle > SESSION_IDLE_TIMEOUT:
            response = RedirectResponse(url="/login?expired=1", status_code=303)
            from app.auth import clear_session
            clear_session(response)
            return response

        # ── Absolute timeout ──
        login_time = session.get("login_time", now)
        age = now - login_time
        if age > SESSION_ABSOLUTE_TIMEOUT:
            response = RedirectResponse(url="/login?expired=1", status_code=303)
            from app.auth import clear_session
            clear_session(response)
            return response

        # ── Update last_activity ──
        session["last_activity"] = now

        # ── Freshness re-sync: re-read security-relevant claims from the DB ──
        # (session cookies last up to 8h; role / org status / verification / 2FA
        # changes must take effect without waiting for session expiry)
        try:
            from app.models import User, Organization
            from app.database import SessionLocal
            from app.auth import clear_session as _clear_session
            _db = SessionLocal()
            try:
                u = _db.query(User).filter(User.id == session.get("user_id")).first()
                o = _db.query(Organization).filter(Organization.id == session.get("org_id")).first()
                if not u or not u.is_active or not o:
                    # Account or org deleted/deactivated → force re-login
                    response = RedirectResponse(url="/login?expired=1", status_code=303)
                    _clear_session(response)
                    return response
                session["role"] = u.role
                session["is_platform_admin"] = bool(u.is_platform_admin)
                session["must_change_password"] = bool(u.must_change_password)
                session["twofa_enabled"] = bool(u.twofa_enabled)
                session["email_verified"] = u.email_verified_at is not None
                session["org_status"] = o.status
                session["subscription_status"] = o.subscription_status or "trial"
                session["trial_ends_at"] = o.trial_ends_at.isoformat() if o.trial_ends_at else None
            finally:
                _db.close()
        except Exception:
            pass  # Never break the request because the freshness check failed

        # ── Enforce must_change_password ──
        if session.get("must_change_password") and not _path_is(path, "/profile", "/logout"):
            response = RedirectResponse(url="/profile?required=1", status_code=303)
            set_session(response, session)
            return response

        # ── Enforce email verification (Gap 2) ──
        if not session.get("email_verified") and not session.get("is_platform_admin"):
            if not _path_is(path, "/verify_email", "/logout", "/profile"):
                response = RedirectResponse(url="/verify_email", status_code=303)
                set_session(response, session)
                return response

        # ── Enforce 2FA policy (if configured) ──
        if not session.get("twofa_enabled"):
            require_2fa_roles = session.get("require_2fa_roles", "")
            if require_2fa_roles:
                roles = [r.strip() for r in require_2fa_roles.split(",") if r.strip()]
                if session.get("role") in roles and not _path_is(path, "/settings", "/logout"):
                    response = RedirectResponse(url="/settings?tab=twofa", status_code=303)
                    set_session(response, session)
                    return response

        # ── Enforce subscription + trial expiry (Gap 11) ──
        if not session.get("is_platform_admin"):
            org_status = session.get("org_status", "active")
            if org_status == "suspended" and not _path_is(path, "/billing", "/logout"):
                response = RedirectResponse(url="/billing?suspended=1", status_code=303)
                set_session(response, session)
                return response

            # Trial expiry check
            sub_status = session.get("subscription_status", "active")
            if sub_status == "trial":
                trial_ends = session.get("trial_ends_at")
                if trial_ends:
                    from datetime import datetime
                    try:
                        if isinstance(trial_ends, str):
                            ends_dt = datetime.fromisoformat(trial_ends)
                        else:
                            ends_dt = trial_ends
                        if datetime.utcnow() > ends_dt:
                            if not _path_is(path, "/billing", "/logout"):
                                response = RedirectResponse(url="/billing?trial_expired=1", status_code=303)
                                set_session(response, session)
                                return response
                    except Exception:
                        pass

        # Continue with updated session
        response: Response = await call_next(request)
        # Ensure csrf_token from request.state is retained in session cookie
        if not session.get("csrf_token") and hasattr(request.state, "csrf_token"):
            session["csrf_token"] = request.state.csrf_token
        set_session(response, session)
        return response


def _path_is(path: str, *prefixes: str) -> bool:
    """True if path matches or starts with any of the given prefixes."""
    return any(path == p or path.startswith(p + "/") or path.startswith(p + "?") for p in prefixes)


# ═══════════════════════════════════════════════════════════════════════════
#   Jinja2 Template Globals Helper
# ═══════════════════════════════════════════════════════════════════════════

def register_csrf_template_globals(templates_instance):
    """
    Register csrf_token() and csrf_field() as Jinja2 global functions so
    templates can use {{ csrf_field | safe }} in forms.
    """
    # These are request-scoped, so we provide callables that read from
    # request.state (set by CSRFMiddleware)
    pass  # Handled via the _patched_template_response in main.py


# ═══════════════════════════════════════════════════════════════════════════
#   4. Request Body Size Limit Middleware (Gap 8)
# ═══════════════════════════════════════════════════════════════════════════

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Reject requests with bodies exceeding MAX_REQUEST_BODY_SIZE.
    Prevents memory exhaustion from oversized payloads.
    File upload routes have their own per-route limits (10MB in records.py);
    this is a global safety net.
    """

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BODY_SIZE:
                    return Response(
                        content='{"error": "payload_too_large", "detail": "Request body too large."}',
                        status_code=413,
                        media_type="application/json",
                    )
            except (ValueError, TypeError):
                pass  # Malformed header — let downstream handle
        return await call_next(request)

class CanonicalHostMiddleware:
    """301-redirect requests for legacy hosts to APP_URL, preserving path and query."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and LEGACY_HOSTS:
            host = dict(scope.get("headers") or []).get(b"host", b"").decode("latin-1").split(":")[0].lower()
            if host in LEGACY_HOSTS:
                qs = scope.get("query_string", b"").decode("latin-1")
                location = APP_URL + scope.get("path", "/") + (f"?{qs}" if qs else "")
                await send({"type": "http.response.start", "status": 301,
                            "headers": [(b"location", location.encode("latin-1"))]})
                await send({"type": "http.response.body", "body": b""})
                return
        await self.app(scope, receive, send)
