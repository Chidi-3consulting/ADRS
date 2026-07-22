import hmac
import hashlib
import json
import httpx
from datetime import datetime, date, timedelta
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import Session
from app.models import (
    DataRecord, DataCategory, CategoryRetentionRule, AuditLog,
    Notification, User, ConnectedSystem, DisposalDispatch,
    WebhookEndpoint, SystemSetting, OrganizationSetting
)
from app.helpers import log_audit

def get_setting(db: Session, key: str, default: str = "") -> str:
    # Check system setting
    s = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    return s.setting_value if s else default

def calculate_retention_end_date(db: Session, record: DataRecord):
    # Fetch effective values (category defaults vs rule overrides)
    cat = db.query(DataCategory).filter(DataCategory.id == record.category_id).first()
    if not cat:
        return

    rule = None
    if record.retention_rule_id:
        rule = db.query(CategoryRetentionRule).filter(CategoryRetentionRule.id == record.retention_rule_id).first()

    trigger = rule.disposal_trigger if (rule and rule.disposal_trigger) else cat.disposal_trigger
    days = rule.retention_period_days if (rule and rule.retention_period_days is not None) else cat.retention_period_days

    if trigger == "date_based":
        # Calculate from collection_date
        if record.collection_date:
            record.retention_end_date = record.collection_date + timedelta(days=days)
    else:
        # consent_withdrawal or account_closure: retention clock starts on signal withdrawal date
        if record.consent_withdrawn_at:
            record.retention_end_date = record.consent_withdrawn_at.date() + timedelta(days=days)
        else:
            record.retention_end_date = None

def queue_disposal_dispatch(db: Session, record_id: int, method: str):
    # E3: check if record is synced from connected systems
    record = db.query(DataRecord).filter(DataRecord.id == record_id).first()
    if not record:
        return

    # Find connected systems
    systems = db.query(ConnectedSystem).filter(
        ConnectedSystem.organization_id == record.organization_id,
        ConnectedSystem.is_active == True
    ).all()

    for sys in systems:
        # Create dispatch entry
        dispatch = DisposalDispatch(
            organization_id=record.organization_id,
            record_id=record.id,
            system_id=sys.id,
            dispatch_type=method,
            external_ref=record.record_reference,
            endpoint_url=sys.base_url,
            status="pending",
            payload={"record_reference": record.record_reference, "action": method}
        )
        db.add(dispatch)
    db.commit()

def execute_disposal(db: Session, record_id: int, actor_id: int = None, ip_address: str = "127.0.0.1") -> bool:
    record = db.query(DataRecord).filter(DataRecord.id == record_id).first()
    if not record or record.status == "disposed" or record.legal_hold:
        return False

    cat = db.query(DataCategory).filter(DataCategory.id == record.category_id).first()
    rule = db.query(CategoryRetentionRule).filter(CategoryRetentionRule.id == record.retention_rule_id).first() if record.retention_rule_id else None

    method = rule.disposal_method if (rule and rule.disposal_method) else cat.disposal_method

    if method == "anonymise":
        record.status = "disposed"
        record.disposed_at = datetime.utcnow()
        record.disposed_by = actor_id
        record.record_reference = f"ANONYMISED-{record.id}"
        record.data_subject_type = None
        record.notes = "Data record anonymised in accordance with compliance."
    elif method == "delete":
        record.status = "disposed"
        record.disposed_at = datetime.utcnow()
        record.disposed_by = actor_id
        record.deleted_at = datetime.utcnow()
    else:  # archive
        record.status = "disposed"
        record.disposed_at = datetime.utcnow()
        record.disposed_by = actor_id
        record.notes = f"Record archived. Method: {method}"

    db.commit()

    log_audit(db, record.organization_id, f"record_disposed_{method}", "data_record", record.id, actor_id, {"method": method}, ip_address)

    # Outbound webhook queuing
    if get_setting(db, "adrs_tier", "core") == "enterprise":
        queue_disposal_dispatch(db, record.id, method)

    return True

def run_retention_checks(db: Session, org_id: int) -> dict:
    results = {"flagged": 0, "disposed": 0, "skipped_dual": 0, "escalated": 0}

    # Settings
    review_alert_days = int(get_setting(db, "review_alert_days", "30"))
    escalation_days = int(get_setting(db, "escalation_days", "14"))
    consent_disposal_days = int(get_setting(db, "consent_disposal_days", "30"))

    today = date.today()

    # Step 1: Flag date_based active records approaching retention end date
    flag_threshold = today + timedelta(days=review_alert_days)
    records_to_flag = db.query(DataRecord).join(DataCategory, DataRecord.category_id == DataCategory.id).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "active",
        DataRecord.legal_hold == False,
        DataRecord.deleted_at == None,
        DataRecord.retention_end_date != None,
        DataRecord.retention_end_date <= flag_threshold
    ).all()

    for r in records_to_flag:
        cat = r.category
        rule = db.query(CategoryRetentionRule).filter(CategoryRetentionRule.id == r.retention_rule_id).first() if r.retention_rule_id else None
        trigger = rule.disposal_trigger if (rule and rule.disposal_trigger) else cat.disposal_trigger
        
        if trigger == "date_based":
            r.status = "due_review"
            r.review_flagged_at = datetime.utcnow()
            results["flagged"] += 1

    if results["flagged"] > 0:
        db.commit()
        log_audit(db, org_id, "record_flagged_review", "data_record", None, None, {"count": results["flagged"]}, None)

    # Step 2: Auto dispose consent withdrawal records after delay
    consent_threshold = datetime.utcnow() - timedelta(days=consent_disposal_days)
    consent_records = db.query(DataRecord).join(DataCategory, DataRecord.category_id == DataCategory.id).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status != "disposed",
        DataRecord.legal_hold == False,
        DataRecord.deleted_at == None,
        DataRecord.consent_withdrawn_at != None,
        DataRecord.consent_withdrawn_at <= consent_threshold
    ).all()

    for r in consent_records:
        cat = r.category
        rule = db.query(CategoryRetentionRule).filter(CategoryRetentionRule.id == r.retention_rule_id).first() if r.retention_rule_id else None
        trigger = rule.disposal_trigger if (rule and rule.disposal_trigger) else cat.disposal_trigger

        if trigger == "consent_withdrawal":
            if execute_disposal(db, r.id):
                results["disposed"] += 1

    # Step 3: Auto-dispose date-based overdue records (Skipping Dual Approval)
    overdue_records = db.query(DataRecord).join(DataCategory, DataRecord.category_id == DataCategory.id).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "due_review",
        DataRecord.legal_hold == False,
        DataRecord.deleted_at == None,
        DataRecord.retention_end_date != None,
        DataRecord.retention_end_date < today
    ).all()

    for r in overdue_records:
        cat = r.category
        rule = db.query(CategoryRetentionRule).filter(CategoryRetentionRule.id == r.retention_rule_id).first() if r.retention_rule_id else None
        
        trigger = rule.disposal_trigger if (rule and rule.disposal_trigger) else cat.disposal_trigger
        requires_dual = rule.requires_dual_approval if (rule and rule.requires_dual_approval is not None) else cat.requires_dual_approval

        if trigger == "date_based":
            if requires_dual:
                results["skipped_dual"] += 1
                continue
            if execute_disposal(db, r.id):
                results["disposed"] += 1

    if results["skipped_dual"] > 0:
        log_audit(db, org_id, "record_flagged_review", "data_record", None, None, {"dual_approval_skipped": results["skipped_dual"]}, None)

    # Step 4: Escalation
    esc_threshold = datetime.utcnow() - timedelta(days=escalation_days)
    esc_records = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "due_review",
        DataRecord.legal_hold == False,
        DataRecord.deleted_at == None,
        DataRecord.escalation_sent_at == None,
        DataRecord.review_flagged_at != None,
        DataRecord.review_flagged_at <= esc_threshold
    ).all()

    if esc_records:
        for r in esc_records:
            r.escalation_sent_at = datetime.utcnow()
            results["escalated"] += 1
        
        # Notify admins
        admins = db.query(User).filter(User.organization_id == org_id, User.role == "admin").all()
        for admin in admins:
            notif = Notification(
                organization_id=org_id,
                recipient_id=admin.id,
                type="escalation_alert",
                subject=f"🚨 ESCALATION: {len(esc_records)} record(s) overdue",
                message=f"{len(esc_records)} data records have remained unreviewed past the deadline.",
                status="sent",
                sent_at=datetime.utcnow()
            )
            db.add(notif)
        db.commit()
        log_audit(db, org_id, "escalation_sent", "data_record", None, None, {"count": len(esc_records)}, None)

    # Step 5: Notify Category Owners falls back to DPO
    unnotified_due = db.query(DataRecord).join(DataCategory, DataRecord.category_id == DataCategory.id).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "due_review",
        DataRecord.deleted_at == None
    ).all()

    by_owner = {}
    for r in unnotified_due:
        owner_id = r.category.owner_id or 0
        by_owner.setdefault(owner_id, []).append(r)

    dpos = db.query(User).filter(User.organization_id == org_id, User.role == "dpo").all()
    for owner_id, recs in by_owner.items():
        targets = [db.query(User).filter(User.id == owner_id).first()] if owner_id else dpos
        for target in targets:
            if target:
                notif = Notification(
                    organization_id=org_id,
                    recipient_id=target.id,
                    type="review_due",
                    subject=f"{len(recs)} record(s) due for review",
                    message=f"You have {len(recs)} records awaiting compliance verification.",
                    status="sent",
                    sent_at=datetime.utcnow()
                )
                db.add(notif)
    db.commit()

    return results

async def dispatch_ops_webhook(db: Session, org_id: int, event_type: str, payload: dict):
    # E5: outbound webhook notifications
    if get_setting(db, "ops_webhooks_enabled", "0") != "1":
        return

    endpoints = db.query(WebhookEndpoint).filter(
        WebhookEndpoint.organization_id == org_id,
        WebhookEndpoint.is_active == True
    ).all()

    async with httpx.AsyncClient() as client:
        for ep in endpoints:
            if ep.event_types == "*" or event_type in ep.event_types.split(","):
                # Sign payload using HMAC-SHA256
                secret = "adrs_shared_ops_secret_key"
                signature = hmac.new(
                    secret.encode("utf-8"),
                    json.dumps(payload).encode("utf-8"),
                    hashlib.sha256
                ).hexdigest()

                try:
                    await client.post(
                        ep.url,
                        json=payload,
                        headers={
                            "X-ADRS-Signature": signature,
                            "X-ADRS-Event": event_type
                        },
                        timeout=5.0
                    )
                    ep.last_fired_at = datetime.utcnow()
                    db.commit()
                except Exception:
                    pass
