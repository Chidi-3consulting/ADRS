import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PendingRecalculation, DataRecord, DataCategory, User
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

@router.get("/recalculations", response_class=HTMLResponse)
def view_recalculations(request: Request, status: str = "pending", db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)
    if session.get("role") not in ("admin", "dpo"):
        raise HTTPException(status_code=403, detail="Access denied")

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    q = db.query(PendingRecalculation).filter(PendingRecalculation.organization_id == org_id)
    if status:
        q = q.filter(PendingRecalculation.status == status)

    items = q.order_by(PendingRecalculation.id.desc()).all()

    return templates.TemplateResponse(request=request, name="recalculations.html", context=_ctx(session, labels, {
        "page_title": "Pending Recalculations",
        "active_nav": "recalculations",
        "items": items,
        "filter_status": status
    }))

@router.post("/recalculations/{id}/action")
def handle_recalculation_action(
    id: int,
    request: Request,
    decision: str = Form(...),  # "recalculate" or "keep_original"
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    recalc = db.query(PendingRecalculation).filter(
        PendingRecalculation.id == id,
        PendingRecalculation.organization_id == org_id,
        PendingRecalculation.status == "pending"
    ).first()

    if not recalc:
        raise HTTPException(status_code=404, detail="Recalculation entry not found or already processed.")

    record = db.query(DataRecord).filter(DataRecord.id == recalc.record_id).first()

    if decision == "recalculate" and record:
        record.retention_end_date = recalc.new_retention_end_date
        recalc.status = "recalculate"
    else:
        recalc.status = "keep_original"

    recalc.reviewed_by = session["user_id"]
    recalc.reviewed_at = datetime.now(timezone.utc)
    db.commit()

    log_audit(db, org_id, "recalculation_reviewed", "data_record", recalc.record_id, session["user_id"], {
        "decision": decision,
        "old_date": str(recalc.old_retention_end_date),
        "new_date": str(recalc.new_retention_end_date)
    }, request.client.host if request.client else None)

    return RedirectResponse(url="/recalculations", status_code=303)
