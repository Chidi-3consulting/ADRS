"""
SafeData Public Routes — landing, login, register, password reset, logout.

Security integrations:
  - Login brute-force throttling
  - Login attempt recording (success + failure)
  - Password policy enforcement on registration and password reset
  - Session timestamps for timeout enforcement
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Request, Response, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import secrets
import hashlib

from app.database import get_db
from app.config import APP_URL, APP_HOST
from app.models import User, Organization, DataCategory, PasswordReset
from app.auth import (
    hash_password, verify_password, DUMMY_PASSWORD_HASH, set_session, clear_session, get_session,
    build_session_data, record_login_attempt, login_throttle_seconds,
    password_policy_error, check_password_history, record_password_history,
)
from app.helpers import (
    SafeData_SUPPORTED_COUNTRIES, detect_visitor_currency, get_country_regulation_labels,
    provision_org_categories, get_framework_badge, totp_verify, consume_recovery_code,
    send_system_email, log_audit, get_visitor_country, get_localized_pricing, CURRENCY_DATA,
)

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)
templates.env.globals['get_framework_badge'] = get_framework_badge
templates.env.globals['unread_notifications_count'] = 0

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def view_landing(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if session and "user_id" in session:
        return RedirectResponse(url="/dashboard", status_code=303)

    country = get_visitor_country(request)
    pricing = get_localized_pricing(country)
    geo = detect_visitor_currency(country)

    return templates.TemplateResponse(request=request, name="landing.html", context={
        "page_title": "SafeData — Automated Data Retention & Governance Platform",
        "wl_name": "SafeData",
        "wl_footer": "3Consulting Limited",
        "country_code": country,
        "pricing": pricing,
        "currencies": CURRENCY_DATA,
        "geo_currency": geo["code"],
        "geo_symbol": geo["symbol"],
        "geo_rate_yearly": "{:,.2f}".format(399 * geo["rate"]),
        "geo_rate_monthly": "{:,.2f}".format(40 * geo["rate"]),
    })


@router.get("/safedata", response_class=HTMLResponse)
def view_safedata_content(request: Request):
    return templates.TemplateResponse(request=request, name="safedata_content.html", context={
        "page_title": "SafeData — Data Retention & Governance",
        "page_description": "A practical, accountable approach to information retention and lifecycle governance.",
        "wl_name": "SafeData",
        "wl_footer": "3Consulting Limited",
        "app_url": APP_URL,
    })


@router.get("/login", response_class=HTMLResponse)
def view_login(request: Request):
    session = get_session(request)
    if session and "user_id" in session:
        return RedirectResponse(url="/dashboard", status_code=303)

    # A6: Show session expiry message
    expired = request.query_params.get("expired", "")
    flash_msg = "Your session has expired. Please sign in again." if expired == "1" else None

    return templates.TemplateResponse(request=request, name="login.html", context={
        "page_title": "Sign In — SafeData",
        "wl_name": "SafeData",
        "wl_footer": "3Consulting Limited",
        "flash_error": flash_msg,
    })


@router.post("/login")
def handle_login(
    response: Response,
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    email = email.strip().lower()
    ip = request.client.host if request.client else "127.0.0.1"

    # ── Brute-force throttle check ──
    wait = login_throttle_seconds(db, email, ip)
    if wait > 0:
        return templates.TemplateResponse(request=request, name="login.html", context={
            "page_title": "Sign In — SafeData",
            "wl_name": "SafeData",
            "wl_footer": "3Consulting Limited",
            "flash_error": f"Too many failed attempts. Try again in {wait} seconds."
        })

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    # SEC: always run bcrypt against a real hash, known user or not, so an
    # unregistered email doesn't come back measurably faster than a wrong
    # password on a real account (DUMMY_PASSWORD_HASH in app/auth.py).
    password_ok = verify_password(password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not user or not password_ok:
        # Record failed attempt
        record_login_attempt(db, email, ip, success=False)
        # F2 fix: check user is not None before accessing user.organization_id
        audit_org_id = user.organization_id if user else 0
        audit_user_id = user.id if user else None
        log_audit(db, audit_org_id, "login_failed", "user",
                  audit_user_id, None, {"email": email, "ip": ip}, ip)
        return templates.TemplateResponse(request=request, name="login.html", context={
            "page_title": "Sign In — SafeData",
            "wl_name": "SafeData",
            "wl_footer": "3Consulting Limited",
            "flash_error": "Invalid email credentials or inactive account."
        })

    # Record successful attempt
    record_login_attempt(db, email, ip, success=True)

    # Check 2FA
    if user.twofa_enabled:
        redir = RedirectResponse(url="/login/2fa", status_code=303)
        set_session(redir, {"2fa_pending_user": user.id})
        return redir

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    session_data = build_session_data(user, org)

    # Gap 10: Regenerate CSRF token on login to prevent session fixation
    import secrets as _secrets
    session_data["csrf_token"] = _secrets.token_hex(32)

    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    log_audit(db, org.id, "login_success", "user", user.id, user.id, {"email": email, "role": user.role}, ip)

    redir = RedirectResponse(url="/dashboard", status_code=303)
    set_session(redir, session_data)
    return redir


@router.get("/login/2fa", response_class=HTMLResponse)
def view_2fa(request: Request):
    session = get_session(request)
    if not session or "2fa_pending_user" not in session:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(request=request, name="twofa_challenge.html", context={
        "page_title": "Two-Factor Authentication — SafeData",
        "wl_name": "SafeData"
    })


@router.post("/login/2fa")
def handle_2fa(
    response: Response,
    request: Request,
    code: str = Form(...),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "2fa_pending_user" not in session:
        return RedirectResponse(url="/login", status_code=303)

    pending_id = session["2fa_pending_user"]
    user = db.query(User).filter(User.id == pending_id, User.is_active == True).first()
    if not user:
        redir = RedirectResponse(url="/login", status_code=303)
        clear_session(redir)
        return redir

    from app.auth import decrypt_totp_secret
    ok = False
    if totp_verify(decrypt_totp_secret(user.twofa_secret), code):
        ok = True
    else:
        # Try recovery codes
        import json
        try:
            recovery_list = json.loads(user.twofa_recovery or "[]")
        except Exception:
            recovery_list = []

        remaining = consume_recovery_code(recovery_list, code)
        if remaining is not None:
            user.twofa_recovery = json.dumps(remaining)
            db.commit()
            ok = True

    if ok:
        org = db.query(Organization).filter(Organization.id == user.organization_id).first()
        session_data = build_session_data(user, org)

        # Gap 10: Regenerate CSRF token on 2FA login
        import secrets as _secrets
        session_data["csrf_token"] = _secrets.token_hex(32)

        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()

        ip = request.client.host if request.client else "127.0.0.1"
        log_audit(db, org.id, "2fa_login_success", "user", user.id, user.id, {"email": user.email}, ip)

        redir = RedirectResponse(url="/dashboard", status_code=303)
        set_session(redir, session_data)
        return redir

    return templates.TemplateResponse(request=request, name="twofa_challenge.html", context={
        "page_title": "Two-Factor Authentication — SafeData",
        "wl_name": "SafeData",
        "error": "Invalid verification code or recovery code."
    })


@router.get("/forgot_password", response_class=HTMLResponse)
def view_forgot_password(request: Request):
    return templates.TemplateResponse(request=request, name="forgot_password.html", context={
        "page_title": "Forgot Password — SafeData",
        "wl_name": "SafeData"
    })


@router.post("/forgot_password")
def handle_forgot_password(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if user:
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

        reset_row = PasswordReset(
            email=email,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used=False
        )
        db.add(reset_row)
        db.commit()

        reset_link = f"{request.base_url}reset_password?email={email}&token={raw_token}"
        subject = "Reset your password — SafeData"
        html = f"""
        <p>Hello,</p>
        <p>We received a request to reset the password for your SafeData account.</p>
        <p><a href="{reset_link}">Click here to set a new password</a></p>
        <p>This link is valid for 1 hour.</p>
        <p>If you did not request this, please ignore this email.</p>
        """
        send_system_email(db, email, subject, html)

    return templates.TemplateResponse(request=request, name="forgot_password.html", context={
        "page_title": "Forgot Password — SafeData",
        "wl_name": "SafeData",
        "done": True
    })


@router.get("/reset_password", response_class=HTMLResponse)
def view_reset_password(
    request: Request,
    email: str = "",
    token: str = "",
    db: Session = Depends(get_db)
):
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    reset = db.query(PasswordReset).filter(
        PasswordReset.email == email,
        PasswordReset.token_hash == token_hash,
        PasswordReset.used == False,
        PasswordReset.expires_at > datetime.utcnow()
    ).first()

    return templates.TemplateResponse(request=request, name="reset_password.html", context={
        "page_title": "Set New Password — SafeData",
        "wl_name": "SafeData",
        "valid_token": bool(reset),
        "email": email,
        "token": token
    })


@router.post("/reset_password")
def handle_reset_password(
    request: Request,
    email: str = Form(...),
    token: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db)
):
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    reset = db.query(PasswordReset).filter(
        PasswordReset.email == email,
        PasswordReset.token_hash == token_hash,
        PasswordReset.used == False,
        PasswordReset.expires_at > datetime.utcnow()
    ).first()

    if not reset:
        return templates.TemplateResponse(request=request, name="reset_password.html", context={
            "page_title": "Set New Password — SafeData",
            "wl_name": "SafeData",
            "valid_token": False
        })

    if password != password_confirm:
        return templates.TemplateResponse(request=request, name="reset_password.html", context={
            "page_title": "Set New Password — SafeData",
            "wl_name": "SafeData",
            "valid_token": True,
            "email": email,
            "token": token,
            "error": "Passwords do not match."
        })

    # ── Password policy enforcement ──
    policy_err = password_policy_error(password)
    if policy_err:
        return templates.TemplateResponse(request=request, name="reset_password.html", context={
            "page_title": "Set New Password — SafeData",
            "wl_name": "SafeData",
            "valid_token": True,
            "email": email,
            "token": token,
            "error": policy_err,
        })

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if user:
        # Gap 3: Check password history before allowing reset
        if check_password_history(db, user.id, password):
            return templates.TemplateResponse(request=request, name="reset_password.html", context={
                "page_title": "Set New Password — SafeData",
                "wl_name": "SafeData",
                "valid_token": True,
                "email": email,
                "token": token,
                "error": "You cannot reuse a recent password. Please choose a different one.",
            })

        new_hash = hash_password(password)
        user.password_hash = new_hash
        user.must_change_password = False  # Clear enforcement flag
        reset.used = True
        db.commit()

        # Gap 3: Record in password history
        record_password_history(db, user.id, new_hash)

        ip = request.client.host if request.client else "127.0.0.1"
        log_audit(db, user.organization_id, "password_reset_completed", "user", user.id, user.id, {"email": email}, ip)

    return templates.TemplateResponse(request=request, name="reset_password.html", context={
        "page_title": "Set New Password — SafeData",
        "wl_name": "SafeData",
        "ok": True
    })


@router.get("/register", response_class=HTMLResponse)
def view_register(request: Request):
    session = get_session(request)
    if session and "user_id" in session:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(request=request, name="register.html", context={
        "page_title": "Start Free Trial — SafeData",
        "countries": SafeData_SUPPORTED_COUNTRIES,
        "wl_name": "SafeData",
        "wl_footer": "3Consulting Limited"
    })


@router.post("/register")
def handle_register(
    response: Response,
    request: Request,
    org_name: str = Form(...),
    domain: str = Form(...),
    user_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    country: str = Form(...),
    db: Session = Depends(get_db)
):
    import re

    # Normalise inputs
    org_name = org_name.strip()
    domain = domain.strip().lower()
    user_name = user_name.strip()
    email = email.strip().lower()

    # Strip leading http(s):// or www. from domain input (common user mistake)
    domain = re.sub(r'^https?://', '', domain)
    domain = re.sub(r'^www\.', '', domain)
    domain = domain.rstrip('/')

    # Helper: return to form with error + retained values
    def _error(msg: str):
        return templates.TemplateResponse(request=request, name="register.html", context={
            "page_title": "Start Free Trial — SafeData",
            "countries": SafeData_SUPPORTED_COUNTRIES,
            "wl_name": "SafeData",
            "wl_footer": "3Consulting Limited",
            "flash_error": msg,
            "form_org_name": org_name,
            "form_domain": domain,
            "form_user_name": user_name,
            "form_email": email,
            "form_country": country,
        })

    # ── Domain format validation ──
    # Supports any valid TLD: .com, .co.uk, .org, .ng, .io, .tech, .edu, etc.
    # Pattern: one or more labels separated by dots, each label is 1-63 alphanum/hyphens,
    # and the TLD must be at least 2 chars (letters only).
    domain_regex = r'^(?!-)[a-z0-9-]{1,63}(?<!-)(\.[a-z0-9-]{1,63})*\.[a-z]{2,}$'
    if not re.match(domain_regex, domain):
        return _error(
            "Invalid domain format. Enter your company domain without http:// "
            "(e.g. company.com, firm.co.uk, org.ng)."
        )

    # ── Password confirmation ──
    if password != password_confirm:
        return _error("Passwords do not match. Please re-enter.")

    # ── Password policy enforcement ──
    policy_err = password_policy_error(password)
    if policy_err:
        return _error(policy_err)

    # ── Email must belong to the declared domain ──
    email_domain = email.split("@")[-1] if "@" in email else ""
    if email_domain != domain:
        return _error(
            f"Your email must use the domain you registered ({domain}). "
            f"Got @{email_domain} instead."
        )

    # ── Uniqueness checks ──
    domain_exists = db.query(Organization).filter(Organization.primary_domain == domain).first()
    email_exists = db.query(User).filter(User.email == email).first()

    if domain_exists:
        return _error("This domain is already registered on SafeData.")
    if email_exists:
        return _error("This email address is already registered.")

    # ── Create organisation ──
    now_utc = datetime.utcnow()
    org = Organization(
        name=org_name,
        slug=re.sub(r'[^a-z0-9]+', '-', org_name.lower()).strip('-')[:50],
        primary_domain=domain,
        country=country,
        tier="core",
        status="trial",
        subscription_status="trial",
        trial_ends_at=now_utc + timedelta(days=14),
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    provision_org_categories(db, org.id, country)

    pwd = hash_password(password)
    user = User(
        organization_id=org.id,
        name=user_name,
        email=email,
        password_hash=pwd,
        role="admin",
        is_active=True,
        email_verified_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    ip = request.client.host if request.client else "127.0.0.1"
    record_login_attempt(db, email, ip, success=True)
    log_audit(db, org.id, "user_registered", "user", user.id, user.id, {"email": email}, ip)

    # Gap 3: Record initial password in history
    record_password_history(db, user.id, pwd)

    # ── Automatic welcome email (sent by 3Consulting's platform SMTP) ──
    # Runs in a background thread so it never delays the redirect.
    def _send_welcome(to: str, name: str, org: str, country: str):
        from app.helpers import send_system_email
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a2e;">
          <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:32px 40px;border-radius:12px 12px 0 0;">
            <h1 style="color:#fff;margin:0;font-size:24px;">Welcome to SafeData 🎉</h1>
            <p style="color:rgba(255,255,255,0.85);margin:8px 0 0;">Your organisation is ready for compliance governance.</p>
          </div>
          <div style="background:#fff;padding:32px 40px;border:1px solid #e8e8f0;border-top:none;border-radius:0 0 12px 12px;">
            <p style="font-size:16px;">Hi <strong>{name}</strong>,</p>
            <p>Your organisation <strong>{org}</strong> has been successfully registered on SafeData — the data retention &amp; governance platform by <strong>3Consulting</strong>.</p>
            <p>Here's what to do next:</p>
            <ol style="line-height:1.8;color:#444;">
              <li>Log in and complete your <strong>compliance setup checklist</strong> on the dashboard</li>
              <li>Review your auto-provisioned <strong>data categories</strong> for {country}</li>
              <li>Add your team members under <strong>Settings → Users</strong></li>
              <li>Import or create your first <strong>data records</strong></li>
            </ol>
            <div style="background:#f0f4ff;border-left:4px solid #667eea;padding:16px 20px;border-radius:6px;margin:24px 0;">
              <p style="margin:0;font-size:14px;color:#444;">
                Your 14-day free trial is now active. Our team will be in touch with guidance.<br>
                Need help? Reply to this email — we're here for you.
              </p>
            </div>
            <p style="color:#888;font-size:13px;margin-top:32px;">
              — The SafeData Team, 3Consulting Limited<br>
              <a href="{APP_URL}" style="color:#667eea;">{APP_HOST}</a>
            </p>
          </div>
        </div>
        """
        send_system_email(None, to, f"Welcome to SafeData — {org} is ready!", html)

    import threading
    threading.Thread(
        target=_send_welcome,
        args=(email, user_name, org_name, country),
        daemon=True
    ).start()

    session_data = build_session_data(user, org)

    redir = RedirectResponse(url="/dashboard", status_code=303)
    set_session(redir, session_data)
    return redir



@router.get("/logout")
def handle_logout(request: Request, response: Response, db: Session = Depends(get_db)):
    session = get_session(request)
    if session and "user_id" in session:
        ip = request.client.host if request.client else "127.0.0.1"
        log_audit(db, session.get("org_id", 1), "user_logout", "user", session["user_id"], session["user_id"], {"name": session.get("user_name")}, ip)
    redir = RedirectResponse(url="/", status_code=303)
    clear_session(redir)
    return redir


# ═══════════════════════════════════════════════════════════════════════════
#   Email Verification (Gap 2
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/verify_email", response_class=HTMLResponse)
def view_verify_email(request: Request, token: str = "", db: Session = Depends(get_db)):
    session = get_session(request)

    # If token provided, verify it immediately
    if token:
        from app.auth import verify_email_token
        success = verify_email_token(db, token)
        return templates.TemplateResponse(request=request, name="verify_email.html", context={
            "page_title": "Email Verification — SafeData",
            "wl_name": "SafeData",
            "wl_footer": "3Consulting Limited",
            "verified": success,
            "token_provided": True,
            "session": session,
        })

    return templates.TemplateResponse(request=request, name="verify_email.html", context={
        "page_title": "Verify Your Email — SafeData",
        "wl_name": "SafeData",
        "wl_footer": "3Consulting Limited",
        "verified": False,
        "token_provided": False,
        "session": session,
    })


@router.post("/verify_email/resend", response_class=HTMLResponse)
def resend_verification(request: Request, db: Session = Depends(get_db)):
    """Resend verification email to the currently logged-in user."""
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    from app.auth import issue_email_verification_token
    from app.helpers import email_verification, send_system_email
    from app.models import User

    user = db.query(User).filter(User.id == session["user_id"]).first()
    if user and not user.email_verified_at:
        raw_token = issue_email_verification_token(db, user.id)
        if raw_token:
            verify_link = f"{APP_URL}/verify_email?token={raw_token}"
            subject, html = email_verification(user.name, verify_link)
            send_system_email(db, user.email, subject, html)

    return RedirectResponse(url="/verify_email?resent=1", status_code=303)


# ═══════════════════════════════════════════════════════════════════════════
#   Setup Wizard (Gap 3
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/setup", response_class=HTMLResponse)
def view_setup(request: Request, db: Session = Depends(get_db)):
    from app.auth import setup_is_complete

    if setup_is_complete(db):
        session = get_session(request)
        if session and "user_id" in session:
            return RedirectResponse(url="/dashboard", status_code=303)
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(request=request, name="setup.html", context={
        "page_title": "Initial Setup — SafeData",
        "wl_name": "SafeData",
        "wl_footer": "3Consulting Limited",
        "error": None,
    })


@router.post("/setup", response_class=HTMLResponse)
def handle_setup(
    request: Request,
    org_name: str = Form(""),
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    password_confirm: str = Form(""),
    import_categories: str = Form(""),
    db: Session = Depends(get_db),
):
    from app.auth import setup_is_complete
    from app.models import SystemSetting

    if setup_is_complete(db):
        return RedirectResponse(url="/login", status_code=303)

    error = None
    org_name = org_name.strip()
    name = name.strip()
    email = email.strip().lower()

    if not org_name or not name or not email:
        error = "Organisation name, your name, and email are required."
    elif "@" not in email or "." not in email:
        error = "A valid email address is required."
    else:
        pw_err = password_policy_error(password)
        if pw_err:
            error = pw_err
        elif password != password_confirm:
            error = "Passwords do not match."
        else:
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                error = "A user with that email already exists."

    if error:
        return templates.TemplateResponse(request=request, name="setup.html", context={
            "page_title": "Initial Setup — SafeData",
            "wl_name": "SafeData",
            "wl_footer": "3Consulting Limited",
            "error": error,
        })

    # Create organization
    import secrets as _secrets
    now_utc = datetime.utcnow()
    org = Organization(
        name=org_name,
        slug=org_name.lower().replace(" ", "-")[:50],
        primary_domain=f"{org_name.lower().replace(' ', '-')}.SafeData.local",
        country="NG",
        tier="core",
        status="trial",
        subscription_status="trial",
        trial_ends_at=now_utc + timedelta(days=14),
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create admin user
    admin = User(
        organization_id=org.id,
        name=name,
        email=email,
        password_hash=hash_password(password),
        role="admin",
        is_active=True,
        must_change_password=False,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    # System settings
    db.add(SystemSetting(setting_key="white_label_name", setting_value=org_name))
    db.add(SystemSetting(setting_key="app_name", setting_value=org_name))
    db.add(SystemSetting(setting_key="setup_complete", setting_value="1"))
    db.commit()

    # Seed categories if requested
    if import_categories == "1":
        provision_org_categories(db, org.id, org.country or "NG")

    ip = request.client.host if request.client else "127.0.0.1"
    log_audit(db, org.id, "setup_completed", "system", org.id, admin.id, {"org": org_name}, ip)

    session_data = build_session_data(admin, org)
    redir = RedirectResponse(url="/dashboard", status_code=303)
    set_session(redir, session_data)
    return redir
