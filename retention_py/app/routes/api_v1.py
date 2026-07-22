from fastapi import APIRouter, Request, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
import hashlib
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models import ApiKey, ConnectedSystem, DataRecord, DataCategory, IntegrationLog
from app.engine import calculate_retention_end_date

router = APIRouter()

# Helper to authenticate API Key
def authenticate_api_key(db: Session, authorization: str) -> ApiKey:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Expected Bearer token."
        )
    
    raw_key = authorization.split(" ")[1]
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API Key."
        )

    # Check expiration
    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key has expired."
        )

    # Update last used
    api_key.last_used_at = datetime.utcnow()
    db.commit()
    return api_key

class IngestRecordRequest(BaseModel):
    record_reference: str
    category_id: int
    collection_date: str  # YYYY-MM-DD
    data_subject_type: Optional[str] = None
    notes: Optional[str] = None

class IngestBatchRequest(BaseModel):
    records: List[IngestRecordRequest]

class ConsentWithdrawalRequest(BaseModel):
    record_reference: str
    category_id: Optional[int] = None

@router.get("/health")
def api_health():
    return {"status": "healthy", "service": "ADRS API v1"}

@router.post("/ingest")
def api_ingest(
    payload: IngestRecordRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    api_key = authenticate_api_key(db, authorization)
    org_id = api_key.organization_id

    try:
        coll_date = datetime.strptime(payload.collection_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD.")

    # Verify category exists for org
    cat = db.query(DataCategory).filter(
        DataCategory.id == payload.category_id,
        DataCategory.organization_id == org_id
    ).first()
    if not cat:
        raise HTTPException(status_code=400, detail="Category not found.")

    # Deduplicate record reference
    exists = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.record_reference == payload.record_reference
    ).first()
    if exists:
        return {"status": "duplicate", "record_id": exists.id, "message": "Record reference already exists."}

    new_rec = DataRecord(
        organization_id=org_id,
        category_id=payload.category_id,
        record_reference=payload.record_reference,
        data_subject_type=payload.data_subject_type,
        collection_date=coll_date,
        status="active",
        notes=payload.notes
    )
    calculate_retention_end_date(db, new_rec)

    db.add(new_rec)
    db.commit()
    db.refresh(new_rec)

    # Log integration API call
    log = IntegrationLog(
        organization_id=org_id,
        system_id=api_key.system_id,
        api_key_id=api_key.id,
        direction="inbound",
        endpoint="/api/v1/ingest",
        method="POST",
        status_code=200,
        request_body=payload.model_dump_json(),
        response_body='{"status": "success"}',
        records_affected=1
    )
    db.add(log)
    db.commit()

    return {"status": "success", "record_id": new_rec.id}

@router.post("/ingest/batch")
def api_ingest_batch(
    payload: IngestBatchRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    api_key = authenticate_api_key(db, authorization)
    org_id = api_key.organization_id

    records_created = 0
    duplicates = 0

    for rec_data in payload.records:
        try:
            coll_date = datetime.strptime(rec_data.collection_date, "%Y-%m-%d").date()
        except ValueError:
            continue

        cat = db.query(DataCategory).filter(
            DataCategory.id == rec_data.category_id,
            DataCategory.organization_id == org_id
        ).first()
        if not cat:
            continue

        exists = db.query(DataRecord).filter(
            DataRecord.organization_id == org_id,
            DataRecord.record_reference == rec_data.record_reference
        ).first()
        if exists:
            duplicates += 1
            continue

        new_rec = DataRecord(
            organization_id=org_id,
            category_id=rec_data.category_id,
            record_reference=rec_data.record_reference,
            data_subject_type=rec_data.data_subject_type,
            collection_date=coll_date,
            status="active",
            notes=rec_data.notes
        )
        calculate_retention_end_date(db, new_rec)
        db.add(new_rec)
        records_created += 1

    db.commit()

    # Log batch run
    log = IntegrationLog(
        organization_id=org_id,
        system_id=api_key.system_id,
        api_key_id=api_key.id,
        direction="inbound",
        endpoint="/api/v1/ingest/batch",
        method="POST",
        status_code=200,
        request_body=payload.model_dump_json(),
        response_body='{"status": "success"}',
        records_affected=records_created
    )
    db.add(log)
    db.commit()

    return {
        "status": "success",
        "processed": records_created,
        "duplicates_skipped": duplicates
    }

@router.post("/consent/withdraw")
def api_consent_withdraw(
    payload: ConsentWithdrawalRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    api_key = authenticate_api_key(db, authorization)
    org_id = api_key.organization_id

    # Find record reference
    query = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.record_reference == payload.record_reference
    )
    if payload.category_id:
        query = query.filter(DataRecord.category_id == payload.category_id)
        
    records = query.all()
    if not records:
        raise HTTPException(status_code=404, detail="No matching records found.")

    updated_count = 0
    for r in records:
        if r.status != "disposed" and not r.consent_withdrawn_at:
            r.consent_withdrawn_at = datetime.utcnow()
            calculate_retention_end_date(db, r)
            updated_count += 1

    db.commit()

    return {"status": "success", "updated_records": updated_count}

@router.get("/records/status")
def api_record_status(
    record_reference: str,
    category_id: Optional[int] = None,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    api_key = authenticate_api_key(db, authorization)
    org_id = api_key.organization_id

    query = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.record_reference == record_reference
    )
    if category_id:
        query = query.filter(DataRecord.category_id == category_id)

    record = query.first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")

    return {
        "record_id": record.id,
        "record_reference": record.record_reference,
        "status": record.status,
        "collection_date": record.collection_date.strftime("%Y-%m-%d"),
        "retention_end_date": record.retention_end_date.strftime("%Y-%m-%d") if record.retention_end_date else None,
        "legal_hold": record.legal_hold
    }

class DisposedRequest(BaseModel):
    external_ref: str

class TerminateRequest(BaseModel):
    external_ref: str
    termination_date: Optional[str] = None

@router.get("/categories")
def api_list_categories(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    api_key = authenticate_api_key(db, authorization)
    org_id = api_key.organization_id

    categories = db.query(DataCategory).filter(
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None,
        DataCategory.is_active == True
    ).order_by(DataCategory.name).all()

    return {
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "framework": c.compliance_framework,
                "disposal_trigger": c.disposal_trigger,
                "retention_period_label": c.retention_period_label
            } for c in categories
        ]
    }

@router.post("/records/disposed")
def api_records_disposed(
    payload: DisposedRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    api_key = authenticate_api_key(db, authorization)
    org_id = api_key.organization_id

    # Find matching records
    records = db.query(DataRecord).filter(
        DataRecord.record_reference == payload.external_ref,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    ).all()

    if not records:
        raise HTTPException(status_code=404, detail="No active record matched this reference.")

    disposed_count = 0
    for r in records:
        if execute_disposal(db, r.id, actor_id=None, ip_address="API"):
            disposed_count += 1

    return {
        "status": "processed",
        "external_ref": payload.external_ref,
        "matched_count": len(records),
        "disposed_count": disposed_count
    }

@router.post("/records/terminate")
def api_records_terminate(
    payload: TerminateRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    api_key = authenticate_api_key(db, authorization)
    org_id = api_key.organization_id

    term_date_str = payload.termination_date or date.today().strftime("%Y-%m-%d")
    try:
        term_date = datetime.strptime(term_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="termination_date must be YYYY-MM-DD.")

    # Find active records under account_closure categories that don't have an end date yet
    records = db.query(DataRecord).join(
        DataCategory, DataRecord.category_id == DataCategory.id
    ).filter(
        DataRecord.record_reference == payload.external_ref,
        DataRecord.organization_id == org_id,
        DataCategory.disposal_trigger == "account_closure",
        DataRecord.retention_end_date == None,
        DataRecord.deleted_at == None,
        DataRecord.status != "disposed"
    ).all()

    updated_records = []
    for r in records:
        # Calculate retention period in days from category
        days = r.category.retention_period_days
        rend = term_date + timedelta(days=days)
        r.retention_end_date = rend
        db.commit()

        log_audit(db, org_id, "account_terminated", "data_record", r.id, None, {
            "source": "enterprise_api",
            "external_ref": payload.external_ref,
            "termination_date": term_date_str,
            "retention_end_date": rend.strftime("%Y-%m-%d")
        }, "API")

        updated_records.append({
            "record_id": r.id,
            "category": r.category.name,
            "retention_end_date": rend.strftime("%Y-%m-%d")
        })

    return {
        "status": "processed",
        "external_ref": payload.external_ref,
        "matched_count": len(records),
        "updated_records": updated_records
    }

