"""
Additional in-app routes: Audit Log, Notifications, Users, Settings, Profile, Billing,
Integrations, and Reports. These complete the sidebar navigation for the Python port.
"""
from app.core.csvsafe import safe_csv_writer
from app.core.clock import business_today
import os
import json
import hashlib
import secrets
import csv
import io
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, desc, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AuditLog, User, Notification, Organization, DataCategory, DataRecord,
    SystemSetting, OrganizationSetting, ConnectedSystem, ApiKey,
    IntakeQueue, DisposalDispatch, IntegrationLog, WebhookEndpoint,
    AutoCategorizationRule, FieldMapping, OrganizationInvitation
)
from app.auth import get_session, hash_password, verify_password, set_session, encrypt_totp_secret, decrypt_totp_secret
from app.config import APP_URL
from app.helpers import get_country_regulation_labels, get_framework_badge, send_system_email, log_audit

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)
templates.env.globals['get_framework_badge'] = get_framework_badge
templates.env.globals['unread_notifications_count'] = 0

router = APIRouter()

VALID_ROLES = ("admin", "dpo", "data_owner")
NUMERIC_SETTINGS = {
    "default_retention_days": (0, 36500),
    "escalation_days": (0, 365),
    "consent_disposal_days": (0, 3650),
    "notify_days_before_expiry": (0, 365),
}


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
def _ctx(session, labels, extra: dict = None):
    extra = extra or {}
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
def view_audit_log(request: Request, page: int = 1, action: str = "", entity_type: str = "", q_search: str = "", start_date: str = "", end_date: str = "", db: Session = Depends(get_db)):
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
    if q_search:
        q = q.filter(or_(AuditLog.action.ilike(f"%{q_search}%"), AuditLog.entity_type.ilike(f"%{q_search}%")))
    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            q = q.filter(AuditLog.created_at >= sd)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            q = q.filter(AuditLog.created_at < ed)
        except ValueError:
            pass

    total = q.count()
    per_page = 50
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(1, page), pages)
    offset = (page - 1) * per_page

    rows = q.order_by(AuditLog.id.desc()).offset(offset).limit(per_page).all()

    # P1 fix: Use engine's verify_audit_chain() instead of full in-line table scan
    from app.engine import verify_audit_chain
    chain_result = verify_audit_chain(db, org_id=org_id)
    chain_valid = chain_result["ok"]

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
        "filter_search": q_search,
        "filter_start_date": start_date,
        "filter_end_date": end_date,
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
    writer = safe_csv_writer(output)
    writer.writerow(["Log ID", "Timestamp", "Action", "Entity Type", "Entity ID", "Performed By", "IP Address", "Row Hash"])

    for l in logs:
        writer.writerow([
            l.id, l.created_at, l.action, l.entity_type, l.entity_id or "",
            users.get(l.performed_by, "System / Automated"),
            l.ip_address or "127.0.0.1", l.row_hash or ""
        ])

    log_audit(db, org_id, "audit_log_exported", "audit_log", None, session["user_id"], {"count": len(logs)}, request.client.host if request.client else None)

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=SafeData_audit_log.csv"}
    )



# ═══════════════════════════════════════════════════════════════════════════
#   NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/notifications", response_class=HTMLResponse)
def view_notifications(request: Request, filter: str = "all", db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    query = db.query(Notification).filter(
        Notification.organization_id == org_id,
        Notification.recipient_id == user_id
    )

    if filter == "unread":
        query = query.filter(Notification.read_at == None)
    elif filter == "warning":
        query = query.filter(Notification.type.in_(["retention_warning", "escalation"]))
    elif filter == "disposal":
        query = query.filter(Notification.type == "disposal_complete")
    elif filter == "recalculation":
        query = query.filter(Notification.type == "recalculation_needed")

    notifications = query.order_by(Notification.id.desc()).limit(100).all()
    unread_count = db.query(Notification).filter(
        Notification.organization_id == org_id,
        Notification.recipient_id == user_id,
        Notification.read_at == None
    ).count()

    return templates.TemplateResponse(request=request, name="notifications.html", context=_ctx(session, labels, {
        "page_title": "Notification Inbox",
        "active_nav": "notifications",
        "notifications": notifications,
        "current_filter": filter,
        "unread_count": unread_count,
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


@router.post("/notifications/read-all")
def mark_all_notifications_read(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    user_id = session["user_id"]
    org_id = session["org_id"]
    db.query(Notification).filter(
        Notification.organization_id == org_id,
        Notification.recipient_id == user_id,
        Notification.read_at == None
    ).update({"read_at": datetime.now(timezone.utc)}, synchronize_session=False)
    db.commit()

    log_audit(db, org_id, "notifications_marked_all_read", "notification", None, user_id, None, request.client.host if request.client else None)
    return RedirectResponse(url="/notifications", status_code=303)


@router.post("/notifications/clear")
def clear_read_notifications(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    user_id = session["user_id"]
    org_id = session["org_id"]
    db.query(Notification).filter(
        Notification.organization_id == org_id,
        Notification.recipient_id == user_id,
        Notification.read_at != None
    ).delete(synchronize_session=False)
    db.commit()

    log_audit(db, org_id, "notifications_cleared", "notification", None, user_id, None, request.client.host if request.client else None)
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
    email = email.strip().lower()
    name = name.strip()
    if role not in VALID_ROLES or not name or "@" not in email:
        return RedirectResponse(url="/users?error=invalid_input", status_code=303)
    from app.auth import password_policy_error
    if password_policy_error(password, email, name):
        return RedirectResponse(url="/users?error=weak_password", status_code=303)
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
        must_change_password=True,
        email_verified_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(new_user)
    db.commit()
    log_audit(db, org_id, "user_created", "user", new_user.id, session["user_id"],
              {"email": email, "role": role}, request.client.host if request.client else None)
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
    if role not in VALID_ROLES or not name.strip() or "@" not in email:
        return RedirectResponse(url="/users?error=invalid_input", status_code=303)
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

    # Built from the configured address, never from the Host header the caller sent.
    from app.helpers import email_team_invite
    invite_url = f"{APP_URL}/invite/accept?token={raw_token}"
    subject, html = email_team_invite(name.strip(), session["org_name"], role, invite_url)
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
        return RedirectResponse(url=f"/invite/accept?token={quote(token)}&error=invalid", status_code=303)
    from app.auth import password_policy_error
    if password_policy_error(password, invite.email, invite.name):
        return RedirectResponse(url=f"/invite/accept?token={quote(token)}&error=weak_password", status_code=303)
    if db.query(User).filter(User.email == invite.email).first():
        return RedirectResponse(url=f"/invite/accept?token={quote(token)}&error=invalid", status_code=303)

    pwd = hash_password(password)
    user = User(
        organization_id=invite.organization_id,
        name=invite.name,
        email=invite.email,
        password_hash=pwd,
        role=invite.role,
        is_active=True,
        email_verified_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(user)
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()
    log_audit(db, invite.organization_id, "invitation_accepted", "user", user.id, user.id,
              {"email": invite.email, "role": invite.role}, request.client.host if request.client else None)

    return RedirectResponse(url="/login?accepted=1", status_code=303)

@router.get("/legal", response_class=HTMLResponse)
def view_legal(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    labels = get_country_regulation_labels(session.get("country", "OTHER") if session else "OTHER")

    return templates.TemplateResponse(request=request, name="legal.html", context={
        "page_title": "Legal & Terms of Service",
        "wl_name": "SafeData",
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
        log_audit(db, session["org_id"], "user_activated" if user.is_active else "user_deactivated",
                  "user", user.id, session["user_id"], {"email": user.email},
                  request.client.host if request.client else None)
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
    # Email/SMTP is a platform infrastructure setting owned by 3Consulting.
    # It is configured via environment variables on the hosting platform (Render),
    # NOT stored in or exposed through the application UI.
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
            totp_uri_val = totp_uri(setup_secret, user.email, "SafeData")
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
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(timezone)
        except Exception:
            timezone = "Africa/Lagos"

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
        bad = []
        clean = {}
        for key in section["keys"]:
            if key in form:
                val = str(form[key]).strip()
                if key.endswith("_pass") and val == "":
                    continue  # Don't overwrite passwords with blanks
                if key in NUMERIC_SETTINGS:
                    lo, hi = NUMERIC_SETTINGS[key]
                    if not val.isdigit() or not (lo <= int(val) <= hi):
                        bad.append(section["keys"][key]["label"])
                        continue
                elif key == "default_disposal_method" and val not in ("delete", "anonymise", "archive"):
                    bad.append(section["keys"][key]["label"])
                    continue
                elif key == "enable_email_notifications" and val not in ("0", "1"):
                    bad.append(section["keys"][key]["label"])
                    continue
                clean[key] = val
        if bad:
            session["settings_error"] = "Check these settings: " + ", ".join(bad) + "."
            redir = RedirectResponse(url=f"/settings?tab=general&sub_tab={sub_tab}", status_code=303)
            set_session(redir, session)
            return redir
        for key, val in clean.items():
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
            user.twofa_secret = encrypt_totp_secret(setup_secret)
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
    current_password: str = Form(""),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    user = db.query(User).filter(User.id == session["user_id"]).first()
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    from app.auth import password_policy_error, check_password_history, record_password_history, password_fingerprint
    email = (email or "").strip().lower()
    name = (name or "").strip() or user.name
    email_changed = bool(email) and email != user.email
    # Changing the password or the sign-in e-mail needs the current password, so a stolen
    # session alone cannot take over the account. (A forced first change is exempt: the
    # person has just signed in with the temporary password.)
    if (password or email_changed) and not user.must_change_password:
        if not verify_password(current_password, user.password_hash):
            return RedirectResponse(url="/profile?error=" + quote("Enter your current password to change your password or e-mail."), status_code=303)

    user.name = name
    if email_changed:
        existing = db.query(User).filter(User.email == email, User.id != user.id).first()
        if existing or "@" not in email:
            return RedirectResponse(url="/profile?error=" + quote("That e-mail address cannot be used."), status_code=303)
        user.email = email
        session["email"] = email

    new_hash = None
    if password:
        policy_err = password_policy_error(password, user.email, user.name)
        if policy_err:
            return RedirectResponse(url="/profile?error=" + quote(policy_err), status_code=303)
        if check_password_history(db, user.id, password) or verify_password(password, user.password_hash):
            return RedirectResponse(url="/profile?error=" + quote("Choose a password you have not used recently."), status_code=303)
        new_hash = hash_password(password)
        user.password_hash = new_hash
        user.must_change_password = False
        session["must_change_password"] = False
        session["pw_fp"] = password_fingerprint(new_hash)

    db.commit()
    if new_hash:
        record_password_history(db, user.id, new_hash)
    log_audit(db, user.organization_id, "profile_updated", "user", user.id, user.id,
              {"password_changed": bool(new_hash), "email_changed": email_changed},
              request.client.host if request.client else None)
    res = RedirectResponse(url="/profile?saved=1", status_code=303)
    # F1 fix: always persist the updated session (e.g. must_change_password flag)
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
def view_reports(
    request: Request,
    range: str = "ytd",
    start_date: str = "",
    end_date: str = "",
    category_id: int = 0,
    role_filter: str = "all",
    status: str = "all",
    page: int = 1,
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session["role"] not in ("admin", "dpo"):
        raise HTTPException(status_code=403, detail="Access denied")

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    from datetime import date as _date, timedelta
    from app.engine import (
        records_by_category, compliance_scorecard_details,
        build_compliance_report, disposals_by_month,
    )

    today = business_today()
    start_d = None
    end_d = today

    if range == "30d":
        start_d = today - timedelta(days=30)
    elif range == "90d":
        start_d = today - timedelta(days=90)
    elif range == "ytd":
        start_d = _date(today.year, 1, 1)
    elif range == "1y":
        start_d = today - timedelta(days=365)
    elif range == "custom":
        if start_date:
            try:
                start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                start_d = None
        if end_date:
            try:
                end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                end_d = today
    elif range == "all":
        start_d = None
        end_d = None

    # Base query for records
    q = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    )

    if category_id > 0:
        q = q.filter(DataRecord.category_id == category_id)

    if status != "all" and status:
        q = q.filter(DataRecord.status == status)

    if start_d:
        q = q.filter(DataRecord.collection_date >= start_d)
    if end_d:
        q = q.filter(DataRecord.collection_date <= end_d)

    if role_filter == "processor":
        q = q.filter(DataRecord.processor_name != None, DataRecord.processor_name != "")
    elif role_filter == "controller":
        q = q.filter(or_(DataRecord.processor_name == None, DataRecord.processor_name == ""))

    total_filtered = q.count()
    per_page = 15
    pages = max(1, (total_filtered + per_page - 1) // per_page)
    page = min(max(1, page), pages)
    offset = (page - 1) * per_page
    records_sample = q.order_by(DataRecord.collection_date.desc()).offset(offset).limit(per_page).all()

    # Category stats
    cats = db.query(DataCategory).filter(
        DataCategory.organization_id == org_id, DataCategory.deleted_at == None
    ).all()

    cat_stats = []
    for c in cats:
        cnt = db.query(func.count(DataRecord.id)).filter(
            DataRecord.organization_id == org_id,
            DataRecord.category_id == c.id,
            DataRecord.deleted_at == None
        ).scalar() or 0
        cat_stats.append({
            "id": c.id,
            "name": c.name,
            "framework": c.compliance_framework,
            "processing_role": c.processing_role or "controller",
            "processor_name": c.processor_name or "",
            "count": cnt,
        })

    # Status counts
    status_counts = {}
    for s in ["active", "due_review", "disposal_requested", "legal_hold", "disposed"]:
        sq = db.query(func.count(DataRecord.id)).filter(
            DataRecord.organization_id == org_id,
            DataRecord.status == s,
            DataRecord.deleted_at == None
        )
        if start_d:
            sq = sq.filter(DataRecord.collection_date >= start_d)
        if end_d:
            sq = sq.filter(DataRecord.collection_date <= end_d)
        status_counts[s] = sq.scalar() or 0

    scorecard = compliance_scorecard_details(db, org_id)
    disposal_chart = disposals_by_month(db, org_id, months=12)

    return templates.TemplateResponse(request=request, name="reports.html", context=_ctx(session, labels, {
        "page_title": "Analytics & Reports",
        "active_nav": "reports",
        "cat_stats": cat_stats,
        "categories": cats,
        "status_counts": status_counts,
        "total_records": total_filtered,
        "scorecard": scorecard,
        "disposal_chart": disposal_chart,
        "records_sample": records_sample,
        "page_num": page,
        "total_pages": pages,
        "filter_range": range,
        "filter_start_date": start_date or (start_d.isoformat() if start_d else ""),
        "filter_end_date": end_date or (end_d.isoformat() if end_d else ""),
        "filter_category_id": category_id,
        "filter_role": role_filter,
        "filter_status": status,
    }))


@router.get("/reports/csv")
def export_reports_csv(
    request: Request,
    range: str = "ytd",
    start_date: str = "",
    end_date: str = "",
    category_id: int = 0,
    role_filter: str = "all",
    status: str = "all",
    db: Session = Depends(get_db)
):
    """Export filtered compliance and retention inventory report as CSV."""
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session["role"] not in ("admin", "dpo"):
        raise HTTPException(status_code=403, detail="Access denied")

    from datetime import date as _date, timedelta
    import csv, io
    from fastapi.responses import StreamingResponse

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    today = business_today()
    start_d = None
    end_d = today

    if range == "30d":
        start_d = today - timedelta(days=30)
    elif range == "90d":
        start_d = today - timedelta(days=90)
    elif range == "ytd":
        start_d = _date(today.year, 1, 1)
    elif range == "1y":
        start_d = today - timedelta(days=365)
    elif range == "custom":
        if start_date:
            try:
                start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                start_d = None
        if end_date:
            try:
                end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                end_d = today

    q = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    )

    if category_id > 0:
        q = q.filter(DataRecord.category_id == category_id)
    if status != "all" and status:
        q = q.filter(DataRecord.status == status)
    if start_d:
        q = q.filter(DataRecord.collection_date >= start_d)
    if end_d:
        q = q.filter(DataRecord.collection_date <= end_d)
    if role_filter == "processor":
        q = q.filter(DataRecord.processor_name != None, DataRecord.processor_name != "")
    elif role_filter == "controller":
        q = q.filter(or_(DataRecord.processor_name == None, DataRecord.processor_name == ""))

    records = q.order_by(DataRecord.collection_date.desc()).all()

    output = io.StringIO()
    writer = safe_csv_writer(output)
    writer.writerow([f"{labels['law']} — Data Retention & Compliance Audit Report"])
    writer.writerow(["Generated At", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")])
    writer.writerow(["Filter Range", range, "Start Date", start_d.isoformat() if start_d else "All", "End Date", end_d.isoformat() if end_d else "All"])
    writer.writerow(["Total Records", len(records)])
    writer.writerow([])
    writer.writerow(["Record ID", "Reference", "Category", "Processing Role", "Processor Name", "Collection Date", "Retention End Date", "Status", "Legal Hold", "Disposed At"])

    for r in records:
        cat_name = r.category.name if r.category else "Unassigned"
        proc_role = r.category.processing_role if r.category else "controller"
        writer.writerow([
            r.id,
            r.record_reference,
            cat_name,
            proc_role,
            r.processor_name or (r.category.processor_name if r.category else "") or "In-House",
            r.collection_date.isoformat() if r.collection_date else "",
            r.retention_end_date.isoformat() if r.retention_end_date else "Pending Trigger",
            r.status,
            "Yes" if r.legal_hold else "No",
            r.disposed_at.strftime("%Y-%m-%d %H:%M") if r.disposed_at else ""
        ])

    log_audit(db, org_id, "report_exported_csv", "report", None, session["user_id"], {
        "range": range,
        "count": len(records)
    }, request.client.host if request.client else None)

    output.seek(0)
    filename = f"retention_report_{range}_{today.isoformat()}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/reports/json")
def export_reports_json(
    request: Request,
    range: str = "ytd",
    start_date: str = "",
    end_date: str = "",
    category_id: int = 0,
    role_filter: str = "all",
    status: str = "all",
    db: Session = Depends(get_db)
):
    """Export filtered compliance report in structured JSON format."""
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session["role"] not in ("admin", "dpo"):
        raise HTTPException(status_code=403, detail="Access denied")

    from datetime import date as _date, timedelta
    from app.engine import compliance_scorecard_details

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    today = business_today()
    start_d = None
    end_d = today

    if range == "30d":
        start_d = today - timedelta(days=30)
    elif range == "90d":
        start_d = today - timedelta(days=90)
    elif range == "ytd":
        start_d = _date(today.year, 1, 1)
    elif range == "1y":
        start_d = today - timedelta(days=365)
    elif range == "custom":
        if start_date:
            try:
                start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                start_d = None
        if end_date:
            try:
                end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                end_d = today

    q = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    )

    if category_id > 0:
        q = q.filter(DataRecord.category_id == category_id)
    if status != "all" and status:
        q = q.filter(DataRecord.status == status)
    if start_d:
        q = q.filter(DataRecord.collection_date >= start_d)
    if end_d:
        q = q.filter(DataRecord.collection_date <= end_d)
    if role_filter == "processor":
        q = q.filter(DataRecord.processor_name != None, DataRecord.processor_name != "")
    elif role_filter == "controller":
        q = q.filter(or_(DataRecord.processor_name == None, DataRecord.processor_name == ""))

    records = q.order_by(DataRecord.collection_date.desc()).all()
    scorecard = compliance_scorecard_details(db, org_id)

    payload = {
        "report_title": f"{labels['law']} Data Retention Compliance Audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "organization_id": org_id,
        "filter": {
            "range": range,
            "start_date": start_d.isoformat() if start_d else None,
            "end_date": end_d.isoformat() if end_d else None,
            "category_id": category_id,
            "role": role_filter,
            "status": status
        },
        "scorecard": scorecard,
        "total_records": len(records),
        "records": [
            {
                "id": r.id,
                "reference": r.record_reference,
                "category": r.category.name if r.category else None,
                "processing_role": r.category.processing_role if r.category else "controller",
                "processor_name": r.processor_name or (r.category.processor_name if r.category else None),
                "collection_date": r.collection_date.isoformat() if r.collection_date else None,
                "retention_end_date": r.retention_end_date.isoformat() if r.retention_end_date else None,
                "status": r.status,
                "legal_hold": r.legal_hold,
                "disposed_at": r.disposed_at.isoformat() if r.disposed_at else None,
            }
            for r in records
        ]
    }

    log_audit(db, org_id, "report_exported_json", "report", None, session["user_id"], {
        "range": range,
        "count": len(records)
    }, request.client.host if request.client else None)

    import json
    from fastapi.responses import Response
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=compliance_report_{range}_{today.isoformat()}.json"}
    )


@router.get("/reports/print", response_class=HTMLResponse)
def print_reports(
    request: Request,
    range: str = "ytd",
    start_date: str = "",
    end_date: str = "",
    category_id: int = 0,
    role_filter: str = "all",
    status: str = "all",
    db: Session = Depends(get_db)
):
    """Render clean printable audit report pack."""
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session["role"] not in ("admin", "dpo"):
        raise HTTPException(status_code=403, detail="Access denied")

    from datetime import date as _date, timedelta
    from app.engine import compliance_scorecard_details

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    today = business_today()
    start_d = None
    end_d = today

    if range == "30d":
        start_d = today - timedelta(days=30)
    elif range == "90d":
        start_d = today - timedelta(days=90)
    elif range == "ytd":
        start_d = _date(today.year, 1, 1)
    elif range == "1y":
        start_d = today - timedelta(days=365)
    elif range == "custom":
        if start_date:
            try:
                start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                start_d = None
        if end_date:
            try:
                end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                end_d = today

    q = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    )

    if category_id > 0:
        q = q.filter(DataRecord.category_id == category_id)
    if status != "all" and status:
        q = q.filter(DataRecord.status == status)
    if start_d:
        q = q.filter(DataRecord.collection_date >= start_d)
    if end_d:
        q = q.filter(DataRecord.collection_date <= end_d)
    if role_filter == "processor":
        q = q.filter(DataRecord.processor_name != None, DataRecord.processor_name != "")
    elif role_filter == "controller":
        q = q.filter(or_(DataRecord.processor_name == None, DataRecord.processor_name == ""))

    records = q.order_by(DataRecord.collection_date.desc()).all()
    scorecard = compliance_scorecard_details(db, org_id)

    log_audit(db, org_id, "report_printed", "report", None, session["user_id"], {
        "range": range,
        "count": len(records)
    }, request.client.host if request.client else None)

    return templates.TemplateResponse(request=request, name="reports_print.html", context=_ctx(session, labels, {
        "page_title": f"Compliance Audit Report — {session['org_name']}",
        "scorecard": scorecard,
        "records": records,
        "generated_at": datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC"),
        "filter_range": range,
        "filter_start_date": start_d.isoformat() if start_d else "Inception",
        "filter_end_date": end_d.isoformat() if end_d else today.isoformat(),
        "filter_role": role_filter,
        "filter_status": status,
    }))


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
