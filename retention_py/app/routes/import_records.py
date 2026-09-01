import os
import csv
import io
import json
from datetime import datetime, date

from fastapi import APIRouter, Request, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ImportJob, DataRecord, DataCategory, CategoryRetentionRule
from app.auth import get_session
from app.helpers import get_country_regulation_labels, get_framework_badge, log_audit
from app.engine import calculate_retention_end_date

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

@router.get("/import", response_class=HTMLResponse)
def view_import_page(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))
    recent_jobs = db.query(ImportJob).filter(ImportJob.organization_id == org_id).order_by(ImportJob.id.desc()).limit(10).all()

    return templates.TemplateResponse(request=request, name="import.html", context=_ctx(session, labels, {
        "page_title": "Bulk CSV Import",
        "active_nav": "import",
        "recent_jobs": recent_jobs,
        "result": None
    }))

@router.post("/import")
async def handle_csv_import(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    session = get_session(request)
    if not session or "user_id" not in session:
        return RedirectResponse(url="/login", status_code=303)

    org_id = session["org_id"]
    user_id = session["user_id"]
    labels = get_country_regulation_labels(session.get("country", "OTHER"))

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))

    total_rows = 0
    valid_rows = 0
    imported_rows = 0
    skipped_rows = 0
    error_rows = 0
    error_report = []

    # Map category names to IDs for fast lookup
    cat_map = {c.name.lower(): c.id for c in db.query(DataCategory).filter(DataCategory.organization_id == org_id, DataCategory.deleted_at == None).all()}

    for line_num, row in enumerate(reader, start=2):
        total_rows += 1
        ref = row.get("record_reference") or row.get("reference") or row.get("record_id") or ""
        cat_name = row.get("category_name") or row.get("category") or ""
        coll_date_str = row.get("collection_date") or row.get("date") or ""
        subject_type = row.get("data_subject_type") or row.get("subject_type") or ""
        notes = row.get("notes") or ""

        if not ref.strip():
            error_rows += 1
            error_report.append({"line": line_num, "error": "Missing record_reference"})
            continue

        cat_id = cat_map.get(cat_name.strip().lower())
        if not cat_id:
            # Try parsing cat_name as integer ID
            try:
                cat_id = int(cat_name.strip())
            except ValueError:
                cat_id = None

        if not cat_id:
            error_rows += 1
            error_report.append({"line": line_num, "ref": ref, "error": f"Unknown category '{cat_name}'"})
            continue

        try:
            coll_date = datetime.strptime(coll_date_str.strip(), "%Y-%m-%d").date()
        except Exception:
            error_rows += 1
            error_report.append({"line": line_num, "ref": ref, "error": f"Invalid collection_date '{coll_date_str}'. Expected YYYY-MM-DD"})
            continue

        # Check duplicate
        exists = db.query(DataRecord).filter(DataRecord.organization_id == org_id, DataRecord.record_reference == ref.strip()).first()
        if exists:
            skipped_rows += 1
            continue

        valid_rows += 1

        new_rec = DataRecord(
            organization_id=org_id,
            category_id=cat_id,
            record_reference=ref.strip(),
            data_subject_type=subject_type.strip() if subject_type else None,
            collection_date=coll_date,
            status="active",
            notes=notes.strip() if notes else None,
            created_by=user_id
        )
        calculate_retention_end_date(db, new_rec)
        db.add(new_rec)
        imported_rows += 1

    db.commit()

    job = ImportJob(
        organization_id=org_id,
        imported_by=user_id,
        filename=file.filename,
        total_rows=total_rows,
        valid_rows=valid_rows,
        imported_rows=imported_rows,
        skipped_rows=skipped_rows,
        error_rows=error_rows,
        status="imported" if imported_rows > 0 else ("failed" if error_rows > 0 else "completed"),
        error_report=error_report,
        completed_at=datetime.utcnow()
    )
    db.add(job)
    db.commit()

    log_audit(db, org_id, "bulk_import", "data_record", None, user_id, {
        "filename": file.filename,
        "imported": imported_rows,
        "errors": error_rows
    }, request.client.host if request.client else None)

    recent_jobs = db.query(ImportJob).filter(ImportJob.organization_id == org_id).order_by(ImportJob.id.desc()).limit(10).all()

    return templates.TemplateResponse(request=request, name="import.html", context=_ctx(session, labels, {
        "page_title": "Bulk CSV Import",
        "active_nav": "import",
        "recent_jobs": recent_jobs,
        "result": {
            "total": total_rows,
            "imported": imported_rows,
            "skipped": skipped_rows,
            "errors": error_rows,
            "report": error_report
        }
    }))

@router.get("/import/sample")
def download_sample_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["record_reference", "category_name", "collection_date", "data_subject_type", "notes"])
    writer.writerow(["EMP-1001", "Employee Personnel Records", "2024-01-15", "Employee", "Standard onboarding file"])
    writer.writerow(["CUST-8892", "Marketing Consent Records", "2024-03-20", "Customer", "Opt-in via web portal"])
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=SafeData_import_sample.csv"}
    )
