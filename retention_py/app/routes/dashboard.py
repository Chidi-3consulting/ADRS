from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from datetime import date

from app.database import get_db
from app.models import DataRecord, SystemSetting
from app.auth import get_session
from app.helpers import get_country_regulation_labels, get_framework_badge

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)
templates.env.globals['get_framework_badge'] = get_framework_badge
templates.env.globals['unread_notifications_count'] = 0

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse)
def view_dashboard(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    today = date.today()

    # Query KPI counts
    active_count = db.query(DataRecord).filter(DataRecord.organization_id == org_id, DataRecord.status == "active").count()
    due_review_count = db.query(DataRecord).filter(DataRecord.organization_id == org_id, DataRecord.status == "due_review").count()
    overdue_count = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "due_review",
        DataRecord.retention_end_date != None,
        DataRecord.retention_end_date < today
    ).count()
    hold_count = db.query(DataRecord).filter(DataRecord.organization_id == org_id, DataRecord.status == "legal_hold").count()
    pending_approval_count = db.query(DataRecord).filter(DataRecord.organization_id == org_id, DataRecord.status == "disposal_requested").count()
    disposed_count = db.query(DataRecord).filter(DataRecord.organization_id == org_id, DataRecord.status == "disposed").count()

    # Calculate compliance score
    total_active_lifecycle = active_count + due_review_count
    health_score = 100
    if total_active_lifecycle > 0 and overdue_count > 0:
        health_score = max(0, int(((total_active_lifecycle - overdue_count) / total_active_lifecycle) * 100))

    metrics = {
        "active": active_count,
        "due_review": due_review_count,
        "overdue": overdue_count,
        "legal_hold": hold_count,
        "pending_approval": pending_approval_count,
        "disposed": disposed_count,
        "health_score": health_score
    }

    # Fetch SMTP status warnings
    smtp_host = db.query(SystemSetting).filter(SystemSetting.setting_key == "smtp_host").first()
    smtp_warning = not smtp_host or smtp_host.setting_value == "mail.yourdomain.com" or smtp_host.setting_value == ""

    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "page_title": "Compliance Dashboard",
        "active_nav": "dashboard",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "metrics": metrics,
        "smtp_warning": smtp_warning
    })

@router.get("/help", response_class=HTMLResponse)
def view_help(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    from app.helpers import ADRS_SUPPORTED_COUNTRIES
    country_code = session.get("country", "OTHER")
    country_name = ADRS_SUPPORTED_COUNTRIES.get(country_code, "General")
    labels = get_country_regulation_labels(country_code)

    return templates.TemplateResponse(request=request, name="help.html", context={
        "page_title": "Solution Manual & Help",
        "active_nav": "help",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "country_name": country_name,
        "law_name": labels["law"],
        "authority_name": labels["authority"]
    })
