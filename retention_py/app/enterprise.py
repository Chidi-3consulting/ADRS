"""
SafeData Enterprise Engine

Provides: API-key lifecycle (E1, SHA-256 hashed), auto-categorisation (E5 first-match-
by-priority), async intake queue processing (E2), inbound consent signal matching (E4),
outbound disposal dispatch queueing + sending (E3), and enterprise daily engine steps.

Tier gating: callers must verify get_setting(db,'SafeData_tier')==='enterprise' first.
"""
import json
import hashlib
import secrets
from datetime import datetime, date, timedelta

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ApiKey, ConnectedSystem, AutoCategorizationRule, IntakeQueue,
    DataRecord, DataCategory, ConsentSignal, DisposalDispatch,
    IntegrationLog, Organization,
)
from app.helpers import log_audit


# ---------------------------------------------------------------------------
#   Helper: settings reader
# ---------------------------------------------------------------------------

def _get_setting(db: Session, key: str, default: str = "", org_id: int = None) -> str:
    from app.models import OrganizationSetting, SystemSetting
    if org_id:
        row = db.query(OrganizationSetting).filter(
            OrganizationSetting.organization_id == org_id,
            OrganizationSetting.setting_key == key,
        ).first()
        if row:
            return row.setting_value
    row = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    return row.setting_value if row else default


def _set_setting(db: Session, key: str, value: str, org_id: int = None):
    from app.models import OrganizationSetting, SystemSetting
    if org_id:
        row = db.query(OrganizationSetting).filter(
            OrganizationSetting.organization_id == org_id,
            OrganizationSetting.setting_key == key,
        ).first()
        if row:
            row.setting_value = value
        else:
            db.add(OrganizationSetting(organization_id=org_id, setting_key=key, setting_value=value))
    else:
        row = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
        if row:
            row.setting_value = value
        else:
            db.add(SystemSetting(setting_key=key, setting_value=value))
    db.commit()


# ---------------------------------------------------------------------------
#   API Keys (E1)
# ---------------------------------------------------------------------------

def generate_api_key() -> dict:
    """Generate a raw key + its SHA-256 hash + display prefix. Raw shown once only."""
    raw = "SafeData_" + secrets.token_hex(24)  # 53 chars, unguessable
    return {"raw": raw, "hash": hashlib.sha256(raw.encode()).hexdigest(), "prefix": raw[:12]}


def create_api_key(db: Session, system_id: int, name: str, permissions: list,
                   rate_limit: int, actor_id: int, org_id: int = 1, expires_at=None) -> dict:
    """Create an API key for a connected system. Returns {'id': int, 'raw': str}."""
    k = generate_api_key()
    api_key = ApiKey(
        organization_id=org_id,
        system_id=system_id,
        key_name=name,
        key_hash=k["hash"],
        key_prefix=k["prefix"],
        permissions=json.dumps(permissions),
        rate_limit_per_min=rate_limit,
        created_by=actor_id,
        expires_at=expires_at,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    log_audit(db, org_id, "user_updated", "system", api_key.id, actor_id,
              {"api_key_created": name, "prefix": k["prefix"]}, "127.0.0.1")
    return {"id": api_key.id, "raw": k["raw"]}


def verify_api_key(db: Session, raw_key: str):
    """Verify a raw API key. Returns the key row if valid+active, else None. Updates last_used_at."""
    if not raw_key:
        return None
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True,
        ApiKey.revoked_at == None,
    ).first()
    if not api_key:
        return None
    # Check expiry
    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        return None
    # Check system is active
    system = db.query(ConnectedSystem).filter(
        ConnectedSystem.id == api_key.system_id,
        ConnectedSystem.is_active == True,
    ).first()
    if not system:
        return None
    api_key.last_used_at = datetime.utcnow()
    db.commit()
    return api_key


def revoke_api_key(db: Session, key_id: int, actor_id: int):
    """Revoke an API key."""
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if api_key:
        api_key.is_active = False
        api_key.revoked_at = datetime.utcnow()
        db.commit()
        log_audit(db, api_key.organization_id, "user_updated", "system", key_id,
                  actor_id, {"api_key_revoked": key_id}, "127.0.0.1")


def api_key_can(api_key, permission: str) -> bool:
    """True if the key has the given permission (empty = allow all)."""
    try:
        perms = json.loads(api_key.permissions) if isinstance(api_key.permissions, str) else (api_key.permissions or [])
    except (json.JSONDecodeError, TypeError):
        perms = []
    return perms == [] or permission in perms


def within_rate_limit(db: Session, api_key_id: int, limit_per_min: int) -> bool:
    """Rate-limit gate: True if under the limit (counted from inbound integration_logs)."""
    cutoff = datetime.utcnow() - timedelta(minutes=1)
    count = db.query(func.count(IntegrationLog.id)).filter(
        IntegrationLog.api_key_id == api_key_id,
        IntegrationLog.direction == "inbound",
        IntegrationLog.created_at >= cutoff,
    ).scalar() or 0
    return count < limit_per_min


def log_integration(db: Session, system_id, api_key_id, direction: str,
                    endpoint: str, method: str, status_code: int,
                    req_body=None, res_body=None, records_affected: int = 0,
                    duration_ms: int = 0, ip_address: str = None, error: str = None,
                    org_id: int = 1):
    """Append an integration_logs row. Never throws."""
    try:
        log = IntegrationLog(
            organization_id=org_id,
            system_id=system_id,
            api_key_id=api_key_id,
            direction=direction,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            request_body=json.dumps(req_body) if req_body else None,
            response_body=json.dumps(res_body) if res_body else None,
            records_affected=records_affected,
            duration_ms=duration_ms,
            ip_address=ip_address,
            error_message=error,
        )
        db.add(log)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
#   Auto-Categorisation (E5) — first active matching rule by priority wins
# ---------------------------------------------------------------------------

def auto_categorize(db: Session, system_id: int, object_type: str, metadata: dict = None) -> int:
    """Resolve a category for an inbound object using auto_categorization_rules. Returns category_id or None."""
    metadata = metadata or {}
    rules = db.query(AutoCategorizationRule).filter(
        AutoCategorizationRule.system_id == system_id,
        AutoCategorizationRule.is_active == True,
        AutoCategorizationRule.object_type == object_type,
    ).order_by(AutoCategorizationRule.priority.asc(), AutoCategorizationRule.id.asc()).all()

    for rule in rules:
        if not rule.condition_field or rule.condition_field == "":
            return rule.category_id
        val = metadata.get(rule.condition_field)
        if val is not None and str(val) == str(rule.condition_value):
            return rule.category_id
    return None


# ---------------------------------------------------------------------------
#   Intake Queue (E2) — process pending inbound records
# ---------------------------------------------------------------------------

def enqueue_intake(db: Session, system_id: int, api_key_id: int, batch_id: str,
                   payload: dict, org_id: int = 1) -> int:
    """Insert a record into the intake queue. Returns queue id."""
    item = IntakeQueue(
        organization_id=org_id,
        system_id=system_id,
        api_key_id=api_key_id,
        batch_id=batch_id,
        payload=json.dumps(payload),
        status="pending",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item.id


def intake_is_duplicate(db: Session, external_ref: str, category_id: int) -> bool:
    """True if a non-deleted record already exists with this reference in this category."""
    return db.query(DataRecord).filter(
        DataRecord.record_reference == external_ref,
        DataRecord.category_id == category_id,
        DataRecord.deleted_at == None,
    ).first() is not None


def _compute_retention_end(category, collection_date_str: str):
    """Compute retention_end_date from a category and collection date."""
    from datetime import date as _date
    if isinstance(collection_date_str, str):
        try:
            cd = _date.fromisoformat(collection_date_str)
        except ValueError:
            cd = _date.today()
    else:
        cd = collection_date_str or _date.today()

    days = category.retention_period_days or 0
    if days > 0:
        return cd + timedelta(days=days)
    return None


def process_intake_item(db: Session, item) -> dict:
    """
    Process a single intake_queue row: auto-categorise, create the data_record, link them.
    Returns {'status': 'completed'|'failed'|'duplicate', 'record_id': int|None, 'error': str|None}.
    """
    try:
        payload = json.loads(item.payload) if isinstance(item.payload, str) else (item.payload or {})
    except (json.JSONDecodeError, TypeError):
        payload = {}

    object_type = payload.get("object_type", "")
    external_ref = payload.get("external_ref", "")
    metadata = payload.get("metadata", {})

    try:
        if not object_type or not external_ref:
            raise RuntimeError("object_type and external_ref are required")

        category_id = payload.get("category_id") or auto_categorize(db, item.system_id, object_type, metadata)
        if not category_id:
            item.status = "failed"
            item.error = "no_matching_rule"
            item.attempts = (item.attempts or 0) + 1
            item.processed_at = datetime.utcnow()
            db.commit()
            return {"status": "failed", "record_id": None, "error": "no_matching_rule"}

        if intake_is_duplicate(db, external_ref, int(category_id)):
            item.status = "duplicate"
            item.category_id = category_id
            item.processed_at = datetime.utcnow()
            db.commit()
            return {"status": "duplicate", "record_id": None, "error": None}

        category = db.query(DataCategory).filter(DataCategory.id == int(category_id)).first()
        collection_date = payload.get("collection_date") or date.today().isoformat()
        retention_end = _compute_retention_end(category, collection_date)

        org_id = category.organization_id if category else (item.organization_id or 1)
        record = DataRecord(
            organization_id=org_id,
            category_id=int(category_id),
            record_reference=external_ref,
            data_subject_type=payload.get("data_subject_type"),
            collection_date=date.fromisoformat(collection_date) if isinstance(collection_date, str) else collection_date,
            retention_end_date=retention_end,
            status="active",
            notes=f"Captured via Enterprise API from system #{item.system_id}",
        )
        if category:
            from app.engine import calculate_retention_end_date
            record.category = category
            calculate_retention_end_date(db, record)
        db.add(record)
        db.commit()
        db.refresh(record)

        item.status = "completed"
        item.category_id = category_id
        item.record_id = record.id
        item.processed_at = datetime.utcnow()
        db.commit()

        # Update sync count
        system = db.query(ConnectedSystem).filter(ConnectedSystem.id == item.system_id).first()
        if system:
            system.records_synced = (system.records_synced or 0) + 1
            db.commit()

        log_audit(db, org_id, "record_created", "data_record", record.id, None,
                  {"source": "enterprise_api", "external_ref": external_ref}, None)

        return {"status": "completed", "record_id": record.id, "error": None}

    except Exception as e:
        item.status = "failed"
        item.error = str(e)[:500]
        item.attempts = (item.attempts or 0) + 1
        item.processed_at = datetime.utcnow()
        try:
            db.commit()
        except Exception:
            db.rollback()
        return {"status": "failed", "record_id": None, "error": str(e)}


def process_intake_queue(db: Session, limit: int = 100) -> dict:
    """Process up to `limit` pending intake rows. Returns counts."""
    rows = db.query(IntakeQueue).filter(
        IntakeQueue.status == "pending",
        IntakeQueue.attempts < 3,
    ).order_by(IntakeQueue.id.asc()).limit(limit).all()

    r = {"processed": 0, "created": 0, "failed": 0, "duplicate": 0}
    for item in rows:
        res = process_intake_item(db, item)
        r["processed"] += 1
        if res["status"] == "completed":
            r["created"] += 1
        elif res["status"] == "duplicate":
            r["duplicate"] += 1
        else:
            r["failed"] += 1
    return r


# ---------------------------------------------------------------------------
#   Consent Signals (E4) — inbound consent signal matching
# ---------------------------------------------------------------------------

def record_consent_signal(db: Session, system_id: int, external_ref: str,
                          signal_type: str, payload: dict = None, org_id: int = 1) -> dict:
    """Record an inbound consent signal and attempt to match it to a record."""
    signal = ConsentSignal(
        organization_id=org_id,
        system_id=system_id,
        external_ref=external_ref,
        signal_type=signal_type,
        raw_payload=json.dumps(payload or {}),
        status="pending",
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    matched = match_consent_signal(db, signal.id)
    return {"signal_id": signal.id, "matched": matched["matched"], "record_id": matched["record_id"]}


def match_consent_signal(db: Session, signal_id: int) -> dict:
    """Try to match a pending/unmatched consent signal to a record."""
    signal = db.query(ConsentSignal).filter(ConsentSignal.id == signal_id).first()
    if not signal or signal.status == "processed":
        return {"matched": False, "record_id": None}

    record = db.query(DataRecord).join(DataCategory, DataRecord.category_id == DataCategory.id).filter(
        DataRecord.record_reference == signal.external_ref,
        DataCategory.disposal_trigger == "consent_withdrawal",
        DataRecord.deleted_at == None,
        DataRecord.status != "disposed",
    ).first()

    if not record:
        signal.status = "unmatched"
        db.commit()
        return {"matched": False, "record_id": None}

    from app.engine import calculate_retention_end_date
    record.consent_withdrawn_at = datetime.utcnow()
    calculate_retention_end_date(db, record)
    signal.status = "processed"
    signal.record_id = record.id
    signal.processed_at = datetime.utcnow()
    db.commit()

    log_audit(db, record.organization_id, "consent_withdrawn", "data_record",
              record.id, None, {"source": "enterprise_signal", "external_ref": signal.external_ref}, None)
    return {"matched": True, "record_id": record.id}


def retry_unmatched_consent_signals(db: Session) -> int:
    """Retry all unmatched consent signals from the last 7 days. Returns count newly matched."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    signals = db.query(ConsentSignal).filter(
        ConsentSignal.status == "unmatched",
        ConsentSignal.created_at >= cutoff,
    ).all()
    matched = 0
    for sig in signals:
        if match_consent_signal(db, sig.id)["matched"]:
            matched += 1
    return matched


# ---------------------------------------------------------------------------
#   Outbound Disposal Dispatch (E3) — queue + send
# ---------------------------------------------------------------------------

def queue_disposal_dispatch(db: Session, record_id: int, method: str, org_id: int = 1) -> int:
    """Queue outbound disposal instructions for a record to every connected system. Returns count."""
    record = db.query(DataRecord).filter(DataRecord.id == record_id).first()
    if not record:
        return 0

    systems = db.query(IntakeQueue.system_id, ConnectedSystem.base_url).join(
        ConnectedSystem, ConnectedSystem.id == IntakeQueue.system_id
    ).filter(
        IntakeQueue.record_id == record_id,
        ConnectedSystem.is_active == True,
    ).distinct().all()

    n = 0
    for system_id, base_url in systems:
        endpoint = f"{base_url.rstrip('/')}/SafeData/disposal" if base_url else None
        dispatch = DisposalDispatch(
            organization_id=org_id,
            record_id=record_id,
            system_id=system_id,
            dispatch_type=method,
            external_ref=record.record_reference,
            endpoint_url=endpoint,
            payload=json.dumps({
                "action": method,
                "record_reference": record.record_reference,
                "external_ref": record.record_reference
            }),
            status="pending",
        )
        db.add(dispatch)
        n += 1
    if n > 0:
        db.commit()
    return n


def process_disposal_dispatches(db: Session, limit: int = 50) -> dict:
    """Send pending disposal dispatches via webhook POST. Returns {'sent': int, 'failed': int}."""
    retry_limit = int(_get_setting(db, "webhook_retry_limit", "3"))
    rows = db.query(DisposalDispatch).filter(
        DisposalDispatch.status == "pending",
        DisposalDispatch.attempts < retry_limit,
    ).order_by(DisposalDispatch.id.asc()).limit(limit).all()

    sent = 0
    failed = 0
    for d in rows:
        if not d.endpoint_url:
            # No webhook configured — mark confirmed (internal-only disposal)
            d.status = "confirmed"
            d.confirmed_at = datetime.utcnow()
            db.commit()
            sent += 1
            continue

        try:
            payload = json.loads(d.payload) if isinstance(d.payload, str) else (d.payload or {})
            headers = {"Content-Type": "application/json"}

            # HMAC signing if signing_secret is configured
            system = db.query(ConnectedSystem).filter(ConnectedSystem.id == d.system_id).first()
            if system and system.signing_secret:
                import hmac as _hmac
                sig = _hmac.new(
                    system.signing_secret.encode(), d.payload.encode(), hashlib.sha256
                ).hexdigest()
                headers["X-SafeData-Signature"] = sig

            resp = httpx.post(d.endpoint_url, json=payload, headers=headers, timeout=20.0, follow_redirects=True)
            code = resp.status_code

            if 200 <= code < 300:
                d.status = "confirmed"
                d.response_code = code
                d.response_body = resp.text[:2000]
                d.sent_at = datetime.utcnow()
                d.confirmed_at = datetime.utcnow()
                d.attempts = (d.attempts or 0) + 1
                log_integration(db, d.system_id, None, "outbound", "/SafeData/disposal",
                                "POST", code, None, None, 1, org_id=d.organization_id)
                sent += 1
            else:
                d.attempts = (d.attempts or 0) + 1
                d.status = "failed" if d.attempts >= retry_limit else "pending"
                d.response_code = code
                d.response_body = resp.text[:2000]
                d.sent_at = datetime.utcnow()
                failed += 1
                if d.status == "failed":
                    from app.engine import notify_role
                    sys_name = system.name if system else "Connected System"
                    notify_role(
                        db, d.organization_id, ["admin", "dpo"], "webhook_failure",
                        "Disposal Webhook Delivery Failure",
                        f"Outbound disposal webhook for record #{d.record_id} ({d.external_ref}) to '{sys_name}' has failed after {d.attempts} attempts.",
                        related_record_id=d.record_id
                    )
                    log_audit(db, d.organization_id, "disposal_dispatch_failed", "data_record", d.record_id, None, {
                        "system": sys_name,
                        "endpoint": d.endpoint_url,
                        "attempts": d.attempts,
                        "response_code": code
                    }, "127.0.0.1")
        except Exception as e:
            d.attempts = (d.attempts or 0) + 1
            d.status = "failed" if d.attempts >= retry_limit else "pending"
            d.response_body = str(e)[:2000]
            d.sent_at = datetime.utcnow()
            failed += 1
            if d.status == "failed":
                from app.engine import notify_role
                system = db.query(ConnectedSystem).filter(ConnectedSystem.id == d.system_id).first()
                sys_name = system.name if system else "Connected System"
                notify_role(
                    db, d.organization_id, ["admin", "dpo"], "webhook_failure",
                    "Disposal Webhook Delivery Failure",
                    f"Outbound disposal webhook for record #{d.record_id} ({d.external_ref}) to '{sys_name}' encountered an exception after {d.attempts} attempts: {str(e)[:150]}",
                    related_record_id=d.record_id
                )
                log_audit(db, d.organization_id, "disposal_dispatch_failed", "data_record", d.record_id, None, {
                    "system": sys_name,
                    "endpoint": d.endpoint_url,
                    "attempts": d.attempts,
                    "error": str(e)[:200]
                }, "127.0.0.1")

        db.commit()

    return {"sent": sent, "failed": failed}


# ---------------------------------------------------------------------------
#   Enterprise Daily Engine Steps (A/B/C)
# ---------------------------------------------------------------------------

def purge_integration_logs(db: Session) -> int:
    """Step C: purge integration_logs older than api_log_retention_days. Returns rows deleted."""
    days = int(_get_setting(db, "api_log_retention_days", "90"))
    cutoff = datetime.utcnow() - timedelta(days=days)
    count = db.query(IntegrationLog).filter(IntegrationLog.created_at < cutoff).delete()
    db.commit()
    return count


def run_enterprise_engine_steps(db: Session) -> dict:
    """
    Run the Enterprise additions to the daily engine:
      A — process any pending intake queue items
      B — retry unmatched consent signals from the last 7 days
      C — purge old integration logs
    Returns a summary. No-op-safe.
    """
    intake = process_intake_queue(db, 100) if _get_setting(db, "intake_queue_enabled", "1") == "1" else {"created": 0}
    consent_retried = retry_unmatched_consent_signals(db) if _get_setting(db, "consent_signal_enabled", "1") == "1" else 0
    purged = purge_integration_logs(db)
    return {
        "intake_created": intake.get("created", 0),
        "consent_retried": consent_retried,
        "logs_purged": purged,
    }
