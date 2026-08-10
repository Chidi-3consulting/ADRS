"""
ADRS ROPA (Record of Processing Activities) Routes
Ported from legacy — provides full CRUD for ROPA entries with
controller/processor support and processor sub-entries.
"""
import csv
import io
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from app.database import get_db
from app.models import RopaEntry, RopaProcessor, DataCategory
from app.auth import get_session
from app.helpers import log_audit, get_framework_badge, get_country_regulation_labels

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)
templates.env.globals['get_framework_badge'] = get_framework_badge
templates.env.globals['unread_notifications_count'] = 0

router = APIRouter()


# ── List all ROPA entries ──
@router.get("/ropa", response_class=HTMLResponse)
def ropa_list(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    entries = db.query(RopaEntry).filter(
        RopaEntry.organization_id == org_id
    ).order_by(RopaEntry.created_at.desc()).all()

    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="ropa.html", context={
        "page_title": "Record of Processing Activities",
        "active_nav": "ropa",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "entries": entries,
    })


# ── Create ROPA entry form ──
@router.get("/ropa/create", response_class=HTMLResponse)
def ropa_create_form(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    categories = db.query(DataCategory).filter(
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None,
    ).order_by(DataCategory.name).all()
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="ropa_form.html", context={
        "page_title": "New ROPA Entry",
        "active_nav": "ropa",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "categories": categories,
        "entry": None,
        "mode": "create",
    })


# ── Create ROPA entry (POST) ──
@router.post("/ropa/create")
def ropa_create(
    request: Request,
    db: Session = Depends(get_db),
    activity_name: str = Form(...),
    role_type: str = Form("controller"),
    category_id: int = Form(None),
    controller_name: str = Form(""),
    controller_contact: str = Form(""),
    processor_name: str = Form(""),
    processor_contact: str = Form(""),
    dpo_contact: str = Form(""),
    purpose: str = Form(""),
    lawful_basis: str = Form(""),
    data_subjects: str = Form(""),
    data_categories: str = Form(""),
    recipients: str = Form(""),
    third_country_transfers: str = Form(""),
    retention_summary: str = Form(""),
    security_measures: str = Form(""),
):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    entry = RopaEntry(
        organization_id=org_id,
        activity_name=activity_name.strip(),
        role_type=role_type,
        category_id=category_id if category_id else None,
        controller_name=controller_name.strip() or None,
        controller_contact=controller_contact.strip() or None,
        processor_name=processor_name.strip() or None,
        processor_contact=processor_contact.strip() or None,
        dpo_contact=dpo_contact.strip() or None,
        purpose=purpose.strip() or None,
        lawful_basis=lawful_basis.strip() or None,
        data_subjects=data_subjects.strip() or None,
        data_categories=data_categories.strip() or None,
        recipients=recipients.strip() or None,
        third_country_transfers=third_country_transfers.strip() or None,
        retention_summary=retention_summary.strip() or None,
        security_measures=security_measures.strip() or None,
        created_by=session["user_id"],
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    log_audit(db, org_id, "ropa_created", "ropa_entry", entry.id,
              session["user_id"], {"activity": activity_name}, request.client.host)

    return RedirectResponse(url=f"/ropa/{entry.id}", status_code=303)


# ── View ROPA entry ──
@router.get("/ropa/{entry_id}", response_class=HTMLResponse)
def ropa_view(entry_id: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    entry = db.query(RopaEntry).filter(
        RopaEntry.id == entry_id,
        RopaEntry.organization_id == org_id,
    ).first()
    if not entry:
        return RedirectResponse(url="/ropa", status_code=303)

    processors = db.query(RopaProcessor).filter(
        RopaProcessor.ropa_entry_id == entry.id
    ).all()
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="ropa_view.html", context={
        "page_title": f"ROPA — {entry.activity_name}",
        "active_nav": "ropa",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "entry": entry,
        "processors": processors,
    })


# ── Edit ROPA entry form ──
@router.get("/ropa/{entry_id}/edit", response_class=HTMLResponse)
def ropa_edit_form(entry_id: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    entry = db.query(RopaEntry).filter(
        RopaEntry.id == entry_id,
        RopaEntry.organization_id == org_id,
    ).first()
    if not entry:
        return RedirectResponse(url="/ropa", status_code=303)

    categories = db.query(DataCategory).filter(
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None,
    ).order_by(DataCategory.name).all()
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="ropa_form.html", context={
        "page_title": f"Edit ROPA — {entry.activity_name}",
        "active_nav": "ropa",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "categories": categories,
        "entry": entry,
        "mode": "edit",
    })


# ── Edit ROPA entry (POST) ──
@router.post("/ropa/{entry_id}/edit")
def ropa_edit(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    activity_name: str = Form(...),
    role_type: str = Form("controller"),
    category_id: int = Form(None),
    controller_name: str = Form(""),
    controller_contact: str = Form(""),
    processor_name: str = Form(""),
    processor_contact: str = Form(""),
    dpo_contact: str = Form(""),
    purpose: str = Form(""),
    lawful_basis: str = Form(""),
    data_subjects: str = Form(""),
    data_categories: str = Form(""),
    recipients: str = Form(""),
    third_country_transfers: str = Form(""),
    retention_summary: str = Form(""),
    security_measures: str = Form(""),
):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    entry = db.query(RopaEntry).filter(
        RopaEntry.id == entry_id,
        RopaEntry.organization_id == org_id,
    ).first()
    if not entry:
        return RedirectResponse(url="/ropa", status_code=303)

    entry.activity_name = activity_name.strip()
    entry.role_type = role_type
    entry.category_id = category_id if category_id else None
    entry.controller_name = controller_name.strip() or None
    entry.controller_contact = controller_contact.strip() or None
    entry.processor_name = processor_name.strip() or None
    entry.processor_contact = processor_contact.strip() or None
    entry.dpo_contact = dpo_contact.strip() or None
    entry.purpose = purpose.strip() or None
    entry.lawful_basis = lawful_basis.strip() or None
    entry.data_subjects = data_subjects.strip() or None
    entry.data_categories = data_categories.strip() or None
    entry.recipients = recipients.strip() or None
    entry.third_country_transfers = third_country_transfers.strip() or None
    entry.retention_summary = retention_summary.strip() or None
    entry.security_measures = security_measures.strip() or None
    db.commit()

    log_audit(db, org_id, "ropa_updated", "ropa_entry", entry.id,
              session["user_id"], {"activity": activity_name}, request.client.host)

    return RedirectResponse(url=f"/ropa/{entry.id}", status_code=303)


# ── Add processor sub-entry ──
@router.post("/ropa/{entry_id}/processors/add")
def ropa_add_processor(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    processor_name: str = Form(...),
    processor_contact: str = Form(""),
    processing_purpose: str = Form(""),
    data_categories_handled: str = Form(""),
    security_measures: str = Form(""),
    sub_processors: str = Form(""),
    contract_reference: str = Form(""),
):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    entry = db.query(RopaEntry).filter(
        RopaEntry.id == entry_id,
        RopaEntry.organization_id == org_id,
    ).first()
    if not entry:
        return RedirectResponse(url="/ropa", status_code=303)

    proc = RopaProcessor(
        ropa_entry_id=entry.id,
        organization_id=org_id,
        processor_name=processor_name.strip(),
        processor_contact=processor_contact.strip() or None,
        processing_purpose=processing_purpose.strip() or None,
        data_categories_handled=data_categories_handled.strip() or None,
        security_measures=security_measures.strip() or None,
        sub_processors=sub_processors.strip() or None,
        contract_reference=contract_reference.strip() or None,
    )
    db.add(proc)
    db.commit()

    log_audit(db, org_id, "ropa_processor_added", "ropa_processor", proc.id,
              session["user_id"], {"ropa_entry_id": entry.id, "processor": processor_name},
              request.client.host)

    return RedirectResponse(url=f"/ropa/{entry.id}", status_code=303)


# ── Delete processor sub-entry ──
@router.post("/ropa/{entry_id}/processors/{proc_id}/delete")
def ropa_delete_processor(entry_id: int, proc_id: int, request: Request,
                          db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    proc = db.query(RopaProcessor).filter(
        RopaProcessor.id == proc_id,
        RopaProcessor.ropa_entry_id == entry_id,
        RopaProcessor.organization_id == org_id,
    ).first()
    if proc:
        db.delete(proc)
        db.commit()
        log_audit(db, org_id, "ropa_processor_deleted", "ropa_processor", proc_id,
                  session["user_id"], {"ropa_entry_id": entry_id},
                  request.client.host)

    return RedirectResponse(url=f"/ropa/{entry_id}", status_code=303)


# ── Export ROPA as CSV ──
@router.get("/ropa/export/csv")
def ropa_export_csv(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    entries = db.query(RopaEntry).filter(
        RopaEntry.organization_id == org_id
    ).order_by(RopaEntry.id.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Activity Name", "Role Type", "Controller", "Controller Contact",
        "Processor", "Processor Contact", "DPO Contact", "Purpose",
        "Lawful Basis", "Data Subjects", "Data Categories", "Recipients",
        "Third Country Transfers", "Retention Summary", "Security Measures",
        "Created At",
    ])
    for e in entries:
        writer.writerow([
            e.id, e.activity_name, e.role_type,
            e.controller_name or "", e.controller_contact or "",
            e.processor_name or "", e.processor_contact or "",
            e.dpo_contact or "", e.purpose or "",
            e.lawful_basis or "", e.data_subjects or "",
            e.data_categories or "", e.recipients or "",
            e.third_country_transfers or "", e.retention_summary or "",
            e.security_measures or "",
            e.created_at.strftime("%Y-%m-%d") if e.created_at else "",
        ])

    output.seek(0)
    filename = f"ropa_export_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
