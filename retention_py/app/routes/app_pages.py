"""
Additional in-app routes: Audit Log, Notifications, Users, Settings, Profile, Billing,
Integrations, and Reports. These complete the sidebar navigation for the Python port.
"""
import os
import json
import hashlib
import secrets
import csv
import io
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AuditLog, User, Notification, Organization, DataCategory, DataRecord,
    SystemSetting, OrganizationSetting, ConnectedSystem, ApiKey,
    IntakeQueue, DisposalDispatch, IntegrationLog, WebhookEndpoint,
    AutoCategorizationRule, FieldMapping, OrganizationInvitation
)
from app.auth import get_session, hash_password, set_session
from app.helpers import get_country_regulation_labels, get_framework_badge, send_system_email

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)
templates.env.globals['get_framework_badge'] = get_framework_badge
templates.env.globals['unread_notifications_count'] = 0

router = APIRouter()

# ---------------------------------------------------------------------------
#   Helper: get a setting for an org (returns value or default)
# ---------------------------------------------------------------------------
def _get_org_setting(db: Session, org_id: int, key: str, default: str = "") -> str:
    row = db.query(OrganizationSetting).filter(
        OrganizationSetting.organization_id == org_id,
        OrganizationSetting.setting_key == key
    ).first()
    if row:
        return row.setting_value
    sys_row = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    return sys_row.setting_value if sys_row else default


def _set_org_setting(db: Session, org_id: int, key: str, value: str):
    row = db.query(OrganizationSetting).filter(
        OrganizationSetting.organization_id == org_id,
        OrganizationSetting.setting_key == key
    ).first()
    if row:
        row.setting_value = value
    else:
        db.add(OrganizationSetting(
            organization_id=org_id, setting_key=key, setting_value=value
        ))
    db.commit()


# ---------------------------------------------------------------------------
#   Common context builder
# ---------------------------------------------------------------------------
def _ctx(session, labels, extra: dict = {}):
    base = {
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "is_platform_admin": session.get("is_platform_admin", False)
    }
    base.update(extra)
    return base


# ═══════════════════════════════════════════════════════════════════════════
#   AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/audit", response_class=HTMLResponse)
def view_audit_log(request: Request, page: int = 1, action: str = "", entity_type: str = "", db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session["role"] not in ("admin", "dpo"):
        raise HTTPException(status_code=403, detail="Access denied")

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    # Build query
    q = db.query(AuditLog).filter(AuditLog.organization_id == org_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)

    total = q.count()
    per_page = 50
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(1, page), pages)
    offset = (page - 1) * per_page

    rows = q.order_by(AuditLog.id.desc()).offset(offset).limit(per_page).all()

    # Verify SHA-256 HMAC cryptographic chain for this org
    all_logs = db.query(AuditLog).filter(AuditLog.organization_id == org_id).order_by(AuditLog.id.asc()).all()
    chain_valid = True
    prev_h = "0" * 64
    for r in all_logs:
        details_str = str(r.details or {})
        payload = f"{r.organization_id}|{r.action}|{r.entity_type}|{r.entity_id}|{r.performed_by}|{details_str}|{r.ip_address}|{prev_h}"
        computed = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        if r.row_hash and r.row_hash != computed:
            chain_valid = False
            break
        prev_h = r.row_hash or prev_h

    # Distinct actions for filter dropdown
    actions = [r[0] for r in db.query(AuditLog.action).filter(
        AuditLog.organization_id == org_id
    ).distinct().order_by(AuditLog.action).all()]

    # Fetch user names for performed_by
    user_map = {}
    user_ids = set(r.performed_by for r in rows if r.performed_by)
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u.name for u in users}

    return templates.TemplateResponse(request=request, name="audit.html", context=_ctx(session, labels, {
        "page_title": "Audit Log",
        "active_nav": "audit",
        "rows": rows,
        "user_map": user_map,
        "actions": actions,
        "filter_action": action,
        "filter_entity": entity_type,
        "page_num": page,
        "total_pages": pages,
        "total": total,
        "chain_valid": chain_valid
    }))


@router.get("/audit/export")
def export_audit_csv(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session["role"] not in ("admin", "dpo"):
        raise HTTPException(status_code=403, detail="Access denied")

    org_id = session["org_id"]
    logs = db.query(AuditLog).filter(AuditLog.organization_id == org_id).order_by(AuditLog.id.desc()).all()

    users = {u.id: u.name for u in db.query(User).filter(User.organization_id == org_id).all()}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Log ID", "Timestamp", "Action", "Entity Type", "Entity ID", "Performed By", "IP Address", "Row Hash"])

    for l in logs:
        writer.writerow([
            l.id, l.created_at, l.action, l.entity_type, l.entity_id or "",
            users.get(l.performed_by, "System / Automated"),
            l.ip_address or "127.0.0.1", l.row_hash or ""
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=adrs_audit_log.csv"}
    )



# ═══════════════════════════════════════════════════════════════════════════
#   NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/notifications", response_class=HTMLResponse)
def view_notifications(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    notifications = db.query(Notification).filter(
        Notification.organization_id == org_id,
        Notification.recipient_id == user_id
    ).order_by(Notification.id.desc()).limit(100).all()

    return templates.TemplateResponse(request=request, name="notifications.html", context=_ctx(session, labels, {
        "page_title": "Notification Inbox",
        "active_nav": "notifications",
        "notifications": notifications,
    }))


@router.post("/notifications/{nid}/read")
def mark_notification_read(nid: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    notif = db.query(Notification).filter(Notification.id == nid, Notification.recipient_id == session["user_id"]).first()
    if notif and not notif.read_at:
        notif.read_at = datetime.now(timezone.utc)
        db.commit()
    return RedirectResponse(url="/notifications", status_code=303)


# ═══════════════════════════════════════════════════════════════════════════
#   TEAM USERS
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/users", response_class=HTMLResponse)
def view_users(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    users = db.query(User).filter(
        User.organization_id == org_id,
        User.deleted_at == None
    ).order_by(User.id).all()

    return templates.TemplateResponse(request=request, name="users.html", context=_ctx(session, labels, {
        "page_title": "Team Users",
        "active_nav": "users",
        "users": users,
    }))


@router.post("/users/create")
def create_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("data_owner"),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or session["role"] != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return RedirectResponse(url="/users?error=email_exists", status_code=303)

    new_user = User(
        organization_id=org_id,
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        email_verified_at=datetime.now(timezone.utc)
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/users", status_code=303)

@router.post("/users/invite")
def invite_user(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    role: str = Form("data_owner"),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or session["role"] != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    email = email.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return RedirectResponse(url="/users?error=email_exists", status_code=303)

    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    invite = OrganizationInvitation(
        organization_id=org_id,
        email=email,
        name=name.strip(),
        role=role,
        token_hash=token_hash,
        invited_by=session["user_id"],
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    db.add(invite)
    db.commit()

    invite_url = f"{request.base_url}invite/accept?token={raw_token}"
    subject = "You have been invited to ADRS"
    html = f"""
    <p>Hello {name},</p>
    <p>You have been invited to join the ADRS workspace for {session['org_name']} as a <strong>{role.upper()}</strong>.</p>
    <p><a href="{invite_url}">Click here to accept invitation and set your password</a></p>
    <p>This invitation link is valid for 7 days.</p>
    """
    send_system_email(db, email, subject, html)

    log_audit(db, org_id, "user_invited", "user", None, session["user_id"], {"email": email, "role": role}, request.client.host if request.client else None)
    return RedirectResponse(url="/users?invited=1", status_code=303)

@router.get("/invite/accept", response_class=HTMLResponse)
def view_accept_invite(request: Request, token: str = "", db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    invite = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.token_hash == token_hash,
        OrganizationInvitation.accepted_at == None,
        OrganizationInvitation.revoked_at == None,
        OrganizationInvitation.expires_at > datetime.now(timezone.utc)
    ).first()

    return templates.TemplateResponse(request=request, name="invite_accept.html", context={
        "page_title": "Accept Workspace Invitation",
        "valid_invite": bool(invite),
        "invite": invite,
        "token": token
    })

@router.post("/invite/accept")
def handle_accept_invite(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db)
):
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    invite = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.token_hash == token_hash,
        OrganizationInvitation.accepted_at == None,
        OrganizationInvitation.revoked_at == None,
        OrganizationInvitation.expires_at > datetime.now(timezone.utc)
    ).first()

    if not invite or password != password_confirm:
        return RedirectResponse(url=f"/invite/accept?token={token}&error=invalid", status_code=303)

    pwd = hash_password(password)
    user = User(
        organization_id=invite.organization_id,
        name=invite.name,
        email=invite.email,
        password_hash=pwd,
        role=invite.role,
        is_active=True,
        email_verified_at=datetime.now(timezone.utc)
    )
    db.add(user)
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()

    return RedirectResponse(url="/login?accepted=1", status_code=303)

@router.get("/legal", response_class=HTMLResponse)
def view_legal(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    labels = get_country_regulation_labels(session.get("country", "OTHER") if session else "OTHER")

    return templates.TemplateResponse(request=request, name="legal.html", context={
        "page_title": "Legal & Terms of Service",
        "wl_name": "ADRS",
        "wl_footer": "3Consulting Limited",
        "law_label": labels["law"]
    })

@router.post("/users/{uid}/toggle")
def toggle_user(uid: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session["role"] != "admin":
        return RedirectResponse(url="/login", status_code=303)

    user = db.query(User).filter(User.id == uid, User.organization_id == session["org_id"]).first()
    if user and user.id != session["user_id"]:
        user.is_active = not user.is_active
        db.commit()
    return RedirectResponse(url="/users", status_code=303)


# ═══════════════════════════════════════════════════════════════════════════
#   SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

SETTINGS_SECTIONS = {
    "retention": {
        "label": "Retention Defaults",
        "description": "Default retention periods and disposal behaviour.",
        "keys": {
            "default_retention_days": {"label": "Default Retention Period (days)", "type": "number", "placeholder": "2555"},
            "default_disposal_method": {"label": "Default Disposal Method", "type": "text", "placeholder": "delete"},
            "escalation_days": {"label": "Escalation Days After Expiry", "type": "number", "placeholder": "14"},
            "consent_disposal_days": {"label": "Post-Consent Withdrawal Days", "type": "number", "placeholder": "30"},
        }
    },
    "email": {
        "label": "Email / SMTP",
        "description": "Configure SMTP for retention alerts and notifications.",
        "keys": {
            "smtp_host": {"label": "SMTP Host", "type": "text", "placeholder": "mail.yourdomain.com"},
            "smtp_port": {"label": "SMTP Port", "type": "number", "placeholder": "587"},
            "smtp_user": {"label": "SMTP Username", "type": "text", "placeholder": ""},
            "smtp_pass": {"label": "SMTP Password", "type": "password", "placeholder": ""},
            "smtp_from_name": {"label": "Sender Name", "type": "text", "placeholder": "ADRS Notifications"},
            "smtp_from_email": {"label": "Sender Email", "type": "text", "placeholder": "no-reply@yourdomain.com"},
        }
    },
    "notifications": {
        "label": "Notification Rules",
        "description": "Control which events trigger alerts.",
        "keys": {
            "notify_days_before_expiry": {"label": "Warn X Days Before Expiry", "type": "number", "placeholder": "30"},
            "enable_email_notifications": {"label": "Email Notifications (1=on, 0=off)", "type": "text", "placeholder": "1"},
        }
    },
}

@router.get("/settings", response_class=HTMLResponse)
def view_settings(
    request: Request,
    tab: str = "organization",
    sub_tab: str = "retention",
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    org = db.query(Organization).filter(Organization.id == org_id).first()

    context_data = {
        "page_title": "Settings",
        "active_nav": "settings",
        "active_tab": tab,
        "org": org,
        "timezone": "",
        "general_sections": SETTINGS_SECTIONS,
        "sub_tab": sub_tab,
        "active_section": None,
        "fields": {},
        "user": None,
        "setup_secret": "",
        "totp_uri": "",
        "new_recovery": None,
        "error": None
    }

    if tab == "organization":
        timezone = _get_org_setting(db, org_id, "timezone", "Africa/Lagos")
        context_data["timezone"] = timezone

    elif tab == "general":
        if sub_tab not in SETTINGS_SECTIONS:
            sub_tab = "retention"
        section = SETTINGS_SECTIONS[sub_tab]
        fields = {}
        for key, meta in section["keys"].items():
            val = _get_org_setting(db, org_id, key, meta.get("placeholder", ""))
            fields[key] = {"meta": meta, "value": val}
        context_data.update({
            "general_sections": SETTINGS_SECTIONS,
            "sub_tab": sub_tab,
            "active_section": section,
            "fields": fields
        })

    elif tab == "twofa":
        user_id = session["user_id"]
        user = db.query(User).filter(User.id == user_id).first()
        context_data["user"] = user

        if not user.twofa_enabled:
            # Generate setup secret
            setup_secret = session.get("2fa_setup_secret")
            if not setup_secret:
                from app.helpers import totp_generate_secret
                setup_secret = totp_generate_secret()
                # Store in session (in FastAPI session is usually client-side cookie via middleware, 
                # but since set_session handles dict in request.state, we can check how get_session/set_session works in auth.py)
                # Let's write the setup_secret to session dict.
                session["2fa_setup_secret"] = setup_secret
            
            from app.helpers import totp_uri
            totp_uri_val = totp_uri(setup_secret, user.email, "ADRS")
            context_data["setup_secret"] = setup_secret
            context_data["totp_uri"] = totp_uri_val

        # If recovery codes were generated in POST, pass them
        if "new_recovery_codes" in session:
            context_data["new_recovery"] = session["new_recovery_codes"]
            del session["new_recovery_codes"]

    # Retrieve error/success messages
    error_msg = session.pop("settings_error", None)
    if error_msg:
        context_data["error"] = error_msg

    # We must call set_session because we modified the session (added/removed keys)
    res = templates.TemplateResponse(request=request, name="settings.html", context=_ctx(session, labels, context_data))
    set_session(res, session)
    return res


@router.post("/settings/save")
async def save_settings_post(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session["role"] != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]
    form = await request.form()
    tab = form.get("tab", "organization")

    if tab == "organization":
        name = str(form.get("name", "")).strip()
        billing_email = str(form.get("billing_email", "")).strip().lower()
        timezone = str(form.get("timezone", "Africa/Lagos")).strip()

        if not name:
            session["settings_error"] = "Organisation name is required."
            redir = RedirectResponse(url="/settings?tab=organization", status_code=303)
            set_session(redir, session)
            return redir

        org = db.query(Organization).filter(Organization.id == org_id).first()
        org.name = name
        org.billing_email = billing_email
        db.commit()

        _set_org_setting(db, org_id, "white_label_name", name)
        _set_org_setting(db, org_id, "app_name", name)
        _set_org_setting(db, org_id, "timezone", timezone)

        log_audit(db, org_id, "organisation_updated", "organization", org_id, user_id, {
            "name": name,
            "billing_email": billing_email
        }, request.client.host if request.client else None)

        redir = RedirectResponse(url="/settings?tab=organization&saved=1", status_code=303)
        set_session(redir, session)
        return redir

    elif tab == "general":
        sub_tab = form.get("sub_tab", "retention")
        if sub_tab not in SETTINGS_SECTIONS:
            return RedirectResponse(url="/settings?tab=general", status_code=303)

        section = SETTINGS_SECTIONS[sub_tab]
        for key in section["keys"]:
            if key in form:
                val = str(form[key]).strip()
                if key.endswith("_pass") and val == "":
                    continue  # Don't overwrite passwords with blanks
                _set_org_setting(db, org_id, key, val)

        log_audit(db, org_id, "settings_updated", "system", None, user_id, {
            "action": "settings_updated",
            "tab": sub_tab
        }, request.client.host if request.client else None)

        redir = RedirectResponse(url=f"/settings?tab=general&sub_tab={sub_tab}&saved=1", status_code=303)
        set_session(redir, session)
        return redir

    elif tab == "twofa":
        action = form.get("action", "")
        user = db.query(User).filter(User.id == user_id).first()

        if action == "enable":
            setup_secret = session.get("2fa_setup_secret", "")
            code = str(form.get("code", "")).strip()

            from app.helpers import totp_verify, generate_recovery_codes
            if not setup_secret or not totp_verify(setup_secret, code):
                session["settings_error"] = "Invalid verification code. Try again."
                redir = RedirectResponse(url="/settings?tab=twofa", status_code=303)
                set_session(redir, session)
                return redir

            import json
            rc = generate_recovery_codes(8)
            user.twofa_enabled = True
            user.twofa_secret = setup_secret
            user.twofa_recovery = json.dumps(rc["hashed"])
            db.commit()

            log_audit(db, org_id, "user_updated", "user", user_id, user_id, {
                "twofa": "enabled"
            }, request.client.host if request.client else None)

            # Store recovery codes in session so we show them once
            session["new_recovery_codes"] = rc["plain"]
            if "2fa_setup_secret" in session:
                del session["2fa_setup_secret"]

            redir = RedirectResponse(url="/settings?tab=twofa", status_code=303)
            set_session(redir, session)
            return redir

        elif action == "disable":
            password = str(form.get("password", ""))
            if not verify_password(password, user.password_hash):
                session["settings_error"] = "Incorrect password."
                redir = RedirectResponse(url="/settings?tab=twofa", status_code=303)
                set_session(redir, session)
                return redir

            user.twofa_enabled = False
            user.twofa_secret = None
            user.twofa_recovery = None
            db.commit()

            log_audit(db, org_id, "user_updated", "user", user_id, user_id, {
                "twofa": "disabled"
            }, request.client.host if request.client else None)

            redir = RedirectResponse(url="/settings?tab=twofa&saved=1", status_code=303)
            set_session(redir, session)
            return redir

    return RedirectResponse(url="/settings", status_code=303)



# ═══════════════════════════════════════════════════════════════════════════
#   PROFILE
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/profile", response_class=HTMLResponse)
def view_profile(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    user = db.query(User).filter(User.id == session["user_id"]).first()

    return templates.TemplateResponse(request=request, name="profile.html", context=_ctx(session, labels, {
        "page_title": "My Profile",
        "active_nav": "profile",
        "user": user,
    }))


@router.post("/profile")
def update_profile(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(""),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    user = db.query(User).filter(User.id == session["user_id"]).first()
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    user.name = name
    if email and email != user.email:
        existing = db.query(User).filter(User.email == email, User.id != user.id).first()
        if not existing:
            user.email = email

    if password:
        from app.auth import password_policy_error
        policy_err = password_policy_error(password)
        if policy_err:
            return RedirectResponse(url=f"/profile?error={policy_err}", status_code=303)
        user.password_hash = hash_password(password)
        user.must_change_password = False
        session["must_change_password"] = False

    db.commit()
    res = RedirectResponse(url="/profile?saved=1", status_code=303)
    set_session(res, session)
    return res


# ═══════════════════════════════════════════════════════════════════════════
#   INTEGRATIONS
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/integrations", response_class=HTMLResponse)
def view_integrations(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    systems_count = db.query(func.count(ConnectedSystem.id)).filter(
        ConnectedSystem.organization_id == org_id, ConnectedSystem.is_active == True
    ).scalar() or 0

    keys_count = db.query(func.count(ApiKey.id)).filter(
        ApiKey.organization_id == org_id, ApiKey.is_active == True, ApiKey.revoked_at == None
    ).scalar() or 0

    queue_pending = db.query(func.count(IntakeQueue.id)).filter(
        IntakeQueue.organization_id == org_id, IntakeQueue.status == "pending"
    ).scalar() or 0

    queue_failed = db.query(func.count(IntakeQueue.id)).filter(
        IntakeQueue.organization_id == org_id, IntakeQueue.status == "failed"
    ).scalar() or 0

    dispatch_pending = db.query(func.count(DisposalDispatch.id)).filter(
        DisposalDispatch.organization_id == org_id, DisposalDispatch.status == "pending"
    ).scalar() or 0

    synced = db.query(func.coalesce(func.sum(ConnectedSystem.records_synced), 0)).filter(
        ConnectedSystem.organization_id == org_id
    ).scalar() or 0

    rules_count = db.query(func.count(AutoCategorizationRule.id)).filter(
        AutoCategorizationRule.organization_id == org_id, AutoCategorizationRule.is_active == True
    ).scalar() or 0

    mappings_count = db.query(func.count(FieldMapping.id)).filter(
        FieldMapping.organization_id == org_id
    ).scalar() or 0

    webhooks = db.query(WebhookEndpoint).filter(
        WebhookEndpoint.organization_id == org_id
    ).all()

    return templates.TemplateResponse(request=request, name="integrations.html", context=_ctx(session, labels, {
        "page_title": "Integrations",
        "active_nav": "integrations",
        "systems_count": systems_count,
        "keys_count": keys_count,
        "queue_pending": queue_pending,
        "queue_failed": queue_failed,
        "dispatch_pending": dispatch_pending,
        "synced": synced,
        "rules_count": rules_count,
        "mappings_count": mappings_count,
        "webhooks": webhooks,
    }))


# ═══════════════════════════════════════════════════════════════════════════
#   ANALYTICS & REPORTS
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/reports", response_class=HTMLResponse)
def view_reports(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session["role"] not in ("admin", "dpo"):
        raise HTTPException(status_code=403, detail="Access denied")

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    from app.engine import (
        records_by_category, compliance_score as calc_score,
        build_compliance_report, disposals_by_month,
    )
    from datetime import date as _date

    # Category breakdown (uses analytics library)
    cat_stats_raw = records_by_category(db, org_id, limit=50)
    cat_stats = []
    cats = db.query(DataCategory).filter(
        DataCategory.organization_id == org_id, DataCategory.deleted_at == None
    ).all()
    cat_fw_map = {c.name: c.compliance_framework for c in cats}
    for item in cat_stats_raw:
        cat_stats.append({
            "name": item["category"],
            "framework": cat_fw_map.get(item["category"], ""),
            "count": item["count"],
        })

    # Status breakdown
    status_counts = {}
    for s in ["active", "due_review", "disposal_requested", "legal_hold", "disposed"]:
        status_counts[s] = db.query(func.count(DataRecord.id)).filter(
            DataRecord.organization_id == org_id,
            DataRecord.status == s,
            DataRecord.deleted_at == None
        ).scalar() or 0

    total_records = sum(status_counts.values())
    score = calc_score(db, org_id)

    # Annual report data
    current_year = _date.today().year
    annual_report = build_compliance_report(db, org_id, current_year)

    # Disposal chart data
    disposal_chart = disposals_by_month(db, org_id, months=12)

    return templates.TemplateResponse(request=request, name="reports.html", context=_ctx(session, labels, {
        "page_title": "Analytics & Reports",
        "active_nav": "reports",
        "cat_stats": cat_stats,
        "status_counts": status_counts,
        "total_records": total_records,
        "compliance_score": score,
        "annual_report": annual_report,
        "disposal_chart": disposal_chart,
    }))


@router.get("/reports/csv")
def export_reports_csv(request: Request, db: Session = Depends(get_db)):
    """Export annual compliance report as CSV."""
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session["role"] not in ("admin", "dpo"):
        raise HTTPException(status_code=403, detail="Access denied")

    from app.engine import build_compliance_report, compliance_report_to_csv_rows
    from datetime import date as _date
    import csv, io

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    year = _date.today().year
    report = build_compliance_report(db, org_id, year)
    title = f"{labels['law']} Annual Compliance Report"
    rows = compliance_report_to_csv_rows(report, title)

    output = io.StringIO()
    writer = csv.writer(output)
    for row in rows:
        writer.writerow(row)
    output.seek(0)

    from fastapi.responses import StreamingResponse
    filename = f"compliance_report_{year}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ═══════════════════════════════════════════════════════════════════════════
#   BILLING & SUBSCRIPTION
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/billing", response_class=HTMLResponse)
def view_billing(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    org = db.query(Organization).filter(Organization.id == org_id).first()

    return templates.TemplateResponse(request=request, name="billing.html", context=_ctx(session, labels, {
        "page_title": "Billing & Subscription",
        "active_nav": "billing",
        "org": org,
    }))
