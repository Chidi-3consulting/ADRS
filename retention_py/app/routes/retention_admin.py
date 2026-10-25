"""Admin tools: run retention, simulate it, manage consent and simulate consent removal.

Simulations are read-only. Only the explicit "run" and "withdraw" actions change data,
and both write to the audit trail.
"""

import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_session
from app.database import get_db
from app.engine import (
    is_disposal_frozen,
    log_consent_withdrawal,
    records_past_retention,
    run_retention_checks,
    simulate_consent_removal,
)
from app.helpers import get_country_regulation_labels, get_framework_badge, log_audit
from app.models import DataCategory, DataRecord

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)
templates.env.globals["get_framework_badge"] = get_framework_badge
templates.env.globals["unread_notifications_count"] = 0

router = APIRouter()

ACTION_LABELS = {
    "flag_for_review": "Flagged for review",
    "dispose_consent_withdrawn": "Disposed (consent withdrawn)",
    "auto_dispose": "Disposed automatically",
    "needs_approval": "Waits for approval",
    "blocked_by_freeze": "Blocked by emergency freeze",
}
OUTCOME_LABELS = {
    "would_dispose": "Would be disposed",
    "blocked_by_legal_hold": "Blocked by legal hold",
    "no_automatic_disposal": "No automatic disposal for this category",
    "paused_by_freeze": "Paused by emergency freeze",
}


def _admin(request: Request) -> dict:
    session = get_session(request)
    if not session or "user_id" not in session:
        raise HTTPException(status_code=303, detail="Redirect to login")
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrators only")
    return session


def _ctx(session, extra):
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    base = {
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "is_platform_admin": session.get("is_platform_admin", False),
        "action_labels": ACTION_LABELS,
        "outcome_labels": OUTCOME_LABELS,
    }
    base.update(extra)
    return base


def _ip(request: Request):
    return request.client.host if request.client else None


def _retention_page(request, db, session, result=None, mode=None):
    org_id = session["org_id"]
    return templates.TemplateResponse(
        request=request,
        name="admin_retention.html",
        context=_ctx(
            session,
            {
                "page_title": "Retention run",
                "active_nav": "admin_retention",
                "queue_count": records_past_retention(db, org_id).count(),
                "held_count": records_past_retention(db, org_id, include_held=True).count()
                - records_past_retention(db, org_id).count(),
                "frozen": is_disposal_frozen(db, org_id),
                "result": result,
                "mode": mode,
            },
        ),
    )


@router.get("/admin/retention", response_class=HTMLResponse)
def retention_page(request: Request, db: Session = Depends(get_db)):
    session = _admin(request)
    return _retention_page(request, db, session)


@router.post("/admin/retention/simulate", response_class=HTMLResponse)
def retention_simulate(request: Request, db: Session = Depends(get_db)):
    session = _admin(request)
    result = run_retention_checks(db, session["org_id"], dry_run=True)
    log_audit(
        db,
        session["org_id"],
        "retention_simulated",
        "organization",
        session["org_id"],
        session["user_id"],
        {"would_act_on": len(result["plan"])},
        _ip(request),
    )
    return _retention_page(request, db, session, result, "simulation")


@router.post("/admin/retention/run", response_class=HTMLResponse)
def retention_run(request: Request, confirm: str = Form(""), db: Session = Depends(get_db)):
    session = _admin(request)
    if confirm.strip().upper() != "RUN":
        return RedirectResponse(url="/admin/retention?error=confirm", status_code=303)
    result = run_retention_checks(db, session["org_id"])
    log_audit(
        db,
        session["org_id"],
        "retention_run_manual",
        "organization",
        session["org_id"],
        session["user_id"],
        {k: v for k, v in result.items() if k not in ("plan",)},
        _ip(request),
    )
    return _retention_page(request, db, session, result, "run")


@router.get("/admin/consent", response_class=HTMLResponse)
def consent_page(request: Request, db: Session = Depends(get_db)):
    session = _admin(request)
    return _consent_page(request, db, session)


def _consent_page(request, db, session, simulation=None, notice=None):
    org_id = session["org_id"]
    records = (
        db.query(DataRecord)
        .join(DataCategory, DataRecord.category_id == DataCategory.id)
        .filter(
            DataRecord.organization_id == org_id,
            DataRecord.deleted_at == None,  # noqa: E711
            DataRecord.status != "disposed",
            DataCategory.legal_basis == "consent",
        )
        .order_by(DataRecord.id.desc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="admin_consent.html",
        context=_ctx(
            session,
            {
                "page_title": "Consent management",
                "active_nav": "admin_consent",
                "records": records,
                "simulation": simulation,
                "notice": notice,
            },
        ),
    )


@router.post("/admin/consent/simulate", response_class=HTMLResponse)
def consent_simulate(request: Request, record_id: int = Form(0), db: Session = Depends(get_db)):
    session = _admin(request)
    sim = simulate_consent_removal(db, session["org_id"], [record_id] if record_id else None)
    log_audit(
        db,
        session["org_id"],
        "consent_removal_simulated",
        "organization",
        session["org_id"],
        session["user_id"],
        {"records": len(sim["items"])},
        _ip(request),
    )
    return _consent_page(request, db, session, simulation=sim)


@router.post("/admin/consent/withdraw/{record_id}")
def consent_withdraw(record_id: int, request: Request, db: Session = Depends(get_db)):
    session = _admin(request)
    ok = log_consent_withdrawal(db, session["org_id"], record_id, session["user_id"], _ip(request))
    if not ok:
        raise HTTPException(status_code=404, detail="Record not found")
    return RedirectResponse(url="/admin/consent?withdrawn=1", status_code=303)
