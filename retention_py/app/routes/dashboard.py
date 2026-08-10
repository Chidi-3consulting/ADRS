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
from app.engine import (
    compliance_metrics, compliance_score, upcoming_deadlines,
    disposals_by_month, org_onboarding_checklist,
    sync_onboarding_notifications,
)

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
    user_id = session["user_id"]
    user_role = session["role"]

    # ── Analytics (replaces inline queries) ──
    metrics = compliance_metrics(db, org_id)
    score = compliance_score(db, org_id)
    deadlines = upcoming_deadlines(db, org_id, limit=10)
    disposal_chart = disposals_by_month(db, org_id, months=6)

    # ── Onboarding (admin only, sync idempotent) ──
    checklist = None
    if user_role == "admin":
        checklist = org_onboarding_checklist(db, org_id)
        all_done = all(step["completed"] for step in checklist)
        if not all_done:
            sync_onboarding_notifications(db, org_id, user_id)
        else:
            checklist = None  # hide when fully completed

    # Fetch SMTP status warnings
    smtp_host = db.query(SystemSetting).filter(SystemSetting.setting_key == "smtp_host").first()
    smtp_warning = not smtp_host or smtp_host.setting_value == "mail.yourdomain.com" or smtp_host.setting_value == ""

    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "page_title": "Compliance Dashboard",
        "active_nav": "dashboard",
        "user_name": session["user_name"],
        "user_role": user_role,
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "metrics": metrics,
        "health_score": score,
        "upcoming_deadlines": deadlines,
        "disposal_chart": disposal_chart,
        "onboarding": checklist,
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
