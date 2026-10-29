from fastapi import APIRouter, Request, Response, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
import hashlib
import json
from datetime import datetime, date, timedelta, timezone
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from typing import List, Optional

from app.database import get_db
from app.models import ApiKey, ConnectedSystem, DataRecord, DataCategory, IntegrationLog, ConsentSignal, Organization
from app.engine import (
    effective_policy, needs_dual_approval,
    calculate_retention_end_date, execute_disposal, is_disposal_frozen,
    compliance_metrics, disposals_by_month, verify_audit_chain,
)
from app.core.clock import business_today, business_date, UTC
from app.enterprise import within_rate_limit, api_key_can, log_integration
from app.helpers import log_audit

router = APIRouter()

# Maximum records accepted in a single batch ingest call
MAX_BATCH_SIZE = 500

# Helper to authenticate API Key (supports Authorization: Bearer and X-API-Key)
def authenticate_api_key(
    db: Session,
    authorization: Optional[str] = None,
    x_api_key: Optional[str] = None,
    required_permission: Optional[str] = None,
    request: Optional[Request] = None,
) -> ApiKey:
    ip = request.client.host if (request is not None and request.client) else None
    _throttle_failed_auth(db, ip)
    raw_key = ""
    if authorization and authorization.startswith("Bearer ") and len(authorization) > 7:
        raw_key = authorization.split(" ", 1)[1].strip()
    elif authorization and not authorization.startswith("Bearer "):
        raw_key = authorization.strip()
    elif x_api_key:
        raw_key = x_api_key.strip()

    if not raw_key:
        _log_api_auth_failure(db, None, "missing_key", ip)
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
        _log_api_auth_failure(db, None, "invalid_key", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API Key."
        )

    # Check expiration
    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        _log_api_auth_failure(db, api_key, "expired_key", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key has expired."
        )

    # Enforce tenant account status: suspended / expired-trial orgs lose API access
    org = db.query(Organization).filter(Organization.id == api_key.organization_id).first()
    if not org or org.status == "suspended":
        _log_api_auth_failure(db, api_key, "org_suspended", ip)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organisation account is suspended. Contact support."
        )

    # Enforce rate limiting using the key's configured per-minute limit
    limit = api_key.rate_limit_per_min or 60
    if not within_rate_limit(db, api_key.id, limit_per_min=limit):
        _log_api_rate_limit(db, api_key)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {limit} requests per minute.",
            headers={"Retry-After": "60"},
        )

    # Enforce permission scoping
    if required_permission and not api_key_can(api_key, required_permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API Key does not have the '{required_permission}' permission."
        )

    # Update last used
    api_key.last_used_at = datetime.utcnow()
    db.commit()
    return api_key


FAILED_AUTH_PER_MIN = 20


def _throttle_failed_auth(db: Session, ip: Optional[str]) -> None:
    """Stop a client that keeps sending bad keys: 429 after FAILED_AUTH_PER_MIN in a minute.

    Keys are 192-bit random, so guessing is not the risk; the risk is a flood filling the
    log table. Failures are recorded with the caller's IP so this can be counted.
    """
    if not ip:
        return
    try:
        from app.models import IntegrationLog as _IL
        cutoff = datetime.utcnow() - timedelta(minutes=1)
        n = db.query(func.count(_IL.id)).filter(
            _IL.method == "AUTH", _IL.ip_address == ip, _IL.created_at >= cutoff
        ).scalar() or 0
    except Exception:
        return
    if n >= FAILED_AUTH_PER_MIN:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a minute.",
                            headers={"Retry-After": "60"})


def _log_api_auth_failure(db: Session, api_key, reason: str, ip: Optional[str] = None):
    """Record failed API authentication attempts so brute-force probing is visible."""
    try:
        log_integration(
            db,
            api_key.system_id if api_key else None,
            api_key.id if api_key else None,
            direction="inbound",
            endpoint="/api/v1/auth",
            method="AUTH",
            status_code=401,
            error=f"auth_failed:{reason}",
            ip_address=ip,
            org_id=api_key.organization_id if api_key else 1,
        )
    except Exception:
        pass


def _log_api_rate_limit(db: Session, api_key):
    """Record a rate-limited rejection."""
    try:
        log_integration(
            db,
            api_key.system_id,
            api_key.id,
            direction="inbound",
            endpoint="/api/v1/rate_limited",
            method="RATE",
            status_code=429,
            error="rate_limit_exceeded",
        )
    except Exception:
        pass


MAX_REF_LEN = 255
MAX_TEXT_LEN = 2000
EARLIEST_DATE = date(2000, 1, 1)


def _parse_business_date(value: str, field: str) -> date:
    """Strict YYYY-MM-DD. Raises ValueError with a message naming the field."""
    try:
        d = datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{field} must be a date written YYYY-MM-DD.")
    if d < EARLIEST_DATE:
        raise ValueError(f"{field} is too far in the past.")
    return d


def _clean_ref(value: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError("record_reference is required.")
    if len(v) > MAX_REF_LEN:
        raise ValueError(f"record_reference is longer than {MAX_REF_LEN} characters.")
    return v


class IngestRecordRequest(BaseModel):
    record_reference: str
    category_id: int
    collection_date: str  # YYYY-MM-DD, a Lagos business date
    data_subject_type: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=MAX_TEXT_LEN)

    @field_validator("record_reference")
    @classmethod
    def _ref(cls, v):
        return _clean_ref(v)


class IngestBatchRequest(BaseModel):
    # Items are validated one by one in the handler so a single bad row is reported, not fatal.
    records: List[dict] = Field(..., max_length=MAX_BATCH_SIZE)


class ConsentSignalRequest(BaseModel):
    record_reference: str
    category_id: Optional[int] = None
    signal_type: Optional[str] = Field("withdrawal", max_length=50)
    withdrawn_at: Optional[str] = Field(None, max_length=40)
    notes: Optional[str] = Field(None, max_length=MAX_TEXT_LEN)

    @field_validator("record_reference")
    @classmethod
    def _ref(cls, v):
        return _clean_ref(v)


# Backward-compatibility alias
ConsentWithdrawalRequest = ConsentSignalRequest


def _key_deps(permission: str):
    """FastAPI dependency: authenticate with Authorization: Bearer or X-API-Key."""
    def dep(
        request: Request,
        authorization: Optional[str] = Header(None),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        db: Session = Depends(get_db),
    ) -> ApiKey:
        return authenticate_api_key(db, authorization, x_api_key, permission, request)
    return dep


def _log_call(db: Session, api_key: ApiKey, endpoint: str, status_code: int,
              affected: int = 0, request_body=None, response_body=None, method: str = "POST") -> None:
    """One inbound log row per authenticated call. The per-minute rate limit counts these rows."""
    db.add(IntegrationLog(
        organization_id=api_key.organization_id, system_id=api_key.system_id, api_key_id=api_key.id,
        direction="inbound", endpoint=endpoint, method=method, status_code=status_code,
        request_body=request_body, response_body=response_body, records_affected=affected,
    ))
    db.commit()


def _active_category(db: Session, org_id: int, category_id: int):
    return db.query(DataCategory).filter(
        DataCategory.id == category_id,
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None,  # noqa: E711
        DataCategory.is_active == True,  # noqa: E712
    ).first()


def _ingest_one(db: Session, org_id: int, rec: IngestRecordRequest):
    """Validate and add one record. Returns ('created'|'duplicate', record) or raises ValueError."""
    coll_date = _parse_business_date(rec.collection_date, "collection_date")
    if coll_date > business_today() + timedelta(days=1):
        raise ValueError("collection_date is in the future.")
    cat = _active_category(db, org_id, rec.category_id)
    if not cat:
        raise ValueError("category_id is not an active category of this organisation.")
    exists = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.record_reference == rec.record_reference,
    ).first()
    if exists:
        return "duplicate", exists
    new_rec = DataRecord(
        organization_id=org_id, category_id=rec.category_id, record_reference=rec.record_reference,
        data_subject_type=(rec.data_subject_type or None), collection_date=coll_date,
        status="active", notes=rec.notes,
    )
    new_rec.category = cat
    calculate_retention_end_date(db, new_rec)
    db.add(new_rec)
    db.flush()
    return "created", new_rec


@router.get("/health")
def api_health():
    return {"status": "healthy", "service": "SafeData API v1"}


@router.post("/ingest")
def api_ingest(
    payload: IngestRecordRequest,
    api_key: ApiKey = Depends(_key_deps("ingest")),
    db: Session = Depends(get_db),
):
    org_id = api_key.organization_id
    try:
        outcome, rec = _ingest_one(db, org_id, payload)
    except ValueError as exc:
        db.rollback()
        _log_call(db, api_key, "/api/v1/ingest", 400, 0, payload.model_dump_json(), json.dumps({"error": str(exc)}))
        raise HTTPException(status_code=400, detail=str(exc))
    if outcome == "duplicate":
        _log_call(db, api_key, "/api/v1/ingest", 200, 0, payload.model_dump_json(), '{"status": "duplicate"}')
        return {"status": "duplicate", "record_id": rec.id, "message": "Record reference already exists."}
    _log_call(db, api_key, "/api/v1/ingest", 200, 1, payload.model_dump_json(), '{"status": "success"}')
    return {"status": "success", "record_id": rec.id}


@router.post("/ingest/batch")
def api_ingest_batch(
    payload: IngestBatchRequest,
    api_key: ApiKey = Depends(_key_deps("ingest")),
    db: Session = Depends(get_db),
):
    org_id = api_key.organization_id
    created = 0
    duplicates = 0
    rejected = []
    for index, raw in enumerate(payload.records):
        try:
            item = IngestRecordRequest(**raw)
            outcome, _rec = _ingest_one(db, org_id, item)
        except Exception as exc:  # validation problems are reported per row, never silently dropped
            if hasattr(exc, "errors"):
                exc = "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors())
            rejected.append({"index": index, "record_reference": str(raw.get("record_reference", ""))[:80]
                             if isinstance(raw, dict) else "", "error": str(exc)})
            continue
        if outcome == "created":
            created += 1
        else:
            duplicates += 1
    db.commit()
    body = {"status": "success" if not rejected else "partial", "processed": created,
            "duplicates_skipped": duplicates, "rejected": rejected}
    _log_call(db, api_key, "/api/v1/ingest/batch", 200, created,
              json.dumps({"count": len(payload.records)}), json.dumps({k: v for k, v in body.items() if k != "rejected"}
                                                                       | {"rejected_count": len(rejected)}))
    return body


def _parse_signal_time(value: Optional[str]) -> datetime:
    """Naive UTC datetime for a withdrawal. Accepts ISO timestamps (with or without offset)
    and plain dates (a Lagos business date). Anything else is an error, never 'now'."""
    if not value:
        return datetime.now(UTC).replace(tzinfo=None)
    v = value.strip()
    try:
        if len(v) == 10:
            return datetime.strptime(v, "%Y-%m-%d")
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail="withdrawn_at must be an ISO timestamp or YYYY-MM-DD.")
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    if dt > datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1):
        raise HTTPException(status_code=422, detail="withdrawn_at is in the future.")
    if dt.date() < EARLIEST_DATE:
        raise HTTPException(status_code=422, detail="withdrawn_at is too far in the past.")
    return dt


@router.post("/consent/signal")
def api_consent_signal(
    payload: ConsentSignalRequest,
    api_key: ApiKey = Depends(_key_deps("consent")),
    db: Session = Depends(get_db),
):
    org_id = api_key.organization_id
    withdrawn_dt = _parse_signal_time(payload.withdrawn_at)

    # Find record reference
    query = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.record_reference == payload.record_reference,
        DataRecord.deleted_at == None,  # noqa: E711
    )
    if payload.category_id:
        query = query.filter(DataRecord.category_id == payload.category_id)

    records = query.all()
    if not records:
        # Record unmatched signal in ConsentSignal if connected system is known
        if api_key.system_id:
            db.add(ConsentSignal(
                organization_id=org_id, system_id=api_key.system_id,
                external_ref=payload.record_reference,
                signal_type=payload.signal_type or "withdrawal",
                raw_payload=payload.model_dump_json(), status="unmatched",
            ))
            db.commit()
        _log_call(db, api_key, "/api/v1/consent/signal", 404, 0, payload.model_dump_json())
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

    if api_key.system_id:
        db.add(ConsentSignal(
            organization_id=org_id, system_id=api_key.system_id,
            external_ref=payload.record_reference,
            signal_type=payload.signal_type or "withdrawal",
            raw_payload=payload.model_dump_json(),
            status="processed" if updated_count > 0 else "matched",
            record_id=records[0].id if records else None,
            processed_at=datetime.utcnow() if updated_count > 0 else None,
        ))

    db.add(IntegrationLog(
        organization_id=org_id, system_id=api_key.system_id, api_key_id=api_key.id,
        direction="inbound", endpoint="/api/v1/consent/signal", method="POST", status_code=200,
        request_body=payload.model_dump_json(),
        response_body=json.dumps({"status": "success", "updated_records": updated_count}),
        records_affected=updated_count,
    ))
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
    api_key: ApiKey = Depends(_key_deps("consent")),
    db: Session = Depends(get_db),
):
    """Backward-compatible endpoint. Clients should migrate to /api/v1/consent/signal."""
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</api/v1/consent/signal>; rel="successor-version"'
    return api_consent_signal(payload=payload, api_key=api_key, db=db)


@router.get("/records/status")
def api_record_status(
    record_reference: str,
    category_id: Optional[int] = None,
    api_key: ApiKey = Depends(_key_deps("read")),
    db: Session = Depends(get_db),
):
    org_id = api_key.organization_id

    query = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.record_reference == record_reference
    )
    if category_id:
        query = query.filter(DataRecord.category_id == category_id)

    record = query.first()
    _log_call(db, api_key, "/api/v1/records/status", 200 if record else 404, 0, method="GET")
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
    external_ref: str = Field(..., max_length=MAX_REF_LEN)

class TerminateRequest(BaseModel):
    external_ref: str = Field(..., max_length=MAX_REF_LEN)
    termination_date: Optional[str] = Field(None, max_length=10)

@router.get("/categories")
def api_list_categories(
    api_key: ApiKey = Depends(_key_deps("read")),
    db: Session = Depends(get_db),
):
    org_id = api_key.organization_id

    categories = db.query(DataCategory).filter(
        DataCategory.organization_id == org_id,
        DataCategory.deleted_at == None,
        DataCategory.is_active == True
    ).order_by(DataCategory.name).all()
    _log_call(db, api_key, "/api/v1/categories", 200, 0, method="GET")

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
    api_key: ApiKey = Depends(_key_deps("dispose")),
    db: Session = Depends(get_db),
):
    """
    Confirm external disposal of records by reference.

    Governance rules enforced:
      - Disposal freeze: rejected while the emergency freeze is active.
      - Dual approval: sensitive (dual-approval) categories can NOT be disposed
        via API; a 409 instructs the caller to use the two-officer workflow.
      - Legal hold: held records are always skipped.
    """
    org_id = api_key.organization_id

    # Emergency disposal freeze applies to API-driven disposal too
    if is_disposal_frozen(db, org_id):
        raise HTTPException(
            status_code=423,
            detail="Disposal is frozen organisation-wide (litigation/audit hold). Request rejected."
        )

    # Find matching records
    records = db.query(DataRecord).filter(
        DataRecord.record_reference == payload.external_ref,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None
    ).all()

    if not records:
        raise HTTPException(status_code=404, detail="No active record matched this reference.")

    # Dual-approval categories must never be disposed through a single API call
    dual_records = [r for r in records if needs_dual_approval(db, r)]
    if dual_records:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{len(dual_records)} matched record(s) belong to dual-approval categories and "
                "cannot be disposed via API. Use the two-officer approval workflow in SafeData."
            )
        )

    disposed_count = 0
    skipped_held = 0
    for r in records:
        if r.status == "disposed":
            continue
        if r.legal_hold:
            skipped_held += 1
            continue
        if execute_disposal(db, r.id, actor_id=None, ip_address="API"):
            disposed_count += 1

    _log_call(db, api_key, "/api/v1/records/disposed", 200, disposed_count)
    return {
        "status": "processed",
        "external_ref": payload.external_ref,
        "matched_count": len(records),
        "disposed_count": disposed_count,
        "skipped_legal_hold": skipped_held
    }

@router.post("/records/terminate")
def api_records_terminate(
    payload: TerminateRequest,
    api_key: ApiKey = Depends(_key_deps("terminate")),
    db: Session = Depends(get_db),
):
    """The relationship (or the event the data was collected for) has ended: start the clock.

    Applies to records in "account_closure" categories whose clock has not started.
    Calling it again for the same reference changes nothing (the first date stands).
    """
    org_id = api_key.organization_id

    try:
        term_date = (_parse_business_date(payload.termination_date, "termination_date")
                     if payload.termination_date else business_today())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if term_date > business_today() + timedelta(days=366):
        raise HTTPException(status_code=422, detail="termination_date is more than a year ahead.")

    same_ref = db.query(DataRecord).filter(
        DataRecord.record_reference == payload.external_ref,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None,  # noqa: E711
        DataRecord.status != "disposed",
    ).all()
    if not same_ref:
        _log_call(db, api_key, "/api/v1/records/terminate", 404, 0, payload.model_dump_json())
        raise HTTPException(status_code=404, detail="No active record matched this reference.")

    updated_records = []
    already = 0
    for r in same_ref:
        trigger = effective_policy(db, r)[1]
        if trigger != "account_closure":
            continue
        if r.relationship_ended_on is not None:
            already += 1
            continue
        r.relationship_ended_on = term_date
        calculate_retention_end_date(db, r)
        rend = r.retention_end_date
        db.commit()

        log_audit(db, org_id, "account_terminated", "data_record", r.id, None, {
            "source": "enterprise_api",
            "external_ref": payload.external_ref,
            "termination_date": term_date.isoformat(),
            "retention_end_date": rend.strftime("%Y-%m-%d") if rend else None,
        }, "API")

        updated_records.append({
            "record_id": r.id,
            "category": r.category.name,
            "retention_end_date": rend.strftime("%Y-%m-%d") if rend else None,
        })

    _log_call(db, api_key, "/api/v1/records/terminate", 200, len(updated_records), payload.model_dump_json())
    return {
        "status": "processed",
        "external_ref": payload.external_ref,
        "matched_count": len(updated_records),
        "already_terminated": already,
        "updated_records": updated_records
    }


# ═══════════════════════════════════════════════════════════════════════════
#   A1: Real-time Dashboard Metrics JSON endpoint
#   (router is mounted at /api/v1 — do NOT repeat the prefix here)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/dashboard/metrics")
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
    api_key = authenticate_api_key(db, authorization, x_api_key, required_permission="read", request=request)
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

@router.get("/disposal/analytics")
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
    from sqlalchemy import func

    api_key = authenticate_api_key(db, authorization, x_api_key, required_permission="read", request=request)
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

@router.get("/audit/verify")
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
    api_key = authenticate_api_key(db, authorization, x_api_key, required_permission="read", request=request)
    org_id = api_key.organization_id

    result = verify_audit_chain(db, org_id=org_id)

    return {
        "organization_id": org_id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "chain_intact": result["ok"],
        "logs_verified": result.get("verified_count", 0),
        "first_broken_at": result.get("first_broken_log_id", None),
    }
