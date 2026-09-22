import os
import uuid
import csv
import io
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DataRecord, DataCategory, CategoryRetentionRule, AuditLog, Attachment, User
from app.auth import get_session, verify_stepup_authentication
from app.helpers import get_country_regulation_labels, get_framework_badge, log_audit
from app.engine import calculate_retention_end_date, execute_disposal
from app.config import UPLOAD_PATH

templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)
templates.env.globals['get_framework_badge'] = get_framework_badge
templates.env.globals['unread_notifications_count'] = 0

router = APIRouter()

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'txt', 'csv'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Gap 5: Magic-byte signatures for MIME type validation
# Maps file extension to expected magic-byte prefixes
_MIME_SIGNATURES = {
    'pdf':  [b'%PDF'],
    'png':  [b'\x89PNG'],
    'jpg':  [b'\xff\xd8\xff'],
    'jpeg': [b'\xff\xd8\xff'],
    'doc':  [b'\xd0\xcf\x11\xe0'],  # OLE2 compound
    'docx': [b'PK\x03\x04'],        # ZIP-based OOXML
    'xls':  [b'\xd0\xcf\x11\xe0'],  # OLE2 compound
    'xlsx': [b'PK\x03\x04'],        # ZIP-based OOXML
    # txt and csv have no reliable magic bytes — validated by extension only
}


def _validate_file_magic(content: bytes, extension: str) -> bool:
    """Gap 5: Verify file content matches expected magic-byte signature."""
    signatures = _MIME_SIGNATURES.get(extension)
    if not signatures:
        return True  # txt/csv have no reliable magic bytes
    return any(content[:len(sig)] == sig for sig in signatures)

def _get_org_setting(db: Session, org_id: int, key: str, default: str = "") -> str:
    from app.models import OrganizationSetting, SystemSetting
    row = db.query(OrganizationSetting).filter(
        OrganizationSetting.organization_id == org_id,
        OrganizationSetting.setting_key == key
    ).first()
    if row:
        return row.setting_value
    sys_row = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    return sys_row.setting_value if sys_row else default

@router.get("/records", response_class=HTMLResponse)
def list_records(
    request: Request,
    page: int = 1,
    q: str = "",
    status: str = "",
    category_id: int = 0,
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]
    is_owner = (session.get("role") == "data_owner")
    today = date.today()

    # Base filters
    kpi_filters = [DataRecord.organization_id == org_id, DataRecord.deleted_at == None]
    if is_owner:
        kpi_filters.append(DataCategory.owner_id == user_id)

    # Compute unfiltered KPIs
    start_of_month = datetime(today.year, today.month, 1)
    if today.month == 12:
        end_of_month = datetime(today.year + 1, 1, 1)
    else:
        end_of_month = datetime(today.year, today.month + 1, 1)

    # P4 fix: Use case() expressions instead of func.sum(bool_expr) for cross-DB compatibility
    from sqlalchemy import case
    kpi_query = db.query(
        func.count(case((DataRecord.status != 'disposed', 1))).label('active'),
        func.count(case((DataRecord.status == 'due_review', 1))).label('due_review'),
        func.count(case((
            and_(DataRecord.retention_end_date < today, DataRecord.status != 'disposed'), 1
        ))).label('overdue'),
        func.count(case((
            or_(DataRecord.legal_hold == True, DataRecord.status == 'legal_hold'), 1
        ))).label('on_hold'),
        func.count(case((DataRecord.status == 'disposal_requested', 1))).label('awaiting_approval'),
        func.count(case((
            and_(
                DataRecord.status == 'disposed',
                DataRecord.disposed_at >= start_of_month,
                DataRecord.disposed_at < end_of_month
            ), 1
        ))).label('disposed_month')
    ).join(DataCategory, DataRecord.category_id == DataCategory.id).filter(*kpi_filters).first()

    # List categories options
    cat_query = db.query(DataCategory).filter(
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None
    )
    if is_owner:
        cat_query = cat_query.filter(DataCategory.owner_id == user_id)
    categories = cat_query.order_by(DataCategory.name).all()

    # Dynamic search/filter query building
    where_clauses = [DataRecord.organization_id == org_id]
    if is_owner:
        where_clauses.append(DataCategory.owner_id == user_id)

    # Disposed records filter
    if status != "disposed":
        where_clauses.append(DataRecord.deleted_at == None)

    if q.strip():
        term = f"%{q.strip()}%"
        where_clauses.append(or_(
            DataRecord.record_reference.like(term),
            DataRecord.data_subject_type.like(term)
        ))

    if category_id > 0:
        where_clauses.append(DataRecord.category_id == category_id)

    if status == "overdue":
        where_clauses.append(and_(
            DataRecord.retention_end_date < today,
            DataRecord.status != "disposed"
        ))
    elif status in ['active', 'due_review', 'disposal_requested', 'legal_hold', 'disposed']:
        where_clauses.append(DataRecord.status == status)

    records_query = db.query(DataRecord).join(
        DataCategory, DataRecord.category_id == DataCategory.id
    ).filter(*where_clauses)

    total_count = records_query.count()
    per_page = 25
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page_num = min(max(1, page), total_pages)
    offset = (page_num - 1) * per_page

    records = records_query.order_by(DataRecord.created_at.desc()).offset(offset).limit(per_page).all()
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    today_str = today.strftime("%Y-%m-%d")

    return templates.TemplateResponse(request=request, name="records.html", context={
        "page_title": "Retention Register",
        "active_nav": "records",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "kpi": kpi_query,
        "categories": categories,
        "records": records,
        "today_str": today_str,
        "today_date": today,
        "filter_q": q,
        "filter_status": status,
        "filter_category_id": category_id,
        "total_count": total_count,
        "total_pages": total_pages,
        "page_num": page_num
    })

@router.post("/records/create")
def handle_create_record(
    request: Request,
    record_reference: str = Form(...),
    category_id: int = Form(...),
    collection_date: str = Form(...),
    data_subject_type: Optional[str] = Form(None),
    processor_name: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]
    role = session.get("role")

    cat = db.query(DataCategory).filter(
        DataCategory.id == category_id,
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None
    ).first()
    if not cat:
        raise HTTPException(status_code=403, detail="Category not found or access denied")

    if role == "data_owner" and cat.owner_id != user_id:
        raise HTTPException(status_code=403, detail="You can only create records in your assigned categories.")

    coll_date = date.today() if role == "data_owner" else datetime.strptime(collection_date, "%Y-%m-%d").date()

    # Check rule overrides
    default_rule = db.query(CategoryRetentionRule).filter(
        CategoryRetentionRule.category_id == category_id,
        CategoryRetentionRule.is_default == True
    ).first()

    if notes:
        from app.helpers import detect_pii_in_text
        pii = detect_pii_in_text(notes)
        if pii:
            log_audit(db, org_id, "pii_ingestion_blocked", "data_record", None, user_id, {
                "detected": pii
            }, request.client.host if request.client else None)
            raise HTTPException(
                status_code=400,
                detail=f"Zero-Knowledge Protection: The notes field contains potential personal data ({', '.join(pii)}). SafeData only retains metadata references, not raw personal data."
            )

    eff_proc_name = processor_name.strip() if processor_name and processor_name.strip() else (cat.processor_name if cat.processor_name else None)

    new_rec = DataRecord(
        organization_id=org_id,
        category_id=category_id,
        retention_rule_id=default_rule.id if default_rule else None,
        record_reference=record_reference.strip(),
        data_subject_type=data_subject_type.strip() if data_subject_type and data_subject_type.strip() else None,
        processor_name=eff_proc_name,
        processor_sync_status="synced",
        collection_date=coll_date,
        status="active",
        created_by_owner=(role == "data_owner"),
        created_by=user_id,
        notes=notes.strip() if notes else None
    )
    calculate_retention_end_date(db, new_rec)

    db.add(new_rec)
    db.commit()
    db.refresh(new_rec)

    log_audit(db, org_id, "record_created", "data_record", new_rec.id, user_id, {
        "category": cat.name,
        "collection_date": coll_date.strftime("%Y-%m-%d"),
        "created_by_owner": (role == "data_owner")
    }, request.client.host if request.client else None)

    return RedirectResponse(url="/records", status_code=303)

@router.get("/records/view/{id}", response_class=HTMLResponse)
def view_record_details(id: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]
    role = session.get("role")

    # Fetch record including soft deleted or disposed for read-only view
    record = db.query(DataRecord).filter(
        DataRecord.id == id,
        DataRecord.organization_id == org_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if role == "data_owner" and record.category.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    creator_name = "System"
    if record.created_by:
        creator = db.query(User).filter(User.id == record.created_by).first()
        if creator:
            creator_name = creator.name

    all_categories = db.query(DataCategory).filter(
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None
    ).order_by(DataCategory.name).all()

    attachments = db.query(Attachment).filter(
        Attachment.record_id == id,
        Attachment.deleted_at == None
    ).order_by(Attachment.created_at.desc()).all()

    audit_trail = db.query(AuditLog).filter(
        AuditLog.organization_id == org_id,
        AuditLog.entity_type == "data_record",
        AuditLog.entity_id == id
    ).order_by(AuditLog.id.desc()).limit(10).all()

    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="records_view.html", context={
        "page_title": f"Record {record.record_reference}",
        "active_nav": "records",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "record": record,
        "creator_name": creator_name,
        "all_categories": all_categories,
        "attachments": attachments,
        "audit_trail": audit_trail
    })

@router.get("/records/edit/{id}", response_class=HTMLResponse)
def edit_record_form(id: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    record = db.query(DataRecord).filter(
        DataRecord.id == id,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="records_edit.html", context={
        "page_title": "Edit Record",
        "active_nav": "records",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "record": record
    })

@router.post("/records/edit/{id}")
def handle_edit_record(
    id: int,
    request: Request,
    record_reference: str = Form(...),
    data_subject_type: Optional[str] = Form(None),
    collection_date: str = Form(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    record = db.query(DataRecord).filter(
        DataRecord.id == id,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if notes:
        from app.helpers import detect_pii_in_text
        pii = detect_pii_in_text(notes)
        if pii:
            log_audit(db, org_id, "pii_ingestion_blocked", "data_record", id, session["user_id"], {
                "detected": pii
            }, request.client.host if request.client else None)
            raise HTTPException(
                status_code=400,
                detail=f"Zero-Knowledge Protection: The notes field contains potential personal data ({', '.join(pii)}). SafeData only retains metadata references, not raw personal data."
            )

    coll_date = datetime.strptime(collection_date, "%Y-%m-%d").date()
    record.record_reference = record_reference.strip()
    record.data_subject_type = data_subject_type.strip() if data_subject_type else None
    record.collection_date = coll_date
    record.notes = notes.strip() if notes else None

    # Recalculate end date
    calculate_retention_end_date(db, record)
    db.commit()

    log_audit(db, org_id, "record_updated", "data_record", id, session["user_id"], {
        "reference": record.record_reference
    }, request.client.host if request.client else None)

    return RedirectResponse(url=f"/records/view/{id}", status_code=303)

@router.post("/records/reassign/{id}")
def handle_reassign_record(
    id: int,
    request: Request,
    new_category_id: int = Form(...),
    recalculate: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    record = db.query(DataRecord).filter(
        DataRecord.id == id,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    target_cat = db.query(DataCategory).filter(
        DataCategory.id == new_category_id,
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None
    ).first()
    if not target_cat:
        raise HTTPException(status_code=400, detail="Target category not found.")

    if record.original_category_id is None:
        record.original_category_id = record.category_id

    record.category_id = new_category_id
    default_rule = db.query(CategoryRetentionRule).filter(
        CategoryRetentionRule.category_id == new_category_id,
        CategoryRetentionRule.is_default == True
    ).first()
    record.retention_rule_id = default_rule.id if default_rule else None
    record.category_reassigned_at = datetime.utcnow()
    record.category_reassigned_by = session["user_id"]

    if recalculate:
        calculate_retention_end_date(db, record)

    db.commit()

    log_audit(db, org_id, "record_reassigned", "data_record", id, session["user_id"], {
        "from_category": record.original_category_id,
        "to_category": new_category_id,
        "recalculated": bool(recalculate)
    }, request.client.host if request.client else None)

    return RedirectResponse(url=f"/records/view/{id}", status_code=303)

@router.post("/records/approve/{id}")
def handle_approve_disposal(
    id: int,
    request: Request,
    decision: str = Form(...),
    reason: Optional[str] = Form(""),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]

    record = db.query(DataRecord).filter(
        DataRecord.id == id,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if record.status != "disposal_requested":
        raise HTTPException(status_code=400, detail="No pending disposal request for this record.")

    if decision == "reject":
        record.status = "due_review"
        record.disposal_requested_at = None
        record.disposal_requested_by = None
        db.commit()
        log_audit(db, org_id, "disposal_request_rejected", "data_record", id, user_id, {
            "reason": reason
        }, request.client.host if request.client else None)
    else:
        # Enforce dual-approver rule
        if record.disposal_requested_by == user_id:
            raise HTTPException(status_code=400, detail="Dual approval requires a different user to confirm.")
        
        execute_disposal(db, id, actor_id=user_id, ip_address=request.client.host if request.client else "127.0.0.1")
        log_audit(db, org_id, "disposal_request_approved", "data_record", id, user_id, {
            "dual_approval": True
        }, request.client.host if request.client else None)

    return RedirectResponse(url=f"/records/view/{id}", status_code=303)


@router.post("/records/dispose/{id}")
def handle_request_disposal(
    id: int,
    request: Request,
    auth_credential: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]
    ip_addr = request.client.host if request.client else "127.0.0.1"

    # Step-Up Verification (if credential provided)
    if auth_credential is not None and str(auth_credential).strip():
        ok, msg = verify_stepup_authentication(db, user_id, auth_credential)
        if not ok:
            log_audit(db, org_id, "stepup_auth_failed", "data_record", id, user_id, {"error": msg, "action": "dispose"}, ip_addr)
            return RedirectResponse(url=f"/records/view/{id}?error=stepup_failed", status_code=303)
        log_audit(db, org_id, "stepup_auth_success", "data_record", id, user_id, {"action": "dispose"}, ip_addr)

    record = db.query(DataRecord).filter(
        DataRecord.id == id,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if record.legal_hold:
        raise HTTPException(status_code=400, detail="Record is on legal hold.")

    if record.category.requires_dual_approval:
        record.status = "disposal_requested"
        record.disposal_requested_at = datetime.utcnow()
        record.disposal_requested_by = user_id
        db.commit()
        log_audit(db, org_id, "disposal_requested", "data_record", id, user_id, None, ip_addr)
    else:
        execute_disposal(db, id, actor_id=user_id, ip_address=ip_addr)
        log_audit(db, org_id, "disposal_request_approved", "data_record", id, user_id, {
            "single_approver": True
        }, ip_addr)

    return RedirectResponse(url=f"/records/view/{id}", status_code=303)

@router.post("/records/bulk_dispose")
def handle_bulk_dispose(
    request: Request,
    record_ids: str = Form(...),
    auth_credential: Optional[str] = Form(None),
    return_url: Optional[str] = Form("/records"),
    db: Session = Depends(get_db)
):
    """Bulk safe disposal for multiple records that have exceeded retention period."""
    session = get_session(request)
    if not session or "user_id" not in session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]
    ip_addr = request.client.host if request.client else "127.0.0.1"

    # Step-Up Verification
    if auth_credential is not None and str(auth_credential).strip():
        ok, msg = verify_stepup_authentication(db, user_id, auth_credential)
        if not ok:
            log_audit(db, org_id, "stepup_auth_failed", "data_record", 0, user_id, {"error": msg, "action": "bulk_dispose"}, ip_addr)
            return RedirectResponse(url=f"{return_url}?error=stepup_failed", status_code=303)
        log_audit(db, org_id, "stepup_auth_success", "data_record", 0, user_id, {"action": "bulk_dispose"}, ip_addr)

    raw_ids = [int(i.strip()) for i in record_ids.split(",") if i.strip().isdigit()]
    if not raw_ids:
        return RedirectResponse(url=f"{return_url}?error=no_records_selected", status_code=303)

    from app.engine import is_disposal_frozen
    if is_disposal_frozen(db, org_id):
        log_audit(db, org_id, "disposal_aborted_freeze", "data_record", 0, user_id, {"action": "bulk_dispose"}, ip_addr)
        return RedirectResponse(url=f"{return_url}?error=disposal_frozen", status_code=303)

    today = date.today()
    disposed_count = 0
    requested_count = 0
    skipped_count = 0

    for rec_id in raw_ids:
        rec = db.query(DataRecord).filter(
            DataRecord.id == rec_id,
            DataRecord.organization_id == org_id,
            DataRecord.deleted_at == None,
            DataRecord.status != "disposed"
        ).first()

        if not rec or rec.legal_hold:
            skipped_count += 1
            continue

        is_due = (
            (rec.retention_end_date and rec.retention_end_date <= today)
            or rec.status in ("due_disposal", "expired")
        )

        if not is_due:
            skipped_count += 1
            continue

        cat = rec.category
        if cat and cat.requires_dual_approval:
            rec.status = "disposal_requested"
            rec.disposal_requested_at = datetime.utcnow()
            rec.disposal_requested_by = user_id
            db.commit()
            log_audit(db, org_id, "disposal_requested", "data_record", rec.id, user_id, {"bulk": True}, ip_addr)
            requested_count += 1
        else:
            success = execute_disposal(db, rec.id, actor_id=user_id, ip_address=ip_addr)
            if success:
                log_audit(db, org_id, "disposal_request_approved", "data_record", rec.id, user_id, {
                    "single_approver": True,
                    "bulk": True
                }, ip_addr)
                disposed_count += 1
            else:
                skipped_count += 1

    return RedirectResponse(
        url=f"{return_url}?disposed={disposed_count}&requested={requested_count}&skipped={skipped_count}",
        status_code=303
    )

@router.post("/records/legal_hold/{id}")
def handle_legal_hold(
    id: int,
    request: Request,
    action: Optional[str] = Form(None),
    reason: Optional[str] = Form(""),
    auth_credential: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]
    ip_addr = request.client.host if request.client else "127.0.0.1"

    # Step-up verification for legal hold changes
    if auth_credential is not None and str(auth_credential).strip():
        ok, msg = verify_stepup_authentication(db, user_id, auth_credential)
        if not ok:
            log_audit(db, org_id, "stepup_auth_failed", "data_record", id, user_id, {"error": msg, "action": f"legal_hold_{action}"}, ip_addr)
            return RedirectResponse(url=f"/records/view/{id}?error=stepup_failed", status_code=303)
        log_audit(db, org_id, "stepup_auth_success", "data_record", id, user_id, {"action": f"legal_hold_{action}"}, ip_addr)

    record = db.query(DataRecord).filter(
        DataRecord.id == id,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if action == "lift":
        record.legal_hold = False
        record.legal_hold_lifted_at = datetime.utcnow()
        db.commit()
        log_audit(db, org_id, "legal_hold_lifted", "data_record", id, user_id, None, ip_addr)
    else:
        if not reason.strip():
            raise HTTPException(status_code=400, detail="Reason for legal hold is required.")
        record.legal_hold = True
        record.legal_hold_reason = reason.strip()
        record.legal_hold_by = user_id
        record.legal_hold_at = datetime.utcnow()
        record.legal_hold_lifted_at = None
        db.commit()
        log_audit(db, org_id, "legal_hold_set", "data_record", id, user_id, {
            "reason": reason.strip()
        }, ip_addr)

    return RedirectResponse(url=f"/records/view/{id}", status_code=303)


@router.post("/records/disposal_approve/{id}")
def handle_disposal_approve(
    id: int,
    request: Request,
    auth_credential: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """B5 dual-approval: second approver approves disposal."""
    session = get_session(request)
    if not session or "user_id" not in session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]
    ip_addr = request.client.host if request.client else "127.0.0.1"

    # Step-Up Verification
    if auth_credential is not None and str(auth_credential).strip():
        ok, msg = verify_stepup_authentication(db, user_id, auth_credential)
        if not ok:
            log_audit(db, org_id, "stepup_auth_failed", "data_record", id, user_id, {"error": msg, "action": "disposal_approve"}, ip_addr)
            return RedirectResponse(url=f"/records/view/{id}?error=stepup_failed", status_code=303)
        log_audit(db, org_id, "stepup_auth_success", "data_record", id, user_id, {"action": "disposal_approve"}, ip_addr)

    from app.engine import approve_disposal
    result = approve_disposal(
        db, org_id, id, user_id,
        ip=ip_addr
    )
    return RedirectResponse(url=f"/records/view/{id}", status_code=303)


@router.post("/records/disposal_reject/{id}")
def handle_disposal_reject(
    id: int,
    request: Request,
    reason: Optional[str] = Form(""),
    db: Session = Depends(get_db)
):
    """B5 dual-approval: reject a pending disposal request."""
    session = get_session(request)
    if not session or "user_id" not in session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    from app.engine import reject_disposal
    reject_disposal(
        db, session["org_id"], id, session["user_id"],
        reason=reason or "", ip=request.client.host if request.client else None
    )
    return RedirectResponse(url=f"/records/view/{id}", status_code=303)


@router.post("/attachments/upload/{record_id}")
async def handle_attachment_upload(
    record_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]

    record = db.query(DataRecord).filter(
        DataRecord.id == record_id,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    original_filename = file.filename
    ext = original_filename.split('.')[-1].lower() if '.' in original_filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File extension not allowed: .{ext}")

    content = await file.read()
    file_size = len(content)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds limit of 10MB.")

    # Gap 5: Validate file magic bytes match declared extension
    if not _validate_file_magic(content, ext):
        raise HTTPException(
            status_code=400,
            detail=f"File content does not match the .{ext} extension. Upload rejected."
        )

    stored_filename = f"{uuid.uuid4().hex}.{ext}"
    dest_path = os.path.join(UPLOAD_PATH, stored_filename)

    with open(dest_path, "wb") as f:
        f.write(content)

    new_att = Attachment(
        organization_id=org_id,
        record_id=record_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        uploaded_by=user_id
    )
    db.add(new_att)
    db.commit()

    log_audit(db, org_id, "attachment_uploaded", "attachment", new_att.id, user_id, {
        "record_id": record_id,
        "name": original_filename
    }, request.client.host if request.client else None)

    return RedirectResponse(url=f"/records/view/{record_id}", status_code=303)

@router.get("/attachments/download/{id}")
def handle_attachment_download(id: int, request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    att = db.query(Attachment).filter(
        Attachment.id == id,
        Attachment.organization_id == org_id,
        Attachment.deleted_at == None
    ).first()

    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    file_path = os.path.join(UPLOAD_PATH, att.stored_filename)

    # Gap 6: Path traversal protection — ensure resolved path stays within UPLOAD_PATH
    real_path = os.path.realpath(file_path)
    real_upload = os.path.realpath(UPLOAD_PATH)
    if not real_path.startswith(real_upload + os.sep) and real_path != real_upload:
        raise HTTPException(status_code=403, detail="Access denied.")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on storage server.")

    # Clean the filename for presentation in headers
    safe_name = "".join(c for c in att.original_filename if c.isalnum() or c in "._-")
    return FileResponse(
        path=file_path,
        media_type=att.mime_type,
        filename=safe_name
    )

@router.get("/attachments", response_class=HTMLResponse)
def list_attachments(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session or session.get("role") not in ("admin", "dpo"):
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    attachments = db.query(Attachment).filter(
        Attachment.organization_id == org_id,
        Attachment.deleted_at == None
    ).order_by(Attachment.created_at.desc()).all()

    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    return templates.TemplateResponse(request=request, name="attachments.html", context={
        "page_title": "Evidence Attachments",
        "active_nav": "attachments",
        "user_name": session["user_name"],
        "user_role": session["role"],
        "org_name": session["org_name"],
        "org_status": session["org_status"],
        "org_domain": session["org_domain"],
        "trial_days": 14,
        "law_label": labels["law"],
        "attachments": attachments
    })

@router.get("/records/export")
def export_records_csv(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    # RBAC: full-register export is restricted to admins and DPOs —
    # data_owner is category-scoped elsewhere and must not bypass that here.
    if session.get("role") not in ("admin", "dpo"):
        raise HTTPException(status_code=403, detail="Only administrators and DPOs can export the full register.")

    org_id = session["org_id"]
    records = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    ).order_by(DataRecord.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Record ID", "Reference", "Category", "Collection Date", "Retention End Date", "Status", "Legal Hold", "Disposed At"])

    for r in records:
        writer.writerow([
            r.id, r.record_reference, r.category.name if r.category else "",
            r.collection_date, r.retention_end_date or "",
            r.status, "Yes" if r.legal_hold else "No", r.disposed_at or ""
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=retention_register_export.csv"}
    )

