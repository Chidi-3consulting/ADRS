import os
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Organization, User, DataRecord, PaymentTransaction
from app.auth import get_session
from app.helpers import log_audit, get_country_regulation_labels

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)

router = APIRouter()

def require_platform_admin(request: Request):
    session = get_session(request)
    if not session or "user_id" not in session:
        raise HTTPException(status_code=303, detail="Redirect to login")
    if not session.get("is_platform_admin"):
        raise HTTPException(status_code=403, detail="Platform administrator access required.")
    return session

@router.get("/platform", response_class=HTMLResponse)
def view_platform_dashboard(request: Request, db: Session = Depends(get_db), session: dict = Depends(require_platform_admin)):
    # Calculate metrics
    orgs_count = db.query(Organization).count()
    active_orgs = db.query(Organization).filter(Organization.status == "active").count()
    trial_orgs = db.query(Organization).filter(Organization.subscription_status == "trial").count()
    paid_orgs = db.query(Organization).filter(Organization.subscription_status == "active").count()
    users_count = db.query(User).filter(User.deleted_at == None).count()
    records_count = db.query(DataRecord).filter(DataRecord.deleted_at == None).count()
    revenue_tx = db.query(PaymentTransaction).filter(PaymentTransaction.status == "success").count()

    metrics = {
        "organizations": orgs_count,
        "active_orgs": active_orgs,
        "trial_orgs": trial_orgs,
        "paid_orgs": paid_orgs,
        "users": users_count,
        "records": records_count,
        "revenue_tx": revenue_tx
    }

    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    # We build the context compatible with layout.html
    context = {
        "page_title": "Platform Administration",
        "active_nav": "platform",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "metrics": metrics
    }

    return templates.TemplateResponse(request=request, name="platform_dashboard.html", context=context)

@router.get("/platform/organizations", response_class=HTMLResponse)
def view_platform_organizations(request: Request, db: Session = Depends(get_db), session: dict = Depends(require_platform_admin)):
    orgs = db.query(Organization).order_by(Organization.created_at.desc()).all()
    
    # Enrich with user and record count
    enriched_orgs = []
    for o in orgs:
        ucount = db.query(User).filter(User.organization_id == o.id, User.deleted_at == None).count()
        rcount = db.query(DataRecord).filter(DataRecord.organization_id == o.id, DataRecord.deleted_at == None).count()
        enriched_orgs.append({
            "id": o.id,
            "name": o.name,
            "slug": o.slug,
            "primary_domain": o.primary_domain,
            "tier": o.tier,
            "status": o.status,
            "subscription_status": o.subscription_status,
            "user_count": ucount,
            "record_count": rcount,
            "created_at": o.created_at
        })

    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    context = {
        "page_title": "Manage Organisations",
        "active_nav": "platform",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "orgs": enriched_orgs
    }

    return templates.TemplateResponse(request=request, name="platform_organizations.html", context=context)

@router.post("/platform/organizations")
def handle_set_org_status(
    request: Request,
    org_id: int = Form(...),
    status: str = Form(...),
    db: Session = Depends(get_db),
    session: dict = Depends(require_platform_admin)
):
    if status not in ["active", "trial", "suspended"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")

    org.status = status
    db.commit()

    log_audit(db, session["org_id"], "platform_org_status", "organization", org_id, session["user_id"], {
        "status": status
    }, request.client.host if request.client else None)

    return RedirectResponse(url="/platform/organizations", status_code=303)
