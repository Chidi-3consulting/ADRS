import os
import csv
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import DataCategory, CategoryRetentionRule, DataRecord, User
from app.auth import get_session
from app.helpers import get_country_regulation_labels, get_framework_badge, get_country_regulations, log_audit

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)
templates.env.globals['get_framework_badge'] = get_framework_badge
templates.env.globals['unread_notifications_count'] = 0

router = APIRouter()

@router.get("/categories", response_class=HTMLResponse)
def list_categories(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    categories = db.query(DataCategory).filter(
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None
    ).all()

    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="categories.html", context={
        "page_title": "Data Categories",
        "active_nav": "categories",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "categories": categories
    })

@router.get("/categories/view/{id}", response_class=HTMLResponse)
def view_category_details(id: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    category = db.query(DataCategory).filter(
        DataCategory.id == id,
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    active_count = db.query(func.count(DataRecord.id)).filter(
        DataRecord.organization_id == org_id,
        DataRecord.category_id == id,
        DataRecord.deleted_at == None,
        DataRecord.status != "disposed"
    ).scalar() or 0

    due_review_count = db.query(func.count(DataRecord.id)).filter(
        DataRecord.organization_id == org_id,
        DataRecord.category_id == id,
        DataRecord.status == "due_review"
    ).scalar() or 0

    on_hold_count = db.query(func.count(DataRecord.id)).filter(
        DataRecord.organization_id == org_id,
        DataRecord.category_id == id,
        DataRecord.legal_hold == True
    ).scalar() or 0

    owner_name = None
    if category.owner_id:
        owner = db.query(User).filter(User.id == category.owner_id).first()
        if owner:
            owner_name = owner.name

    rules = db.query(CategoryRetentionRule).filter(
        CategoryRetentionRule.category_id == id,
        CategoryRetentionRule.organization_id == org_id,
        CategoryRetentionRule.is_active == True
    ).all()

    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="categories_view.html", context={
        "page_title": f"Category: {category.name}",
        "active_nav": "categories",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "category": category,
        "active_count": active_count,
        "due_review_count": due_review_count,
        "on_hold_count": on_hold_count,
        "owner_name": owner_name,
        "rules": rules
    })

@router.get("/categories/create", response_class=HTMLResponse)
def view_create_category(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="categories_create.html", context={
        "page_title": "Create Data Category",
        "active_nav": "categories",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"]
    })

@router.post("/categories/create")
def handle_create_category(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    retention_reason: str = Form("Compliance retention"),
    legal_basis: str = Form("legitimate_interest"),
    disposal_trigger: str = Form("date_based"),
    retention_period_days: int = Form(365),
    retention_period_label: str = Form("1 year"),
    disposal_method: str = Form("delete"),
    review_frequency: str = Form("quarterly"),
    processing_role: str = Form("controller"),
    processor_name: str = Form(""),
    processor_contact: str = Form(""),
    dpa_reference: str = Form(""),
    processor_retention_status: str = Form("compliant"),
    data_classification: str = Form("standard"),
    approval_type: str = Form("single_approval"),
    requires_dual_approval: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    country = session.get("country", "OTHER")

    frameworks = get_country_regulations(country)
    framework_string = ",".join(frameworks)

    # Enforce classification rules:
    if data_classification in ("special_category", "children"):
        approval_type = "dual_approval"
    elif data_classification in ("confidential", "financial_aml") and approval_type == "auto_disposal":
        approval_type = "single_approval"

    dual_bool = (approval_type == "dual_approval") or bool(requires_dual_approval and str(requires_dual_approval).lower() in ("on", "true", "1"))
    if dual_bool:
        approval_type = "dual_approval"

    new_cat = DataCategory(
        organization_id=org_id,
        name=name,
        description=description,
        retention_reason=retention_reason,
        compliance_framework=framework_string,
        legal_basis=legal_basis,
        retention_period_days=retention_period_days,
        retention_period_label=retention_period_label,
        disposal_method=disposal_method,
        disposal_trigger=disposal_trigger,
        data_classification=data_classification,
        approval_type=approval_type,
        requires_dual_approval=dual_bool,
        review_frequency=review_frequency,
        processing_role=processing_role,
        processor_name=processor_name.strip() or None,
        processor_contact=processor_contact.strip() or None,
        dpa_reference=dpa_reference.strip() or None,
        processor_retention_status=processor_retention_status or "compliant",
        source="custom"
    )

    db.add(new_cat)
    db.commit()

    log_audit(db, org_id, "category_created", "data_category", new_cat.id, session["user_id"], {"name": name, "role": processing_role, "processor": processor_name}, request.client.host if request.client else None)
    return RedirectResponse(url="/categories", status_code=303)

@router.get("/categories/edit/{id}", response_class=HTMLResponse)
def view_edit_category(id: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    category = db.query(DataCategory).filter(
        DataCategory.id == id,
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="categories_edit.html", context={
        "page_title": "Edit Data Category",
        "active_nav": "categories",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "category": category
    })

@router.post("/categories/edit/{id}")
def handle_edit_category(
    id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    retention_reason: str = Form(...),
    legal_basis: str = Form(...),
    disposal_trigger: str = Form(...),
    retention_period_days: int = Form(0),
    retention_period_label: str = Form(""),
    disposal_method: str = Form(...),
    review_frequency: str = Form(...),
    processing_role: str = Form("controller"),
    processor_name: str = Form(""),
    processor_contact: str = Form(""),
    dpa_reference: str = Form(""),
    processor_retention_status: str = Form("compliant"),
    data_classification: str = Form("standard"),
    approval_type: str = Form("single_approval"),
    requires_dual_approval: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    category = db.query(DataCategory).filter(
        DataCategory.id == id,
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Enforce classification rules:
    if data_classification in ("special_category", "children"):
        approval_type = "dual_approval"
    elif data_classification in ("confidential", "financial_aml") and approval_type == "auto_disposal":
        approval_type = "single_approval"

    dual_bool = (approval_type == "dual_approval") or bool(requires_dual_approval and str(requires_dual_approval).lower() in ("on", "true", "1"))
    if dual_bool:
        approval_type = "dual_approval"

    category.name = name
    category.description = description
    category.retention_reason = retention_reason
    category.legal_basis = legal_basis
    category.disposal_trigger = disposal_trigger
    category.retention_period_days = retention_period_days
    category.retention_period_label = retention_period_label
    category.disposal_method = disposal_method
    category.review_frequency = review_frequency
    category.processing_role = processing_role
    category.processor_name = processor_name.strip() or None
    category.processor_contact = processor_contact.strip() or None
    category.dpa_reference = dpa_reference.strip() or None
    category.processor_retention_status = processor_retention_status or "compliant"
    category.data_classification = data_classification
    category.approval_type = approval_type
    category.requires_dual_approval = dual_bool

    db.commit()

    log_audit(db, org_id, "category_updated", "data_category", id, session["user_id"], {"name": name, "role": processing_role, "processor": processor_name}, request.client.host if request.client else None)
    return RedirectResponse(url=f"/categories/view/{id}", status_code=303)

@router.post("/categories/delete/{id}")
def handle_delete_category(id: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    category = db.query(DataCategory).filter(
        DataCategory.id == id,
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check for active non-disposed records
    active_records = db.query(DataRecord).filter(
        DataRecord.category_id == id,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None,
        DataRecord.status != "disposed"
    ).count()

    if active_records > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete category: {active_records} active records are assigned to it.")

    category.deleted_at = datetime.now(timezone.utc)
    db.commit()

    log_audit(db, org_id, "category_deleted", "data_category", id, session["user_id"], {"name": category.name}, request.client.host if request.client else None)
    return RedirectResponse(url="/categories", status_code=303)

@router.get("/categories/export")
def export_categories_csv(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    categories = db.query(DataCategory).filter(
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Compliance Framework", "Legal Basis", "Retention Days", "Label", "Disposal Method", "Disposal Trigger", "Role", "Processor", "DPA Reference", "Dual Approval Required"])

    for c in categories:
        writer.writerow([
            c.id, c.name, c.compliance_framework, c.legal_basis,
            c.retention_period_days, c.retention_period_label,
            c.disposal_method, c.disposal_trigger,
            c.processing_role or "controller",
            c.processor_name or "",
            c.dpa_reference or "",
            "Yes" if c.requires_dual_approval else "No"
        ])

    log_audit(db, org_id, "categories_exported", "data_category", None, session["user_id"], {"count": len(categories)}, request.client.host if request.client else None)

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=data_categories_export.csv"}
    )
