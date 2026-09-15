from fastapi import APIRouter, Request, Response, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
import hashlib
import json
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models import ApiKey, ConnectedSystem, DataRecord, DataCategory, IntegrationLog, ConsentSignal
from app.engine import calculate_retention_end_date
from app.enterprise import within_rate_limit, api_key_can, log_integration
from app.helpers import log_audit

router = APIRouter()

# Helper to authenticate API Key (supports Authorization: Bearer and X-API-Key)
def authenticate_api_key(
    db: Session,
    authorization: Optional[str] = None,
    x_api_key: Optional[str] = None,
    required_permission: Optional[str] = None,
) -> ApiKey:
    raw_key = ""
    if authorization and authorization.startswith("Bearer "):
        raw_key = authorization.split(" ", 1)[1].strip()
    elif authorization and not authorization.startswith("Bearer "):
        raw_key = authorization.strip()
    elif x_api_key:
        raw_key = x_api_key.strip()

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API Key. Provide 'Authorization: Bearer <key>' or 'X-API-Key: <key>'."
        )

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

    # Gap 4: Enforce rate limiting (60 requests per minute per key)
    if not within_rate_limit(db, api_key.id, limit_per_min=60):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 60 requests per minute.",
            headers={"Retry-After": "60"},
        )

    # Gap 11: Enforce permission scoping
    if required_permission and not api_key_can(api_key, required_permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API Key does not have the '{required_permission}' permission."
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

class ConsentSignalRequest(BaseModel):
    record_reference: str
    category_id: Optional[int] = None
    signal_type: Optional[str] = "withdrawal"
    withdrawn_at: Optional[str] = None
    notes: Optional[str] = None

# Backward-compatibility alias
ConsentWithdrawalRequest = ConsentSignalRequest

@router.get("/health")
def api_health():
    return {"status": "healthy", "service": "SafeData API v1"}

@router.post("/ingest")
def api_ingest(
    payload: IngestRecordRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    api_key = authenticate_api_key(db, authorization=authorization, x_api_key=x_api_key, required_permission="ingest")
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
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    api_key = authenticate_api_key(db, authorization=authorization, x_api_key=x_api_key, required_permission="ingest")
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

@router.post("/consent/signal")
def api_consent_signal(
    payload: ConsentSignalRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    api_key = authenticate_api_key(db, authorization=authorization, x_api_key=x_api_key, required_permission="consent")
    org_id = api_key.organization_id

    # Parse signal timestamp if provided, else use current UTC
    withdrawn_dt = datetime.utcnow()
    if payload.withdrawn_at:
        try:
            withdrawn_dt = datetime.fromisoformat(payload.withdrawn_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            try:
                withdrawn_dt = datetime.strptime(payload.withdrawn_at, "%Y-%m-%d")
            except Exception:
                pass

    # Find record reference
    query = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.record_reference == payload.record_reference
    )
    if payload.category_id:
        query = query.filter(DataRecord.category_id == payload.category_id)

    records = query.all()
    if not records:
        # Record unmatched signal in ConsentSignal if connected system is known
        if api_key.system_id:
            signal = ConsentSignal(
                organization_id=org_id,
                system_id=api_key.system_id,
                external_ref=payload.record_reference,
                signal_type=payload.signal_type or "withdrawal",
                raw_payload=payload.model_dump_json(),
                status="unmatched",
            )
            db.add(signal)
            db.commit()
        raise HTTPException(status_code=404, detail="No matching records found for provided reference.")

    updated_count = 0
    for r in records:
        if r.status != "disposed" and not r.consent_withdrawn_at:
            r.consent_withdrawn_at = withdrawn_dt
            r.consent_withdrawn_by = None  # Inbound signal from external system, not an internal user
            calculate_retention_end_date(db, r)
            updated_count += 1
            log_audit(
                db, org_id, "consent_withdrawn", "data_record", r.id, None,
                {
                    "source": "api_signal",
                    "external_ref": payload.record_reference,
                    "signal_type": payload.signal_type or "withdrawal",
                    "disposal_due": r.retention_end_date.strftime("%Y-%m-%d") if r.retention_end_date else None,
                }
            )

    # Record matched signal if connected system is linked
    if api_key.system_id:
        signal = ConsentSignal(
            organization_id=org_id,
            system_id=api_key.system_id,
            external_ref=payload.record_reference,
            signal_type=payload.signal_type or "withdrawal",
            raw_payload=payload.model_dump_json(),
            status="processed" if updated_count > 0 else "matched",
            record_id=records[0].id if records else None,
            processed_at=datetime.utcnow() if updated_count > 0 else None,
        )
        db.add(signal)

    # Log integration API call
    log = IntegrationLog(
        organization_id=org_id,
        system_id=api_key.system_id,
        api_key_id=api_key.id,
        direction="inbound",
        endpoint="/api/v1/consent/signal",
        method="POST",
        status_code=200,
        request_body=payload.model_dump_json(),
        response_body=json.dumps({"status": "success", "updated_records": updated_count}),
        records_affected=updated_count,
    )
    db.add(log)
    db.commit()

    return {
        "status": "success",
        "signal_type": payload.signal_type or "withdrawal",
        "updated_records": updated_count,
        "records": [
            {
                "id": r.id,
                "record_reference": r.record_reference,
                "retention_end_date": r.retention_end_date.strftime("%Y-%m-%d") if r.retention_end_date else None,
                "status": r.status,
            }
            for r in records
        ],
    }


@router.post("/consent/withdraw", deprecated=True)
def api_consent_withdraw(
    payload: ConsentWithdrawalRequest,
    response: Response,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    """Backward-compatible endpoint. Clients should migrate to /api/v1/consent/signal."""
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</api/v1/consent/signal>; rel="successor-version"'
    return api_consent_signal(
        payload=payload,
        authorization=authorization,
        x_api_key=x_api_key,
        db=db
    )

@router.get("/records/status")
def api_record_status(
    record_reference: str,
    category_id: Optional[int] = None,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    api_key = authenticate_api_key(db, authorization, required_permission="read")
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
    api_key = authenticate_api_key(db, authorization, required_permission="read")
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
    api_key = authenticate_api_key(db, authorization, required_permission="dispose")
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
    api_key = authenticate_api_key(db, authorization, required_permission="terminate")
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


# ═══════════════════════════════════════════════════════════════════════════
#   A1: Real-time Dashboard Metrics JSON endpoint
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/dashboard/metrics")
def get_dashboard_metrics(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Returns live KPI counts for the calling API key's organization.
    Useful for embedding SafeData metrics in external dashboards.
    """
    from datetime import datetime, date, timezone
    from app.engine import compliance_metrics, disposals_by_month
    from sqlalchemy import func

    api_key = authenticate_api_key(db, authorization, x_api_key, required_permission="read")
    org_id = api_key.organization_id

    metrics = compliance_metrics(db, org_id)
    disposal_trend = disposals_by_month(db, org_id, months=6)

    return {
        "organization_id": org_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kpis": {
            "active_records": metrics.get("active", 0),
            "due_review": metrics.get("due_review", 0),
            "overdue": metrics.get("overdue", 0),
            "on_legal_hold": metrics.get("legal_hold", 0),
            "pending_approval": metrics.get("pending_approval", 0),
            "total_disposed": metrics.get("disposed", 0),
            "processor_records": metrics.get("processor_records", 0),
            "controller_records": metrics.get("controller_records", 0),
        },
        "disposal_trend_6m": disposal_trend,
    }


# ═══════════════════════════════════════════════════════════════════════════
#   A2: Disposal Workflow Analytics endpoint
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/disposal/analytics")
def get_disposal_analytics(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Returns disposal workflow analytics: success rate, avg time-to-disposal,
    pending approval aging, and method breakdown.
    """
    from datetime import datetime, timezone
    from sqlalchemy import func

    api_key = authenticate_api_key(db, authorization, x_api_key, required_permission="read")
    org_id = api_key.organization_id

    # Total disposed
    total_disposed = db.query(func.count(DataRecord.id)).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "disposed",
        DataRecord.deleted_at == None,
    ).scalar() or 0

    # Pending approval count
    pending = db.query(func.count(DataRecord.id)).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "disposal_requested",
        DataRecord.deleted_at == None,
    ).scalar() or 0

    # Avg time from request to disposal (days) for dual-approval records
    disposed_with_request = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "disposed",
        DataRecord.disposed_at != None,
        DataRecord.disposal_requested_at != None,
        DataRecord.deleted_at == None,
    ).all()

    avg_days_to_approval = None
    if disposed_with_request:
        deltas = [
            (r.disposed_at - r.disposal_requested_at).total_seconds() / 86400
            for r in disposed_with_request
            if r.disposed_at and r.disposal_requested_at
        ]
        if deltas:
            avg_days_to_approval = round(sum(deltas) / len(deltas), 1)

    # Oldest pending approval (aging)
    oldest_pending = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "disposal_requested",
        DataRecord.disposal_requested_at != None,
        DataRecord.deleted_at == None,
    ).order_by(DataRecord.disposal_requested_at.asc()).first()

    oldest_pending_days = None
    if oldest_pending and oldest_pending.disposal_requested_at:
        oldest_pending_days = (datetime.now(timezone.utc).replace(tzinfo=None) - oldest_pending.disposal_requested_at).days

    return {
        "organization_id": org_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_disposed": total_disposed,
        "pending_approvals": pending,
        "avg_days_to_disposal": avg_days_to_approval,
        "oldest_pending_approval_days": oldest_pending_days,
    }


# ═══════════════════════════════════════════════════════════════════════════
#   A3: Audit Chain Integrity Verification endpoint
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/audit/verify")
def verify_audit_integrity(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Runs SHA-256 HMAC chain verification on the calling org's audit log.
    Returns chain integrity status — suitable for compliance evidence.
    """
    from datetime import datetime, timezone
    from app.engine import verify_audit_chain

    api_key = authenticate_api_key(db, authorization, x_api_key, required_permission="read")
    org_id = api_key.organization_id

    result = verify_audit_chain(db, org_id=org_id)

    return {
        "organization_id": org_id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "chain_intact": result["ok"],
        "logs_verified": result.get("verified_count", 0),
        "first_broken_at": result.get("first_broken_log_id", None),
    }
