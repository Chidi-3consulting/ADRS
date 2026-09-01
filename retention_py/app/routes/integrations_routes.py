import os
import json
import secrets
import hashlib
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import (
    ConnectedSystem, ApiKey, FieldMapping, AutoCategorizationRule,
    IntakeQueue, DisposalDispatch, IntegrationLog, WebhookEndpoint,
    DataCategory, Organization
)
from app.auth import get_session
from app.helpers import get_country_regulation_labels, get_framework_badge, log_audit

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)
templates.env.globals['get_framework_badge'] = get_framework_badge
templates.env.globals['unread_notifications_count'] = 0

router = APIRouter()

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

# ---------------------------------------------------------------------------
# CONNECTED SYSTEMS
# ---------------------------------------------------------------------------
@router.get("/integrations/systems", response_class=HTMLResponse)
def list_connected_systems(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    systems = db.query(ConnectedSystem).filter(ConnectedSystem.organization_id == org_id).all()

    return templates.TemplateResponse(request=request, name="integrations_systems.html", context=_ctx(session, labels, {
        "page_title": "Connected Systems",
        "active_nav": "integrations",
        "systems": systems
    }))

@router.get("/integrations/systems/create", response_class=HTMLResponse)
def view_create_system(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    return templates.TemplateResponse(request=request, name="integrations_systems_form.html", context=_ctx(session, labels, {
        "page_title": "Add Connected System",
        "active_nav": "integrations",
        "system": None
    }))

@router.post("/integrations/systems/create")
def handle_create_system(
    request: Request,
    name: str = Form(...),
    system_type: str = Form("custom"),
    base_url: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    signing_secret = secrets.token_hex(32)

    sys_obj = ConnectedSystem(
        organization_id=org_id,
        name=name.strip(),
        system_type=system_type,
        base_url=base_url.strip() if base_url else None,
        signing_secret=signing_secret,
        description=description.strip() if description else None,
        created_by=session["user_id"]
    )
    db.add(sys_obj)
    db.commit()

    log_audit(db, org_id, "system_created", "system", sys_obj.id, session["user_id"], {"name": sys_obj.name}, request.client.host if request.client else None)
    return RedirectResponse(url="/integrations/systems", status_code=303)

@router.get("/integrations/systems/edit/{id}", response_class=HTMLResponse)
def view_edit_system(id: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    sys_obj = db.query(ConnectedSystem).filter(ConnectedSystem.id == id, ConnectedSystem.organization_id == org_id).first()
    if not sys_obj:
        raise HTTPException(status_code=404, detail="System not found")

    return templates.TemplateResponse(request=request, name="integrations_systems_form.html", context=_ctx(session, labels, {
        "page_title": f"Edit {sys_obj.name}",
        "active_nav": "integrations",
        "system": sys_obj
    }))

@router.post("/integrations/systems/edit/{id}")
def handle_edit_system(
    id: int,
    request: Request,
    name: str = Form(...),
    system_type: str = Form("custom"),
    base_url: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_active: bool = Form(False),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    sys_obj = db.query(ConnectedSystem).filter(ConnectedSystem.id == id, ConnectedSystem.organization_id == org_id).first()
    if not sys_obj:
        raise HTTPException(status_code=404, detail="System not found")

    sys_obj.name = name.strip()
    sys_obj.system_type = system_type
    sys_obj.base_url = base_url.strip() if base_url else None
    sys_obj.description = description.strip() if description else None
    sys_obj.is_active = is_active
    db.commit()

    log_audit(db, org_id, "system_updated", "system", id, session["user_id"], {"name": sys_obj.name}, request.client.host if request.client else None)
    return RedirectResponse(url="/integrations/systems", status_code=303)

# ---------------------------------------------------------------------------
# API KEYS
# ---------------------------------------------------------------------------
@router.get("/integrations/keys", response_class=HTMLResponse)
def list_api_keys(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    keys = db.query(ApiKey).filter(ApiKey.organization_id == org_id).order_by(ApiKey.id.desc()).all()

    return templates.TemplateResponse(request=request, name="integrations_keys.html", context=_ctx(session, labels, {
        "page_title": "API Keys",
        "active_nav": "integrations",
        "keys": keys
    }))

@router.get("/integrations/keys/create", response_class=HTMLResponse)
def view_create_key(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    systems = db.query(ConnectedSystem).filter(ConnectedSystem.organization_id == org_id, ConnectedSystem.is_active == True).all()

    return templates.TemplateResponse(request=request, name="integrations_keys_create.html", context=_ctx(session, labels, {
        "page_title": "Generate API Key",
        "active_nav": "integrations",
        "systems": systems,
        "new_raw_key": None
    }))

@router.post("/integrations/keys/create")
def handle_create_key(
    request: Request,
    system_id: int = Form(...),
    key_name: str = Form(...),
    rate_limit_per_min: int = Form(60),
    permissions: List[str] = Form(["ingest"]),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    raw_key = f"SafeData_k1_{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    key_prefix = raw_key[:12]

    new_key = ApiKey(
        organization_id=org_id,
        system_id=system_id,
        key_name=key_name.strip(),
        key_hash=key_hash,
        key_prefix=key_prefix,
        permissions=permissions,
        rate_limit_per_min=rate_limit_per_min,
        created_by=session["user_id"]
    )
    db.add(new_key)
    db.commit()

    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    systems = db.query(ConnectedSystem).filter(ConnectedSystem.organization_id == org_id, ConnectedSystem.is_active == True).all()

    log_audit(db, org_id, "api_key_created", "system", new_key.id, session["user_id"], {"key_name": key_name}, request.client.host if request.client else None)

    return templates.TemplateResponse(request=request, name="integrations_keys_create.html", context=_ctx(session, labels, {
        "page_title": "API Key Generated",
        "active_nav": "integrations",
        "systems": systems,
        "new_raw_key": raw_key
    }))

@router.post("/integrations/keys/revoke/{id}")
def handle_revoke_key(id: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    key_obj = db.query(ApiKey).filter(ApiKey.id == id, ApiKey.organization_id == org_id).first()
    if key_obj:
        key_obj.is_active = False
        key_obj.revoked_at = datetime.now(timezone.utc)
        db.commit()
        log_audit(db, org_id, "api_key_revoked", "system", id, session["user_id"], None, request.client.host if request.client else None)

    return RedirectResponse(url="/integrations/keys", status_code=303)

# ---------------------------------------------------------------------------
# FIELD MAPPINGS
# ---------------------------------------------------------------------------
@router.get("/integrations/mappings", response_class=HTMLResponse)
def list_field_mappings(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    mappings = db.query(FieldMapping).filter(FieldMapping.organization_id == org_id).all()

    return templates.TemplateResponse(request=request, name="integrations_mappings.html", context=_ctx(session, labels, {
        "page_title": "Field Mappings",
        "active_nav": "integrations",
        "mappings": mappings
    }))

@router.get("/integrations/mappings/create", response_class=HTMLResponse)
def view_create_mapping(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    systems = db.query(ConnectedSystem).filter(ConnectedSystem.organization_id == org_id, ConnectedSystem.is_active == True).all()
    categories = db.query(DataCategory).filter(DataCategory.organization_id == org_id, DataCategory.deleted_at == None).all()

    return templates.TemplateResponse(request=request, name="integrations_mappings_create.html", context=_ctx(session, labels, {
        "page_title": "Create Field Mapping",
        "active_nav": "integrations",
        "systems": systems,
        "categories": categories
    }))

@router.post("/integrations/mappings/create")
def handle_create_mapping(
    request: Request,
    system_id: int = Form(...),
    external_object_type: str = Form(...),
    category_id: int = Form(...),
    external_field: str = Form(...),
    SafeData_field: str = Form("record_reference"),
    transform: Optional[str] = Form(None),
    is_required: bool = Form(False),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    mapping = FieldMapping(
        organization_id=org_id,
        system_id=system_id,
        external_object_type=external_object_type.strip(),
        category_id=category_id,
        external_field=external_field.strip(),
        SafeData_field=SafeData_field.strip(),
        transform=transform.strip() if transform else None,
        is_required=is_required
    )
    db.add(mapping)
    db.commit()

    return RedirectResponse(url="/integrations/mappings", status_code=303)

@router.post("/integrations/mappings/delete/{id}")
def handle_delete_mapping(id: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    mapping = db.query(FieldMapping).filter(FieldMapping.id == id, FieldMapping.organization_id == org_id).first()
    if mapping:
        db.delete(mapping)
        db.commit()

    return RedirectResponse(url="/integrations/mappings", status_code=303)

# ---------------------------------------------------------------------------
# AUTO-CATEGORIZATION RULES
# ---------------------------------------------------------------------------
@router.get("/integrations/rules", response_class=HTMLResponse)
def list_auto_rules(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    rules = db.query(AutoCategorizationRule).filter(AutoCategorizationRule.organization_id == org_id).order_by(AutoCategorizationRule.priority).all()

    return templates.TemplateResponse(request=request, name="integrations_rules.html", context=_ctx(session, labels, {
        "page_title": "Auto-Categorisation Rules",
        "active_nav": "integrations",
        "rules": rules
    }))

@router.get("/integrations/rules/create", response_class=HTMLResponse)
def view_create_rule(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    systems = db.query(ConnectedSystem).filter(ConnectedSystem.organization_id == org_id, ConnectedSystem.is_active == True).all()
    categories = db.query(DataCategory).filter(DataCategory.organization_id == org_id, DataCategory.deleted_at == None).all()

    return templates.TemplateResponse(request=request, name="integrations_rules_create.html", context=_ctx(session, labels, {
        "page_title": "New Auto-Categorisation Rule",
        "active_nav": "integrations",
        "systems": systems,
        "categories": categories
    }))

@router.post("/integrations/rules/create")
def handle_create_rule(
    request: Request,
    system_id: int = Form(...),
    rule_name: str = Form(...),
    object_type: str = Form(...),
    condition_field: Optional[str] = Form(None),
    condition_value: Optional[str] = Form(None),
    category_id: int = Form(...),
    priority: int = Form(10),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    rule = AutoCategorizationRule(
        organization_id=org_id,
        system_id=system_id,
        rule_name=rule_name.strip(),
        object_type=object_type.strip(),
        condition_field=condition_field.strip() if condition_field else None,
        condition_value=condition_value.strip() if condition_value else None,
        category_id=category_id,
        priority=priority,
        created_by=session["user_id"]
    )
    db.add(rule)
    db.commit()

    return RedirectResponse(url="/integrations/rules", status_code=303)

@router.post("/integrations/rules/delete/{id}")
def handle_delete_rule(id: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    rule = db.query(AutoCategorizationRule).filter(AutoCategorizationRule.id == id, AutoCategorizationRule.organization_id == org_id).first()
    if rule:
        db.delete(rule)
        db.commit()

    return RedirectResponse(url="/integrations/rules", status_code=303)

# ---------------------------------------------------------------------------
# INTAKE QUEUE & DISPATCH & LOGS & TIER
# ---------------------------------------------------------------------------
@router.get("/integrations/queue", response_class=HTMLResponse)
def view_intake_queue(request: Request, status: str = "", db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    q = db.query(IntakeQueue).filter(IntakeQueue.organization_id == org_id)
    if status:
        q = q.filter(IntakeQueue.status == status)

    items = q.order_by(IntakeQueue.id.desc()).limit(100).all()
    return templates.TemplateResponse(request=request, name="integrations_queue.html", context=_ctx(session, labels, {
        "page_title": "Intake Queue",
        "active_nav": "integrations",
        "items": items,
        "filter_status": status
    }))

@router.get("/integrations/dispatch", response_class=HTMLResponse)
def view_disposal_dispatch(request: Request, status: str = "", db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    q = db.query(DisposalDispatch).filter(DisposalDispatch.organization_id == org_id)
    if status:
        q = q.filter(DisposalDispatch.status == status)

    items = q.order_by(DisposalDispatch.id.desc()).limit(100).all()
    return templates.TemplateResponse(request=request, name="integrations_dispatch.html", context=_ctx(session, labels, {
        "page_title": "Disposal Dispatches",
        "active_nav": "integrations",
        "items": items,
        "filter_status": status
    }))

@router.get("/integrations/logs", response_class=HTMLResponse)
def view_integration_logs(request: Request, direction: str = "", status_code: Optional[int] = None, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    q = db.query(IntegrationLog).filter(IntegrationLog.organization_id == org_id)
    if direction:
        q = q.filter(IntegrationLog.direction == direction)
    if status_code:
        q = q.filter(IntegrationLog.status_code == status_code)

    logs = q.order_by(IntegrationLog.id.desc()).limit(100).all()
    return templates.TemplateResponse(request=request, name="integrations_logs.html", context=_ctx(session, labels, {
        "page_title": "Integration API Logs",
        "active_nav": "integrations",
        "logs": logs,
        "filter_direction": direction,
        "filter_status": status_code
    }))

@router.get("/integrations/tier", response_class=HTMLResponse)
def view_tier_upgrade(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    org = db.query(Organization).filter(Organization.id == org_id).first()

    return templates.TemplateResponse(request=request, name="integrations_tier.html", context=_ctx(session, labels, {
        "page_title": "Product Tier & Licensing",
        "active_nav": "integrations",
        "org": org
    }))
