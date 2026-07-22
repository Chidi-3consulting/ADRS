import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request, Response, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import secrets
import hashlib

from app.database import get_db
from app.models import User, Organization, DataCategory, PasswordReset
from app.auth import hash_password, verify_password, set_session, clear_session, get_session
from app.helpers import (
    ADRS_SUPPORTED_COUNTRIES, detect_visitor_currency, get_country_regulation_labels,
    provision_org_categories, get_framework_badge, totp_verify, consume_recovery_code,
    send_system_email
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

    country = request.headers.get("accept-language", "US")[:2].upper()
    geo = detect_visitor_currency(country)

    return templates.TemplateResponse(request=request, name="landing.html", context={
        "page_title": "ADRS — Automated Data Retention Solution",
        "wl_name": "ADRS",
        "wl_footer": "3Consulting Limited",
        "geo_currency": geo["code"],
        "geo_symbol": geo["symbol"],
        "geo_rate_yearly": "{:,.2f}".format(399 * geo["rate"]),
        "geo_rate_monthly": "{:,.2f}".format(40 * geo["rate"]),
    })

@router.get("/login", response_class=HTMLResponse)
def view_login(request: Request):
    session = get_session(request)
    if session and "user_id" in session:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(request=request, name="login.html", context={
        "page_title": "Sign In — ADRS",
        "wl_name": "ADRS",
        "wl_footer": "3Consulting Limited"
    })

@router.post("/login")
def handle_login(
    response: Response,
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(request=request, name="login.html", context={
            "page_title": "Sign In — ADRS",
            "wl_name": "ADRS",
            "wl_footer": "3Consulting Limited",
            "flash_error": "Invalid email credentials or inactive account."
        })

    # Check 2FA
    if user.twofa_enabled:
        redir = RedirectResponse(url="/login/2fa", status_code=303)
        set_session(redir, {"2fa_pending_user": user.id})
        return redir

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    
    session_data = {
        "user_id": user.id,
        "user_name": user.name,
        "email": user.email,
        "role": user.role,
        "org_id": org.id,
        "org_name": org.name,
        "org_domain": org.primary_domain,
        "org_status": org.status,
        "country": org.country or "OTHER",
        "is_platform_admin": user.is_platform_admin
    }
    
    user.last_login_at = datetime.utcnow()
    db.commit()

    redir = RedirectResponse(url="/dashboard", status_code=303)
    set_session(redir, session_data)
    return redir

@router.get("/login/2fa", response_class=HTMLResponse)
def view_2fa(request: Request):
    session = get_session(request)
    if not session or "2fa_pending_user" not in session:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(request=request, name="twofa_challenge.html", context={
        "page_title": "Two-Factor Authentication — ADRS",
        "wl_name": "ADRS"
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

    ok = False
    if totp_verify(user.twofa_secret, code):
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
        session_data = {
            "user_id": user.id,
            "user_name": user.name,
            "email": user.email,
            "role": user.role,
            "org_id": org.id,
            "org_name": org.name,
            "org_domain": org.primary_domain,
            "org_status": org.status,
            "country": org.country or "OTHER",
            "is_platform_admin": user.is_platform_admin
        }
        user.last_login_at = datetime.utcnow()
        db.commit()

        redir = RedirectResponse(url="/dashboard", status_code=303)
        set_session(redir, session_data)
        return redir

    return templates.TemplateResponse(request=request, name="twofa_challenge.html", context={
        "page_title": "Two-Factor Authentication — ADRS",
        "wl_name": "ADRS",
        "error": "Invalid verification code or recovery code."
    })

@router.get("/forgot_password", response_class=HTMLResponse)
def view_forgot_password(request: Request):
    return templates.TemplateResponse(request=request, name="forgot_password.html", context={
        "page_title": "Forgot Password — ADRS",
        "wl_name": "ADRS"
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
        subject = "Reset your password — ADRS"
        html = f"""
        <p>Hello,</p>
        <p>We received a request to reset the password for your ADRS account.</p>
        <p><a href="{reset_link}">Click here to set a new password</a></p>
        <p>This link is valid for 1 hour.</p>
        <p>If you did not request this, please ignore this email.</p>
        """
        send_system_email(db, email, subject, html)

    return templates.TemplateResponse(request=request, name="forgot_password.html", context={
        "page_title": "Forgot Password — ADRS",
        "wl_name": "ADRS",
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
        "page_title": "Set New Password — ADRS",
        "wl_name": "ADRS",
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
            "page_title": "Set New Password — ADRS",
            "wl_name": "ADRS",
            "valid_token": False
        })

    if password != password_confirm:
        return templates.TemplateResponse(request=request, name="reset_password.html", context={
            "page_title": "Set New Password — ADRS",
            "wl_name": "ADRS",
            "valid_token": True,
            "email": email,
            "token": token,
            "error": "Passwords do not match."
        })

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if user:
        user.password_hash = hash_password(password)
        reset.used = True
        db.commit()

    return templates.TemplateResponse(request=request, name="reset_password.html", context={
        "page_title": "Set New Password — ADRS",
        "wl_name": "ADRS",
        "ok": True
    })

@router.get("/register", response_class=HTMLResponse)
def view_register(request: Request):
    session = get_session(request)
    if session and "user_id" in session:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(request=request, name="register.html", context={
        "page_title": "Start Free Trial — ADRS",
        "countries": ADRS_SUPPORTED_COUNTRIES,
        "wl_name": "ADRS",
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
    country: str = Form(...),
    db: Session = Depends(get_db)
):
    domain_exists = db.query(Organization).filter(Organization.primary_domain == domain).first()
    email_exists = db.query(User).filter(User.email == email).first()

    if domain_exists or email_exists:
        err = "Domain already registered." if domain_exists else "Email address already registered."
        return templates.TemplateResponse(request=request, name="register.html", context={
            "page_title": "Start Free Trial — ADRS",
            "countries": ADRS_SUPPORTED_COUNTRIES,
            "wl_name": "ADRS",
            "wl_footer": "3Consulting Limited",
            "flash_error": err
        })

    org = Organization(
        name=org_name,
        slug=org_name.lower().replace(" ", "-"),
        primary_domain=domain,
        country=country,
        tier="core",
        status="trial",
        subscription_status="trial"
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
        email_verified_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    session_data = {
        "user_id": user.id,
        "user_name": user.name,
        "email": user.email,
        "role": user.role,
        "org_id": org.id,
        "org_name": org.name,
        "org_domain": org.primary_domain,
        "org_status": org.status,
        "country": org.country or "OTHER",
        "is_platform_admin": user.is_platform_admin
    }

    redir = RedirectResponse(url="/dashboard", status_code=303)
    set_session(redir, session_data)
    return redir

@router.get("/logout")
def handle_logout(response: Response):
    redir = RedirectResponse(url="/", status_code=303)
    clear_session(redir)
    return redir
