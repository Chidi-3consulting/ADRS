"""
ADRS Retention Engine

Provides: the full daily retention engine (flag reviews, consent disposal,
auto-dispose with B5 dual-approval safeguard, escalation, notifications,
follow-ups), housekeeping, quarterly review, audit chain verification,
and outbound webhook dispatch.
"""
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
    WebhookEndpoint, SystemSetting, OrganizationSetting,
    LoginAttempt, PasswordReset,
)
from app.helpers import log_audit


# ── Settings Helper ──

def get_setting(db: Session, key: str, default: str = "") -> str:
    """Read a system setting. For org-scoped settings, use get_org_setting()."""
    s = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    return s.setting_value if s else default


def get_org_setting(db: Session, org_id: int, key: str, default: str = "") -> str:
    """
    Read a setting: check organization_settings first, fall back to
    system_settings, then to the provided default. 
    with org/platform split.
    """
    row = db.query(OrganizationSetting).filter(
        OrganizationSetting.organization_id == org_id,
        OrganizationSetting.setting_key == key,
    ).first()
    if row:
        return row.setting_value
    # Fall back to system setting
    sys_row = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    return sys_row.setting_value if sys_row else default


# ── Notification Helpers  ──

def create_notification(
    db: Session, org_id: int, recipient_id: int, notif_type: str,
    subject: str, message: str, related_record_id: int = None,
    related_dsar_id: int = None, owner_missing: bool = False,
) -> int:
    """Insert a single notification row. Returns the new id."""
    notif = Notification(
        organization_id=org_id,
        recipient_id=recipient_id,
        type=notif_type,
        subject=subject,
        message=message,
        related_record_id=related_record_id,
        related_dsar_id=related_dsar_id,
        owner_missing=owner_missing,
        status="pending",
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif.id


def notify_role(
    db: Session, org_id: int, roles: list, notif_type: str,
    subject: str, message: str, related_record_id: int = None,
) -> int:
    """Notify every active user holding any of the given roles. Returns count."""
    users = db.query(User).filter(
        User.organization_id == org_id,
        User.is_active == True,
        User.deleted_at == None,
        User.role.in_(roles),
    ).all()
    count = 0
    for u in users:
        create_notification(db, org_id, u.id, notif_type, subject, message, related_record_id)
        count += 1
    return count


# ── Retention End Date Calculation ──

def calculate_retention_end_date(db: Session, record: DataRecord):
    """Fetch effective values (category defaults vs rule overrides) and set retention_end_date."""
    cat = db.query(DataCategory).filter(DataCategory.id == record.category_id).first()
    if not cat:
        return

    rule = None
    if record.retention_rule_id:
        rule = db.query(CategoryRetentionRule).filter(CategoryRetentionRule.id == record.retention_rule_id).first()

    trigger = rule.disposal_trigger if (rule and rule.disposal_trigger) else cat.disposal_trigger
    days = rule.retention_period_days if (rule and rule.retention_period_days is not None) else cat.retention_period_days

    if trigger == "date_based":
        if record.collection_date:
            record.retention_end_date = record.collection_date + timedelta(days=days)
    else:
        # consent_withdrawal or account_closure
        if record.consent_withdrawn_at:
            record.retention_end_date = record.consent_withdrawn_at.date() + timedelta(days=days)
        else:
            record.retention_end_date = None


# ── Disposal Dispatch (E3) ──

def queue_disposal_dispatch(db: Session, record_id: int, method: str):
    """E3: queue outbound disposal instructions to connected systems."""
    record = db.query(DataRecord).filter(DataRecord.id == record_id).first()
    if not record:
        return

    systems = db.query(ConnectedSystem).filter(
        ConnectedSystem.organization_id == record.organization_id,
        ConnectedSystem.is_active == True,
    ).all()

    for sys in systems:
        dispatch = DisposalDispatch(
            organization_id=record.organization_id,
            record_id=record.id,
            system_id=sys.id,
            dispatch_type=method,
            external_ref=record.record_reference,
            endpoint_url=sys.base_url,
            status="pending",
            payload={"record_reference": record.record_reference, "action": method},
        )
        db.add(dispatch)
    db.commit()


# ── Execute Disposal ──

def execute_disposal(db: Session, record_id: int, actor_id: int = None, ip_address: str = "127.0.0.1") -> bool:
    """
    Execute disposal of a single record. Transactional, idempotent, legal-hold-safe.
    Uses a nested savepoint (SAVEPOINT) for atomicity and re-reads the record fresh
    to avoid race conditions — ) + FOR UPDATE pattern.
    Returns True if disposed now, False if skipped.
    """
    try:
        db.begin_nested()  # SAVEPOINT for atomic disposal

        # Re-read fresh under the savepoint (idempotency + race guard)
        try:
            record = db.query(DataRecord).filter(DataRecord.id == record_id).with_for_update().first()
        except Exception:
            # SQLite doesn't support FOR UPDATE; fall back to plain query
            record = db.query(DataRecord).filter(DataRecord.id == record_id).first()

        if not record or record.status == "disposed" or record.legal_hold:
            db.rollback()  # Release savepoint
            return False

        cat = db.query(DataCategory).filter(DataCategory.id == record.category_id).first()
        rule = db.query(CategoryRetentionRule).filter(
            CategoryRetentionRule.id == record.retention_rule_id
        ).first() if record.retention_rule_id else None

        method = rule.disposal_method if (rule and rule.disposal_method) else cat.disposal_method

        if method == "anonymise":
            record.status = "disposed"
            record.disposed_at = datetime.utcnow()
            record.disposed_by = actor_id
            record.record_reference = f"ANONYMISED-{record.id}"
            record.data_subject_type = None
            record.notes = None
        elif method == "delete":
            record.status = "disposed"
            record.disposed_at = datetime.utcnow()
            record.disposed_by = actor_id
            record.deleted_at = datetime.utcnow()
        else:  # archive
            record.status = "disposed"
            record.disposed_at = datetime.utcnow()
            record.disposed_by = actor_id

        db.commit()  # Commits the savepoint

        log_audit(db, record.organization_id, f"record_disposed_{method}", "data_record",
                  record.id, actor_id, {"method": method}, ip_address)

        # Enterprise (E3): queue outbound disposal instructions to connected systems
        if get_setting(db, "adrs_tier", "core") == "enterprise":
            queue_disposal_dispatch(db, record.id, method)

        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


# ═══════════════════════════════════════════════════════════════════════════
#   Main Retention Engine
# ═══════════════════════════════════════════════════════════════════════════

def run_retention_checks(db: Session, org_id: int) -> dict:
    """
    Orchestrate the full daily retention engine for one organisation.
    Returns a summary of counts. 
    """
    results = {
        "flagged": 0,
        "consent_disposed": 0,
        "auto_disposed": 0,
        "skipped_dual": 0,
        "escalated": 0,
        "review_notifications": 0,
        "follow_ups": 0,
    }

    # Settings
    review_alert_days = int(get_org_setting(db, org_id, "review_alert_days", "30"))
    escalation_days = int(get_org_setting(db, org_id, "escalation_days", "14"))
    consent_disposal_days = int(get_org_setting(db, org_id, "consent_disposal_days", "30"))

    today = date.today()

    # ── Step 1: Flag date_based active records approaching retention end date ──
    flag_threshold = today + timedelta(days=review_alert_days)
    records_to_flag = db.query(DataRecord).join(
        DataCategory, DataRecord.category_id == DataCategory.id
    ).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "active",
        DataRecord.legal_hold == False,
        DataRecord.deleted_at == None,
        DataRecord.retention_end_date != None,
        DataRecord.retention_end_date <= flag_threshold,
    ).all()

    for r in records_to_flag:
        cat = r.category
        rule = db.query(CategoryRetentionRule).filter(
            CategoryRetentionRule.id == r.retention_rule_id
        ).first() if r.retention_rule_id else None
        trigger = rule.disposal_trigger if (rule and rule.disposal_trigger) else cat.disposal_trigger

        if trigger == "date_based":
            r.status = "due_review"
            r.review_flagged_at = datetime.utcnow()
            results["flagged"] += 1

    if results["flagged"] > 0:
        db.commit()
        log_audit(db, org_id, "record_flagged_review", "data_record", None, None,
                  {"count": results["flagged"]}, None)

    # ── Step 2: Consent withdrawal disposal (B1) ──
    consent_threshold = datetime.utcnow() - timedelta(days=consent_disposal_days)
    consent_records = db.query(DataRecord).join(
        DataCategory, DataRecord.category_id == DataCategory.id
    ).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status != "disposed",
        DataRecord.legal_hold == False,
        DataRecord.deleted_at == None,
        DataRecord.consent_withdrawn_at != None,
        DataRecord.consent_withdrawn_at <= consent_threshold,
    ).all()

    for r in consent_records:
        cat = r.category
        rule = db.query(CategoryRetentionRule).filter(
            CategoryRetentionRule.id == r.retention_rule_id
        ).first() if r.retention_rule_id else None
        trigger = rule.disposal_trigger if (rule and rule.disposal_trigger) else cat.disposal_trigger

        if trigger == "consent_withdrawal":
            if execute_disposal(db, r.id):
                results["consent_disposed"] += 1

    # ── Step 3: Auto-dispose overdue date-based records (B5 dual-approval skip) ──
    overdue_records = db.query(DataRecord).join(
        DataCategory, DataRecord.category_id == DataCategory.id
    ).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "due_review",
        DataRecord.legal_hold == False,
        DataRecord.deleted_at == None,
        DataRecord.retention_end_date != None,
        DataRecord.retention_end_date < today,
    ).all()

    for r in overdue_records:
        cat = r.category
        rule = db.query(CategoryRetentionRule).filter(
            CategoryRetentionRule.id == r.retention_rule_id
        ).first() if r.retention_rule_id else None

        trigger = rule.disposal_trigger if (rule and rule.disposal_trigger) else cat.disposal_trigger
        requires_dual = rule.requires_dual_approval if (rule and rule.requires_dual_approval is not None) else cat.requires_dual_approval

        if trigger == "date_based":
            if requires_dual:
                results["skipped_dual"] += 1
                continue  # NEVER auto-dispose sensitive records (B5)
            if execute_disposal(db, r.id):
                results["auto_disposed"] += 1

    if results["skipped_dual"] > 0:
        log_audit(db, org_id, "record_flagged_review", "data_record", None, None,
                  {"dual_approval_skipped": results["skipped_dual"]}, None)

    # ── Step 4: Escalation (B7) ──
    esc_threshold = datetime.utcnow() - timedelta(days=escalation_days)
    esc_records = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "due_review",
        DataRecord.legal_hold == False,
        DataRecord.deleted_at == None,
        DataRecord.escalation_sent_at == None,
        DataRecord.review_flagged_at != None,
        DataRecord.review_flagged_at <= esc_threshold,
    ).all()

    if esc_records:
        for r in esc_records:
            r.escalation_sent_at = datetime.utcnow()
            results["escalated"] += 1
        db.commit()

        notify_role(db, org_id, ["admin"], "escalation_alert",
                    f"🚨 ESCALATION: {len(esc_records)} record(s) overdue for review",
                    f"{len(esc_records)} record(s) have been awaiting review beyond the escalation window.")
        log_audit(db, org_id, "escalation_sent", "data_record", None, None,
                  {"count": len(esc_records)}, None)

    # ── Step 5: Notify category owners (N1: DPO fallback) ──
    unnotified_due = db.query(DataRecord).join(
        DataCategory, DataRecord.category_id == DataCategory.id
    ).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "due_review",
        DataRecord.deleted_at == None,
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
                create_notification(db, org_id, target.id, "review_due",
                                    f"{len(recs)} record(s) due for review",
                                    f"You have {len(recs)} records awaiting compliance verification.",
                                    recs[0].id if recs else None, None,
                                    not bool(owner_id))
                results["review_notifications"] += 1

    # ── Step 6: Follow-up notifications (unread > 3 days) ──
    results["follow_ups"] = engine_send_follow_ups(db, org_id)

    return results


# ═══════════════════════════════════════════════════════════════════════════
#   Follow-Up Notifications (Step 6 — ported from legacy)
# ═══════════════════════════════════════════════════════════════════════════

def engine_send_follow_ups(db: Session, org_id: int) -> int:
    """
    Send follow-ups for unread review/escalation notifications > 3 days old.
    Creates a new notification row for each follow-up and marks the original
    with follow_up_sent_at. Uses the follow_up_sent_at column for dedup
    . Returns count sent.
    """
    try:
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        notifications = db.query(Notification).filter(
            Notification.organization_id == org_id,
            Notification.read_at == None,
            Notification.type.in_(["review_due", "escalation_alert"]),
            Notification.follow_up_sent_at == None,
            Notification.created_at <= three_days_ago,
        ).all()

        if not notifications:
            return 0

        sent = 0
        for n in notifications:
            create_notification(
                db, org_id, n.recipient_id, n.type,
                f"[Follow-up] {n.subject}",
                f"Follow-up reminder: {n.message}",
                n.related_record_id, n.related_dsar_id,
                bool(n.owner_missing),
            )
            n.follow_up_sent_at = datetime.utcnow()
            sent += 1

        if sent > 0:
            db.commit()

        return sent
    except Exception:
        return 0


# ═══════════════════════════════════════════════════════════════════════════
#   Housekeeping (prune stale data — ported from legacy)
# ═══════════════════════════════════════════════════════════════════════════

def run_housekeeping(db: Session) -> dict:
    """
    Daily housekeeping: prune rows that would otherwise grow unbounded.
    Returns counts of rows deleted. 
    """
    results = {"login_attempts": 0, "password_resets": 0, "read_notifications": 0}

    try:
        cutoff_7d = datetime.utcnow() - timedelta(days=7)
        cutoff_180d = datetime.utcnow() - timedelta(days=180)

        # Prune old login attempts (> 7 days)
        count = db.query(LoginAttempt).filter(
            LoginAttempt.created_at < cutoff_7d
        ).delete(synchronize_session=False)
        results["login_attempts"] = count

        # Prune expired password resets (> 7 days past expiry)
        count = db.query(PasswordReset).filter(
            PasswordReset.expires_at < cutoff_7d
        ).delete(synchronize_session=False)
        results["password_resets"] = count

        # Prune old read notifications (> 180 days)
        count = db.query(Notification).filter(
            Notification.read_at != None,
            Notification.created_at < cutoff_180d,
        ).delete(synchronize_session=False)
        results["read_notifications"] = count

        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    return results


# ═══════════════════════════════════════════════════════════════════════════
#   Quarterly Compliance Review (ported from legacy)
# ═══════════════════════════════════════════════════════════════════════════

def run_quarterly_review(db: Session, org_id: int) -> dict:
    """
    Quarterly review task: summarise compliance posture and notify Admins + DPOs.
    Returns the summary dict. 
    """
    from app.models import DataCategory as DC, DataRecord as DR

    total_categories = db.query(func.count(DC.id)).filter(
        DC.organization_id == org_id, DC.deleted_at == None
    ).scalar() or 0

    on_legal_hold = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id, DR.legal_hold == True, DR.deleted_at == None
    ).scalar() or 0

    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    disposed_quarter = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id, DR.status == "disposed",
        DR.disposed_at >= ninety_days_ago,
    ).scalar() or 0

    due_review = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id, DR.status == "due_review", DR.deleted_at == None
    ).scalar() or 0

    summary = {
        "total_categories": total_categories,
        "on_legal_hold": on_legal_hold,
        "disposed_quarter": disposed_quarter,
        "due_review": due_review,
    }

    msg = (
        f"Quarterly compliance review: {total_categories} categories, "
        f"{on_legal_hold} on legal hold, {disposed_quarter} disposed this quarter, "
        f"{due_review} records due for review."
    )
    notify_role(db, org_id, ["admin", "dpo"], "quarterly_review",
                "Quarterly Compliance Review", msg)
    log_audit(db, org_id, "schedule_reviewed", "system", None, None, summary, None)

    return summary


# ═══════════════════════════════════════════════════════════════════════════
#   Audit Chain Verification 
# ═══════════════════════════════════════════════════════════════════════════

def audit_norm_details(details) -> str:
    """Normalise details to a canonical, key-sorted JSON string ."""
    if details is None:
        return ""
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except (json.JSONDecodeError, TypeError):
            return details
    return json.dumps(details, sort_keys=True, ensure_ascii=False)


def verify_audit_chain(db: Session, org_id: int = None) -> dict:
    """
    Walk the audit_log hash chain and verify integrity.
    Returns {'ok': bool, 'checked': int, 'broken_at': int|None}.
    Uses legacy-compatible canonical format for hash verification.
    """
    query = db.query(AuditLog).order_by(AuditLog.id.asc())
    if org_id:
        query = query.filter(AuditLog.organization_id == org_id)

    rows = query.all()
    expected_prev = "0" * 64
    checked = 0

    for r in rows:
        # Check prev_hash link
        prev_hash = r.prev_hash or ("0" * 64)
        if prev_hash != expected_prev:
            return {"ok": False, "checked": checked, "broken_at": r.id}

        # Recompute row_hash using legacy-compatible canonical format
        details_str = audit_norm_details(r.details)
        created_at_str = r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
        payload = "|".join([
            str(r.organization_id), r.action, r.entity_type,
            str(r.entity_id) if r.entity_id is not None else "",
            str(r.performed_by) if r.performed_by is not None else "",
            details_str, str(r.ip_address or ""), prev_hash, created_at_str,
        ])
        computed = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        if r.row_hash and r.row_hash != computed:
            return {"ok": False, "checked": checked, "broken_at": r.id}

        expected_prev = r.row_hash or expected_prev
        checked += 1

    return {"ok": True, "checked": checked, "broken_at": None}



# ═══════════════════════════════════════════════════════════════════════════
#   Outbound Webhook Dispatch 
# ═══════════════════════════════════════════════════════════════════════════

def webhook_matches(event_types: str, event: str) -> bool:
    """True if an endpoint's event_types ('*' or CSV) subscribes to the event."""
    event_types = (event_types or "").strip()
    if event_types == "" or event_types == "*":
        return True
    return event in [e.strip() for e in event_types.split(",")]


def fire_ops_event(db: Session, org_id: int, event: str, payload: dict,
                   sender=None) -> int:
    """
    Fire an ops event to every active, subscribed webhook.
    Returns count fired. 
    $sender(url, payload) -> [code, body] can be injected for tests.
    """
    if get_org_setting(db, org_id, "ops_webhooks_enabled", "0") != "1":
        return 0

    endpoints = db.query(WebhookEndpoint).filter(
        WebhookEndpoint.organization_id == org_id,
        WebhookEndpoint.is_active == True,
    ).all()
    if not endpoints:
        return 0

    body = {"event": event, "timestamp": datetime.utcnow().isoformat(), "data": payload}
    fired = 0
    for ep in endpoints:
        if not webhook_matches(ep.event_types, event):
            continue
        try:
            if sender:
                sender(ep.url, body)
            else:
                httpx.post(ep.url, json=body, timeout=10.0,
                           headers={"Content-Type": "application/json"})
            ep.last_fired_at = datetime.utcnow()
            db.commit()
            fired += 1
        except Exception:
            pass  # never let a webhook break the originating action
    return fired


# ═══════════════════════════════════════════════════════════════════════════
#   Lifecycle Library 
#   Legal hold, consent withdrawal, disposal workflow with B5 dual-approval.
# ═══════════════════════════════════════════════════════════════════════════

def set_legal_hold(db: Session, org_id: int, record_id: int,
                   reason: str, actor_id: int, ip: str = None) -> bool:
    """Place a record on legal hold. Returns True if set, False if already held or not found."""
    record = db.query(DataRecord).filter(
        DataRecord.id == record_id,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None,
    ).first()
    if not record or record.legal_hold:
        return False

    record.legal_hold = True
    record.legal_hold_reason = reason
    record.legal_hold_by = actor_id
    record.legal_hold_at = datetime.utcnow()
    record.legal_hold_lifted_at = None
    db.commit()
    log_audit(db, org_id, "legal_hold_set", "data_record", record_id,
              actor_id, {"reason": reason}, ip)
    fire_ops_event(db, org_id, "legal_hold_set", {"record_id": record_id, "reason": reason})
    return True


def lift_legal_hold(db: Session, org_id: int, record_id: int,
                    actor_id: int, ip: str = None) -> bool:
    """Lift legal hold from a record. Returns True if lifted, False if not held."""
    record = db.query(DataRecord).filter(
        DataRecord.id == record_id,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None,
    ).first()
    if not record or not record.legal_hold:
        return False

    record.legal_hold = False
    record.legal_hold_lifted_at = datetime.utcnow()
    db.commit()
    log_audit(db, org_id, "legal_hold_lifted", "data_record", record_id,
              actor_id, {}, ip)
    return True


def log_consent_withdrawal(db: Session, org_id: int, record_id: int,
                           actor_id: int, ip: str = None) -> bool:
    """
    Record consent withdrawal on a record (B1). The engine will auto-dispose
    after consent_disposal_days have elapsed.
    """
    record = db.query(DataRecord).filter(
        DataRecord.id == record_id,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None,
    ).first()
    if not record:
        return False

    record.consent_withdrawn_at = datetime.utcnow()
    record.consent_withdrawn_by = actor_id
    db.commit()
    log_audit(db, org_id, "consent_withdrawn", "data_record", record_id,
              actor_id, {}, ip)
    fire_ops_event(db, org_id, "consent_withdrawn", {"record_id": record_id})
    return True


def request_disposal(db: Session, org_id: int, record_id: int,
                     actor_id: int, ip: str = None) -> dict:
    """
    Request disposal of a record. If the category requires_dual_approval (B5),
    status moves to 'disposal_requested' and a second approver must call
    approve_disposal(). Otherwise the record is disposed immediately.
    Returns {'status': 'disposed'|'pending_approval', 'record_id': int}.
    """
    record = db.query(DataRecord).filter(
        DataRecord.id == record_id,
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None,
    ).first()
    if not record or record.status == "disposed":
        return {"status": "error", "record_id": record_id}
    if record.legal_hold:
        return {"status": "legal_hold", "record_id": record_id}

    cat = db.query(DataCategory).filter(DataCategory.id == record.category_id).first()
    # Check rule override for dual approval
    rule = None
    if record.retention_rule_id:
        rule = db.query(CategoryRetentionRule).filter(
            CategoryRetentionRule.id == record.retention_rule_id
        ).first()
    needs_dual = (rule.requires_dual_approval if rule else None)
    if needs_dual is None:
        needs_dual = cat.requires_dual_approval if cat else False

    if needs_dual:
        # B5: require second approver
        record.status = "disposal_requested"
        record.disposal_requested_at = datetime.utcnow()
        record.disposal_requested_by = actor_id
        db.commit()
        log_audit(db, org_id, "disposal_requested", "data_record", record_id,
                  actor_id, {"requires_dual_approval": True}, ip)
        # Notify admins/DPOs
        notify_role(db, org_id, ["admin", "dpo"], "disposal_approval_needed",
                    f"Disposal approval needed for record #{record_id}",
                    f"Record #{record.record_reference} requires dual-approval disposal. Please review.")
        return {"status": "pending_approval", "record_id": record_id}
    else:
        # Single approval — dispose immediately
        result = execute_disposal(db, org_id, record, actor_id, ip)
        return {"status": "disposed" if result else "error", "record_id": record_id}


def approve_disposal(db: Session, org_id: int, record_id: int,
                     approver_id: int, ip: str = None) -> dict:
    """
    B5 second-approver workflow. The approver MUST be a different user than
    the requester. Disposes the record if valid.
    """
    record = db.query(DataRecord).filter(
        DataRecord.id == record_id,
        DataRecord.organization_id == org_id,
        DataRecord.status == "disposal_requested",
        DataRecord.deleted_at == None,
    ).first()
    if not record:
        return {"status": "error", "message": "Record not found or not pending approval"}
    if record.legal_hold:
        return {"status": "error", "message": "Record is on legal hold"}
    if record.disposal_requested_by == approver_id:
        return {"status": "error", "message": "Approver must be different from requester (B5)"}

    result = execute_disposal(db, org_id, record, approver_id, ip)
    if result:
        log_audit(db, org_id, "disposal_approved", "data_record", record_id,
                  approver_id, {"requested_by": record.disposal_requested_by}, ip)
    return {"status": "disposed" if result else "error", "record_id": record_id}


def reject_disposal(db: Session, org_id: int, record_id: int,
                    rejector_id: int, reason: str = "", ip: str = None) -> bool:
    """Reject a pending disposal request, reverting status to due_review."""
    record = db.query(DataRecord).filter(
        DataRecord.id == record_id,
        DataRecord.organization_id == org_id,
        DataRecord.status == "disposal_requested",
        DataRecord.deleted_at == None,
    ).first()
    if not record:
        return False

    record.status = "due_review"
    record.disposal_requested_at = None
    record.disposal_requested_by = None
    db.commit()
    log_audit(db, org_id, "disposal_rejected", "data_record", record_id,
              rejector_id, {"reason": reason}, ip)
    return True


# ═══════════════════════════════════════════════════════════════════════════
#   Analytics Library 
# ═══════════════════════════════════════════════════════════════════════════

def compliance_metrics(db: Session, org_id: int) -> dict:
    """Aggregate headline compliance metrics for the dashboard."""
    DR = DataRecord
    DC = DataCategory

    total_categories = db.query(func.count(DC.id)).filter(
        DC.organization_id == org_id, DC.deleted_at == None
    ).scalar() or 0

    total_records = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id, DR.deleted_at == None
    ).scalar() or 0

    active_records = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id, DR.status == "active", DR.deleted_at == None
    ).scalar() or 0

    due_review = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id, DR.status == "due_review", DR.deleted_at == None
    ).scalar() or 0

    disposal_requested = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id, DR.status == "disposal_requested", DR.deleted_at == None
    ).scalar() or 0

    disposed = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id, DR.status == "disposed"
    ).scalar() or 0

    on_legal_hold = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id, DR.legal_hold == True, DR.deleted_at == None
    ).scalar() or 0

    today = date.today()
    overdue = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id,
        DR.status.in_(["active", "due_review"]),
        DR.deleted_at == None,
        DR.retention_end_date != None,
        DR.retention_end_date < today,
    ).scalar() or 0

    upcoming_30 = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id,
        DR.status == "active",
        DR.deleted_at == None,
        DR.retention_end_date != None,
        DR.retention_end_date <= today + timedelta(days=30),
        DR.retention_end_date >= today,
    ).scalar() or 0

    return {
        "total_categories": total_categories,
        "total_records": total_records,
        "active_records": active_records,
        "due_review": due_review,
        "disposal_requested": disposal_requested,
        "disposed": disposed,
        "on_legal_hold": on_legal_hold,
        "overdue": overdue,
        "upcoming_30": upcoming_30,
    }


def disposals_by_month(db: Session, org_id: int, months: int = 12) -> list:
    """Return disposal counts per month for chart data. Last N months."""
    result = []
    today = date.today()
    for i in range(months - 1, -1, -1):
        # First day of target month
        first_of_month = today.replace(day=1) - timedelta(days=i * 30)
        first_of_month = first_of_month.replace(day=1)
        if first_of_month.month == 12:
            next_month = first_of_month.replace(year=first_of_month.year + 1, month=1)
        else:
            next_month = first_of_month.replace(month=first_of_month.month + 1)

        count = db.query(func.count(DataRecord.id)).filter(
            DataRecord.organization_id == org_id,
            DataRecord.status == "disposed",
            DataRecord.disposed_at >= first_of_month,
            DataRecord.disposed_at < next_month,
        ).scalar() or 0

        result.append({
            "month": first_of_month.strftime("%Y-%m"),
            "label": first_of_month.strftime("%b %Y"),
            "count": count,
        })
    return result


def records_by_category(db: Session, org_id: int, limit: int = 10) -> list:
    """Top N categories by record count."""
    rows = db.query(
        DataCategory.name,
        func.count(DataRecord.id).label("count"),
    ).join(DataRecord, DataRecord.category_id == DataCategory.id).filter(
        DataRecord.organization_id == org_id,
        DataRecord.deleted_at == None,
    ).group_by(DataCategory.name).order_by(
        func.count(DataRecord.id).desc()
    ).limit(limit).all()

    return [{"category": r.name, "count": r.count} for r in rows]


def compliance_score(db: Session, org_id: int) -> int:
    """
    Percentage score (0-100) reflecting the compliance posture.
    100 = no overdue records; penalty for overdue & unreviewed.
    """
    DR = DataRecord
    total = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id,
        DR.status != "disposed",
        DR.deleted_at == None,
    ).scalar() or 0
    if total == 0:
        return 100

    today = date.today()
    overdue = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id,
        DR.status.in_(["active", "due_review"]),
        DR.deleted_at == None,
        DR.retention_end_date != None,
        DR.retention_end_date < today,
    ).scalar() or 0

    score = max(0, int(100 * (1 - (overdue / total))))
    return score


def upcoming_deadlines(db: Session, org_id: int, limit: int = 15) -> list:
    """Next N upcoming retention deadlines."""
    today = date.today()
    rows = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status.in_(["active", "due_review"]),
        DataRecord.deleted_at == None,
        DataRecord.retention_end_date != None,
        DataRecord.retention_end_date >= today,
    ).order_by(DataRecord.retention_end_date.asc()).limit(limit).all()

    result = []
    for r in rows:
        cat = db.query(DataCategory).filter(DataCategory.id == r.category_id).first()
        result.append({
            "record_id": r.id,
            "reference": r.record_reference,
            "category": cat.name if cat else "—",
            "retention_end_date": r.retention_end_date.isoformat() if r.retention_end_date else None,
            "days_remaining": (r.retention_end_date - today).days if r.retention_end_date else None,
            "status": r.status,
        })
    return result


# ═══════════════════════════════════════════════════════════════════════════
#   Reports Library 
# ═══════════════════════════════════════════════════════════════════════════

def build_compliance_report(db: Session, org_id: int, year: int) -> dict:
    """
    Annual Compliance Report builder. Summarises the compliance posture for a
    year: categories, records by status, disposals by method, and audit volume.
    
    """
    DC = DataCategory
    DR = DataRecord

    # Disposals by method
    from sqlalchemy import extract
    by_method = {"delete": 0, "anonymise": 0, "archive": 0}
    rows = db.query(
        DC.disposal_method, func.count(DR.id)
    ).join(DC, DC.id == DR.category_id).filter(
        DR.organization_id == org_id,
        DR.status == "disposed",
        extract("year", DR.disposed_at) == year,
    ).group_by(DC.disposal_method).all()
    for method, cnt in rows:
        if method in by_method:
            by_method[method] = cnt

    # Audit count
    audit_count = db.query(func.count(AuditLog.id)).filter(
        AuditLog.organization_id == org_id,
        extract("year", AuditLog.created_at) == year,
    ).scalar() or 0

    total_categories = db.query(func.count(DC.id)).filter(
        DC.organization_id == org_id, DC.deleted_at == None
    ).scalar() or 0

    active_records = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id,
        DR.status != "disposed",
        DR.deleted_at == None,
    ).scalar() or 0

    on_legal_hold = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id,
        DR.legal_hold == True,
        DR.deleted_at == None,
    ).scalar() or 0

    return {
        "year": year,
        "generated_at": datetime.utcnow().isoformat(),
        "total_categories": total_categories,
        "active_records": active_records,
        "disposed_by_method": by_method,
        "disposed_total": sum(by_method.values()),
        "on_legal_hold": on_legal_hold,
        "audit_events": audit_count,
    }


def compliance_report_to_csv_rows(report: dict, title: str = "Annual Compliance Report") -> list:
    """Flatten the report into CSV rows (header + key/value lines) for export."""
    rows = [[title]]
    rows.append(["Year", report["year"]])
    rows.append(["Generated at", report["generated_at"]])
    rows.append([])
    rows.append(["Metric", "Value"])
    rows.append(["Total active categories", report["total_categories"]])
    rows.append(["Active records", report["active_records"]])
    rows.append(["Records on legal hold", report["on_legal_hold"]])
    rows.append(["Disposed (delete)", report["disposed_by_method"]["delete"]])
    rows.append(["Disposed (anonymise)", report["disposed_by_method"]["anonymise"]])
    rows.append(["Disposed (archive)", report["disposed_by_method"]["archive"]])
    rows.append(["Disposed total", report["disposed_total"]])
    rows.append(["Audit events", report["audit_events"]])
    return rows


# Backward-compatibility aliases 
def build_ndpr_report(db: Session, org_id: int, year: int) -> dict:
    return build_compliance_report(db, org_id, year)


def ndpr_report_to_csv_rows(report: dict, title: str = "NDPR Annual Compliance Report") -> list:
    return compliance_report_to_csv_rows(report, title)


# ═══════════════════════════════════════════════════════════════════════════
#   Onboarding Checklist 
# ═══════════════════════════════════════════════════════════════════════════

def org_onboarding_checklist(db: Session, org_id: int) -> list:
    """
    5-step guided onboarding checklist for new admins. Each step has a
    'completed' bool determined by live data queries.
    """
    DC = DataCategory
    DR = DataRecord
    from app.models import Organization

    org = db.query(Organization).filter(Organization.id == org_id).first()

    cat_count = db.query(func.count(DC.id)).filter(
        DC.organization_id == org_id, DC.deleted_at == None
    ).scalar() or 0

    record_count = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id, DR.deleted_at == None
    ).scalar() or 0

    user_count = db.query(func.count(User.id)).filter(
        User.organization_id == org_id, User.deleted_at == None
    ).scalar() or 0

    has_dpo = db.query(User).filter(
        User.organization_id == org_id,
        User.role == "dpo",
        User.deleted_at == None,
    ).first() is not None

    return [
        {
            "step": 1,
            "title": "Organisation registered",
            "description": "Your organisation profile is set up.",
            "completed": org is not None,
            "link": "/settings",
        },
        {
            "step": 2,
            "title": "Data categories configured",
            "description": f"You have {cat_count} categories. Review or add more to match your processing activities.",
            "completed": cat_count >= 3,
            "link": "/categories",
        },
        {
            "step": 3,
            "title": "First data record created",
            "description": "Create at least one data record to start tracking retention.",
            "completed": record_count > 0,
            "link": "/records",
        },
        {
            "step": 4,
            "title": "Invite team members",
            "description": f"You have {user_count} user(s). Invite colleagues to collaborate.",
            "completed": user_count >= 2,
            "link": "/settings/team",
        },
        {
            "step": 5,
            "title": "Assign a DPO",
            "description": "Designate a Data Protection Officer for escalations and reviews.",
            "completed": has_dpo,
            "link": "/settings/team",
        },
    ]


def sync_onboarding_notifications(db: Session, org_id: int, admin_id: int) -> int:
    """
    Idempotent: create onboarding notifications for incomplete steps.
    Returns count of new notifications created.
    """
    checklist = org_onboarding_checklist(db, org_id)
    created = 0
    for step in checklist:
        if step["completed"]:
            continue
        # Check if notification already exists for this step
        existing = db.query(Notification).filter(
            Notification.organization_id == org_id,
            Notification.recipient_id == admin_id,
            Notification.type == "onboarding",
            Notification.subject == step["title"],
        ).first()
        if not existing:
            create_notification(db, org_id, admin_id, "onboarding",
                                step["title"], step["description"])
            created += 1
    return created


def dismiss_onboarding_notifications(db: Session, org_id: int, user_id: int) -> int:
    """Mark all onboarding notifications as read for a user."""
    notifications = db.query(Notification).filter(
        Notification.organization_id == org_id,
        Notification.recipient_id == user_id,
        Notification.type == "onboarding",
        Notification.read_at == None,
    ).all()
    count = 0
    for n in notifications:
        n.read_at = datetime.utcnow()
        count += 1
    if count > 0:
        db.commit()
    return count

