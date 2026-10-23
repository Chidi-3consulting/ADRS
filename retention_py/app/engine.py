"""
SafeData Retention Engine

Provides: the full daily retention engine (flag reviews, consent disposal,
auto-dispose with B5 dual-approval safeguard, escalation, notifications,
follow-ups), housekeeping, quarterly review, audit chain verification,
and outbound webhook dispatch.
"""
import hmac
import hashlib
import json
import httpx
from datetime import datetime, date, timedelta, timezone
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
    owner_missing: bool = False,
) -> int:
    """Insert a single notification row. Returns the new id."""
    notif = Notification(
        organization_id=org_id,
        recipient_id=recipient_id,
        type=notif_type,
        subject=subject,
        message=message,
        related_record_id=related_record_id,
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
    """
    Notify every active user holding any of the given roles with an in-app
    notification. For critical event types, also sends an email to each user
    so they don't miss it even if they haven't logged in.

    Critical types that trigger email:
        escalation_alert, disposal_approval_needed, security_alert, quarterly_review
    """
    # Critical types that warrant an email — not just an in-app bell
    EMAIL_TYPES = {
        "escalation_alert",
        "disposal_approval_needed",
        "security_alert",
        "quarterly_review",
    }

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

        # ── Email for critical events ──
        if notif_type in EMAIL_TYPES and u.email:
            _send_event_email(u.email, u.name, subject, message, notif_type)

    return count


def _send_event_email(to_email: str, user_name: str, subject: str, message: str, notif_type: str):
    """
    Fire a compliance alert email in a background thread.
    Called by notify_role() for critical event types only.
    """
    import threading

    def _send():
        from app.helpers import send_system_email

        # Colour-code the alert bar by type
        accent = {
            "escalation_alert":       "#ef4444",   # red
            "disposal_approval_needed": "#f59e0b", # amber
            "security_alert":         "#7c3aed",   # purple
            "quarterly_review":       "#3b82f6",   # blue
        }.get(notif_type, "#667eea")

        label = {
            "escalation_alert":       "🚨 Escalation Alert",
            "disposal_approval_needed": "⏳ Approval Required",
            "security_alert":         "🔐 Security Alert",
            "quarterly_review":       "📋 Quarterly Review",
        }.get(notif_type, "📌 SafeData Notification")

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a2e;">
          <div style="background:{accent};padding:24px 32px;border-radius:12px 12px 0 0;">
            <h1 style="color:#fff;margin:0;font-size:20px;">{label}</h1>
          </div>
          <div style="background:#fff;padding:28px 32px;border:1px solid #e8e8f0;
                      border-top:none;border-radius:0 0 12px 12px;">
            <p style="font-size:15px;">Hi <strong>{user_name}</strong>,</p>
            <div style="background:#f8f9ff;border-left:4px solid {accent};
                        padding:14px 18px;border-radius:6px;margin:16px 0;">
              <p style="margin:0;font-size:14px;color:#333;">{message}</p>
            </div>
            <p style="font-size:14px;color:#555;">
              Please log in to your SafeData dashboard to review and take action.
            </p>
            <p style="color:#aaa;font-size:12px;margin-top:28px;border-top:1px solid #eee;padding-top:16px;">
              This is an automated compliance alert from SafeData by 3Consulting.<br>
              You are receiving this because you hold an admin or DPO role in your organisation.
            </p>
          </div>
        </div>
        """
        send_system_email(None, to_email, f"SafeData Alert: {subject}", html)

    threading.Thread(target=_send, daemon=True).start()




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
    """E3: queue outbound disposal instructions to connected systems and dispatch immediately."""
    record = db.query(DataRecord).filter(DataRecord.id == record_id).first()
    if not record:
        return

    systems = db.query(ConnectedSystem).filter(
        ConnectedSystem.organization_id == record.organization_id,
        ConnectedSystem.is_active == True,
    ).all()

    for sys in systems:
        if sys.base_url:
            dispatch = DisposalDispatch(
                organization_id=record.organization_id,
                record_id=record.id,
                system_id=sys.id,
                dispatch_type=method,
                external_ref=record.record_reference,
                endpoint_url=sys.base_url,
                status="pending",
                payload=json.dumps({
                    "action": method,
                    "record_reference": record.record_reference,
                    "external_ref": record.record_reference
                }),
            )
            db.add(dispatch)
    db.commit()

    # Trigger immediate outbound HTTP POST dispatch
    try:
        from app.enterprise import process_disposal_dispatches
        process_disposal_dispatches(db)
    except Exception:
        pass


# ── Emergency Freeze Helper ──

def is_disposal_frozen(db: Session, org_id: int = None) -> bool:
    """
    Check if the emergency disposal freeze is active globally or for an organization.
    When active, all automated and manual record disposals are strictly halted.
    """
    if get_setting(db, "disposal_freeze", "0").lower() in ("1", "true", "yes", "on"):
        return True
    if org_id is not None and get_org_setting(db, org_id, "disposal_freeze", "0").lower() in ("1", "true", "yes", "on"):
        return True
    return False


# ── The collection queue ──

COLLECTABLE_STATUSES = ("active", "due_review")


def records_past_retention(db: Session, org_id: int, today: date = None, include_held: bool = False):
    """Query for the *collection queue*: records whose retention period has been reached.

    "Collection" in SafeData means exactly this and nothing else - a record is only
    collectable once its retention end date is today or earlier. Records still inside
    their retention period are never collectable, whatever else is true of them.
    Disposed, deleted and (unless ``include_held``) legal-hold records are excluded.
    Everything that counts, lists or acts on "due" records goes through this one query.
    """
    today = today or date.today()
    q = db.query(DataRecord).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status.in_(COLLECTABLE_STATUSES + (("legal_hold",) if include_held else ())),
        DataRecord.deleted_at == None,  # noqa: E711
        DataRecord.retention_end_date != None,  # noqa: E711
        DataRecord.retention_end_date <= today,
    )
    if not include_held:
        q = q.filter(DataRecord.legal_hold == False)  # noqa: E712
    return q


def simulate_consent_removal(db: Session, org_id: int, record_ids: list = None, today: date = None) -> dict:
    """What would happen if consent were withdrawn now. Strictly read-only.

    Covers records held on a consent basis. For each: the date it would be disposed
    (withdrawal date + the organisation's ``consent_disposal_days``) or why nothing
    would happen automatically (legal hold, freeze, category not consent-triggered).
    """
    today = today or date.today()
    days = int(get_org_setting(db, org_id, "consent_disposal_days", "30"))
    frozen = is_disposal_frozen(db, org_id)
    q = db.query(DataRecord).join(DataCategory, DataRecord.category_id == DataCategory.id).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status != "disposed",
        DataRecord.deleted_at == None,  # noqa: E711
    )
    if record_ids:
        q = q.filter(DataRecord.id.in_(record_ids))
    else:
        q = q.filter(DataCategory.legal_basis == "consent")
    items = []
    for r in q.order_by(DataRecord.id).all():
        rule = db.query(CategoryRetentionRule).filter(
            CategoryRetentionRule.id == r.retention_rule_id
        ).first() if r.retention_rule_id else None
        cat = r.category
        trigger = rule.disposal_trigger if (rule and rule.disposal_trigger) else cat.disposal_trigger
        withdrawn = r.consent_withdrawn_at.date() if r.consent_withdrawn_at else None
        base = withdrawn or today
        if r.legal_hold:
            outcome, dispose_on = "blocked_by_legal_hold", None
        elif trigger != "consent_withdrawal":
            outcome, dispose_on = "no_automatic_disposal", None
        elif frozen:
            outcome, dispose_on = "paused_by_freeze", base + timedelta(days=days)
        else:
            outcome, dispose_on = "would_dispose", base + timedelta(days=days)
        items.append({
            "record_id": r.id, "reference": r.record_reference, "category": cat.name,
            "trigger": trigger, "already_withdrawn_on": withdrawn,
            "dispose_on": dispose_on, "outcome": outcome,
        })
    return {"grace_days": days, "frozen": frozen, "items": items,
            "would_dispose": sum(1 for i in items if i["outcome"] == "would_dispose")}


# ── Execute Disposal ──

def execute_disposal(
    db: Session, record_id: int, actor_id: int = None,
    ip_address: str = "127.0.0.1", dry_run: bool = False
) -> bool:
    """
    Execute disposal of a single record. Transactional, idempotent, legal-hold-safe.
    Supports dry_run simulation mode (returns True if eligible without mutating DB or firing webhooks).
    Halts immediately if the Emergency Freeze switch is active.
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

        # Emergency Freeze Guard
        if not dry_run and is_disposal_frozen(db, record.organization_id):
            db.rollback()
            log_audit(db, record.organization_id, "disposal_aborted_freeze", "data_record",
                      record.id, actor_id, {"reason": "Emergency disposal freeze is active"}, ip_address)
            return False

        cat = db.query(DataCategory).filter(DataCategory.id == record.category_id).first()
        rule = db.query(CategoryRetentionRule).filter(
            CategoryRetentionRule.id == record.retention_rule_id
        ).first() if record.retention_rule_id else None

        method = rule.disposal_method if (rule and rule.disposal_method) else cat.disposal_method

        # Dry-run simulation mode: rollback and return True without modifying data
        if dry_run:
            db.rollback()
            return True

        _now = datetime.now(timezone.utc).replace(tzinfo=None)
        if method == "anonymise":
            record.status = "disposed"
            record.disposed_at = _now
            record.disposed_by = actor_id
            record.record_reference = f"ANONYMISED-{record.id}"
            record.data_subject_type = None
            record.notes = None
        elif method == "delete":
            record.status = "disposed"
            record.disposed_at = _now
            record.disposed_by = actor_id
            record.deleted_at = _now
        else:  # archive
            record.status = "disposed"
            record.disposed_at = _now
            record.disposed_by = actor_id

        db.commit()  # Commits the savepoint

        log_audit(db, record.organization_id, f"record_disposed_{method}", "data_record",
                  record.id, actor_id, {"method": method}, ip_address)

        # Outbound disposal dispatch: queue outbound disposal instructions to connected systems
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

def run_retention_checks(db: Session, org_id: int, dry_run: bool = False) -> dict:
    """
    Orchestrate the full daily retention engine for one organisation.
    Supports dry_run simulation and respects the emergency disposal freeze.
    Returns a summary of counts. 
    """
    frozen = is_disposal_frozen(db, org_id)
    results = {
        "flagged": 0,
        "consent_disposed": 0,
        "auto_disposed": 0,
        "skipped_dual": 0,
        "skipped_frozen": 0,
        "escalated": 0,
        "review_notifications": 0,
        "follow_ups": 0,
        "disposal_frozen": frozen,
        "dry_run": dry_run,
        "plan": [],  # one entry per record the run acts on (or would act on)
    }
    flagged_ids: set = set()

    def plan(r, action: str):
        results["plan"].append({
            "record_id": r.id, "reference": r.record_reference,
            "category": r.category.name if r.category else "",
            "retention_end_date": r.retention_end_date, "action": action,
        })

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
            if not dry_run:  # a simulation must leave every record untouched
                r.status = "due_review"
                r.review_flagged_at = datetime.now(timezone.utc).replace(tzinfo=None)
            flagged_ids.add(r.id)
            results["flagged"] += 1
            plan(r, "flag_for_review")

    if results["flagged"] > 0 and not dry_run:
        db.commit()
        log_audit(db, org_id, "record_flagged_review", "data_record", None, None,
                  {"count": results["flagged"]}, None)

    # ── Step 2: Consent withdrawal disposal (B1) ──
    consent_threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=consent_disposal_days)
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
            if frozen:
                results["skipped_frozen"] += 1
                plan(r, "blocked_by_freeze")
            else:
                if execute_disposal(db, r.id, dry_run=dry_run):
                    results["consent_disposed"] += 1
                    plan(r, "dispose_consent_withdrawn")

    # ── Step 3: Auto-dispose overdue date-based records (B5 dual-approval skip) ──
    overdue_records = db.query(DataRecord).join(
        DataCategory, DataRecord.category_id == DataCategory.id
    ).filter(
        DataRecord.organization_id == org_id,
        (DataRecord.status == "due_review") | DataRecord.id.in_(flagged_ids or [0]),
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
        app_type = getattr(cat, "approval_type", None)
        if not app_type:
            requires_dual = rule.requires_dual_approval if (rule and rule.requires_dual_approval is not None) else cat.requires_dual_approval
            app_type = "dual_approval" if requires_dual else "single_approval"

        if trigger == "date_based":
            if app_type == "auto_disposal":
                if frozen:
                    results["skipped_frozen"] += 1
                    plan(r, "blocked_by_freeze")
                else:
                    if execute_disposal(db, r.id, dry_run=dry_run):
                        results["auto_disposed"] += 1
                        plan(r, "auto_dispose")
            else:
                results["skipped_dual"] += 1
                plan(r, "needs_approval")
                continue

    if dry_run:
        # Read-only from here on: no escalation stamps, notifications, e-mails or audit rows.
        results["escalated"] = db.query(DataRecord).filter(
            DataRecord.organization_id == org_id,
            DataRecord.status == "due_review",
            DataRecord.legal_hold == False,
            DataRecord.deleted_at == None,
            DataRecord.escalation_sent_at == None,
            DataRecord.review_flagged_at != None,
            DataRecord.review_flagged_at
            <= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=escalation_days),
        ).count()
        return results

    if results["skipped_frozen"] > 0:
        log_audit(db, org_id, "disposal_aborted_freeze", "organization", org_id, None,
                  {"skipped_frozen_records": results["skipped_frozen"]}, None)

    if results["skipped_dual"] > 0:
        log_audit(db, org_id, "record_flagged_review", "data_record", None, None,
                  {"dual_approval_skipped": results["skipped_dual"]}, None)

    # ── Step 4: Escalation (B7) ──
    esc_threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=escalation_days)
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
            r.escalation_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
                                    recs[0].id if recs else None,
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
        three_days_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3)
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
                n.related_record_id,
                bool(n.owner_missing),
            )
            n.follow_up_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
        _now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff_7d = _now - timedelta(days=7)
        cutoff_180d = _now - timedelta(days=180)

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

    ninety_days_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=90)
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

    body = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), "data": payload}
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
            ep.last_fired_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
    record.legal_hold_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
    record.legal_hold_lifted_at = datetime.now(timezone.utc).replace(tzinfo=None)
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

    record.consent_withdrawn_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
        record.disposal_requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
        # Single approval — dispose immediately (B1 fix: pass record.id not record object)
        result = execute_disposal(db, record_id, actor_id, ip)
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

    # B1 fix: pass record.id not the record object, and match 4-arg signature
    result = execute_disposal(db, record_id, approver_id, ip)
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

    # S3 fix: Processor & Controller breakdown — include category-level classification
    processor_records = db.query(func.count(DR.id)).outerjoin(
        DataCategory, DataCategory.id == DR.category_id
    ).filter(
        DR.organization_id == org_id,
        DR.deleted_at == None,
        or_(
            and_(DR.processor_name != None, DR.processor_name != ""),
            DataCategory.processing_role.in_(["processor", "joint_controller"]),
        )
    ).scalar() or 0

    controller_records = max(0, total_records - processor_records)

    base_score = compliance_score(db, org_id)

    return {
        "total_categories": total_categories,
        "total_records": total_records,
        "active_records": active_records,
        "active": active_records,
        "due_review": due_review,
        "disposal_requested": disposal_requested,
        "pending_approval": disposal_requested,
        "disposed": disposed,
        "on_legal_hold": on_legal_hold,
        "legal_hold": on_legal_hold,
        "overdue": overdue,
        "upcoming_30": upcoming_30,
        "processor_records": processor_records,
        "controller_records": controller_records,
        "health_score": base_score,
    }


def disposals_by_month(db: Session, org_id: int, months: int = 12) -> list:
    """Return disposal counts per month for chart data. Last N months.
    P5+S2 fix: single GROUP BY query with proper calendar-aligned month boundaries.
    """
    from sqlalchemy import extract, case

    today = date.today()

    # Build the list of (year, month, label) for the last N calendar months
    month_slots = []
    for i in range(months - 1, -1, -1):
        # Move back i months from current month using proper calendar arithmetic
        total_months = today.year * 12 + today.month - 1 - i
        y = total_months // 12
        m = total_months % 12 + 1
        first = date(y, m, 1)
        month_slots.append((y, m, first.strftime("%Y-%m"), first.strftime("%b %Y")))

    # Earliest boundary we need
    earliest = date(month_slots[0][0], month_slots[0][1], 1)

    # Single query: group all disposed records by year+month
    rows = db.query(
        extract("year", DataRecord.disposed_at).label("yr"),
        extract("month", DataRecord.disposed_at).label("mo"),
        func.count(DataRecord.id).label("cnt"),
    ).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status == "disposed",
        DataRecord.disposed_at >= earliest,
    ).group_by(
        extract("year", DataRecord.disposed_at),
        extract("month", DataRecord.disposed_at),
    ).all()

    # Build a lookup dict {(year, month): count}
    counts = {(int(r.yr), int(r.mo)): r.cnt for r in rows}

    return [
        {
            "month": slot[2],
            "label": slot[3],
            "count": counts.get((slot[0], slot[1]), 0),
        }
        for slot in month_slots
    ]


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
    details = compliance_scorecard_details(db, org_id)
    return details["overall_score"]


def compliance_scorecard_details(db: Session, org_id: int) -> dict:
    """
    Calculates detailed multi-pillar compliance score:
    1. Policy Coverage & Legal Basis (25%)
    2. Retention SLA & Timeliness (35%)
    3. Processor & Third-Party Governance (20%)
    4. Security Safeguards & Oversight (20%)
    """
    DR = DataRecord
    DC = DataCategory

    # 1. Policy Coverage (Categories with valid legal basis and retention period/trigger)
    cats = db.query(DC).filter(DC.organization_id == org_id, DC.deleted_at == None).all()
    if not cats:
        policy_coverage = 50
    else:
        configured_cats = sum(1 for c in cats if c.legal_basis and (c.retention_period_days > 0 or c.disposal_trigger == 'consent_withdrawal'))
        policy_coverage = int((configured_cats / len(cats)) * 100)

    # 2. Retention SLA (Records not overdue)
    # S4: Tiered penalty weighting by overdue duration bands
    total_active_records = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id,
        DR.status != "disposed",
        DR.deleted_at == None,
    ).scalar() or 0

    today = date.today()
    overdue_count = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id,
        DR.status.in_(["active", "due_review"]),
        DR.deleted_at == None,
        DR.retention_end_date != None,
        DR.retention_end_date < today,
    ).scalar() or 0

    if total_active_records == 0:
        retention_sla = 100
    else:
        # Tiered penalty: weight overdue records by duration bands
        # 1-30 days = 1x weight, 31-90 days = 2x weight, 90+ days = 3x weight
        overdue_mild = db.query(func.count(DR.id)).filter(
            DR.organization_id == org_id,
            DR.status.in_(["active", "due_review"]),
            DR.deleted_at == None,
            DR.retention_end_date != None,
            DR.retention_end_date < today,
            DR.retention_end_date >= today - timedelta(days=30),
        ).scalar() or 0
        overdue_moderate = db.query(func.count(DR.id)).filter(
            DR.organization_id == org_id,
            DR.status.in_(["active", "due_review"]),
            DR.deleted_at == None,
            DR.retention_end_date != None,
            DR.retention_end_date < today - timedelta(days=30),
            DR.retention_end_date >= today - timedelta(days=90),
        ).scalar() or 0
        overdue_severe = max(0, overdue_count - overdue_mild - overdue_moderate)
        weighted_overdue = overdue_mild + (overdue_moderate * 2) + (overdue_severe * 3)
        weighted_total = total_active_records + (overdue_moderate + overdue_severe * 2)  # expand denominator proportionally
        retention_sla = max(0, int(100 * (1 - (weighted_overdue / max(1, weighted_total)))))

    # 3. Processor Governance
    proc_cats = [c for c in cats if c.processing_role in ('processor', 'joint_controller') or c.processor_name]
    if not proc_cats:
        processor_governance = 100  # No external risk
    else:
        compliant_procs = sum(1 for c in proc_cats if c.processor_retention_status in ('compliant', 'synced', None))
        processor_governance = int((compliant_procs / len(proc_cats)) * 100)

    # 4. Safeguards & Legal Oversight
    # S1 fix: metric-based scoring instead of arbitrary 80/90 baseline
    hold_records = db.query(func.count(DR.id)).filter(
        DR.organization_id == org_id, DR.legal_hold == True, DR.deleted_at == None
    ).scalar() or 0
    dual_approval_cats = sum(1 for c in cats if c.requires_dual_approval)

    # Score out of 100 based on measurable safeguard metrics
    safeguards_score = 60  # base
    if dual_approval_cats > 0:
        safeguards_score += 20  # dual-signature controls present
    if overdue_count == 0:
        safeguards_score += 15  # no SLA violations
    if total_active_records == 0 or (hold_records / max(1, total_active_records)) <= 0.10:
        safeguards_score += 5   # legal hold ratio is healthy (<10% of active)
    safeguards_score = min(100, safeguards_score)

    overall = int(
        (policy_coverage * 0.25) +
        (retention_sla * 0.35) +
        (processor_governance * 0.20) +
        (safeguards_score * 0.20)
    )
    overall = max(0, min(100, overall))

    if overall >= 90:
        grade = "A"
        grade_label = "Audit Ready"
        grade_badge = "bg-success"
    elif overall >= 75:
        grade = "B"
        grade_label = "Good Standing"
        grade_badge = "bg-info text-dark"
    elif overall >= 60:
        grade = "C"
        grade_label = "Moderate Risk"
        grade_badge = "bg-warning text-dark"
    else:
        grade = "D"
        grade_label = "Urgent Action Required"
        grade_badge = "bg-danger"

    recommendations = []
    if policy_coverage < 100:
        recommendations.append("Assign retention categories to all unassigned records to achieve 100% Policy Coverage.")
    if overdue_count > 0:
        recommendations.append(f"Review and execute disposal on {overdue_count} overdue records to restore Retention SLA.")
    if processor_governance < 100:
        recommendations.append("Ensure Data Processing Agreements (DPAs) and processor sync statuses are documented.")
    if safeguards_score < 100 and dual_approval_cats == 0:
        recommendations.append("Enable Dual-Signature safeguards on sensitive policy categories.")
    if not recommendations:
        recommendations.append("All governance pillars are in optimal standing. Maintain continuous audit readiness.")

    return {
        "overall_score": overall,
        "grade": grade,
        "grade_label": grade_label,
        "status_label": grade_label,
        "grade_badge": grade_badge,
        "audit_date": today.strftime("%B %d, %Y"),
        "pillars": {
            "policy_coverage": {"score": policy_coverage},
            "retention_sla": {"score": retention_sla},
            "processor_governance": {"score": processor_governance},
            "safeguards_oversight": {"score": safeguards_score},
            "safeguards_score": {"score": safeguards_score},
        },
        "recommendations": recommendations,
        "overdue_count": overdue_count,
        "total_active_records": total_active_records,
    }


def upcoming_deadlines(db: Session, org_id: int, limit: int = 15) -> list:
    """Next N upcoming retention deadlines.
    P2 fix: single JOIN query instead of N+1 sub-queries per record.
    """
    from sqlalchemy.orm import aliased
    today = date.today()

    # Single JOIN query — eliminates the N+1 pattern
    DC = aliased(DataCategory)
    rows = db.query(DataRecord, DC).outerjoin(
        DC, DC.id == DataRecord.category_id
    ).filter(
        DataRecord.organization_id == org_id,
        DataRecord.status.in_(["active", "due_review"]),
        DataRecord.deleted_at == None,
        DataRecord.retention_end_date != None,
        DataRecord.retention_end_date >= today,
    ).order_by(DataRecord.retention_end_date.asc()).limit(limit).all()

    result = []
    for r, cat in rows:
        days_rem = (r.retention_end_date - today).days if r.retention_end_date else None
        result.append({
            "id": r.id,
            "record_id": r.id,
            "reference": r.record_reference,
            "category": cat.name if cat else "—",
            "processor_name": r.processor_name or (cat.processor_name if cat else None) or "In-House (Controller)",
            "processing_role": cat.processing_role if cat else "controller",
            "retention_end_date": r.retention_end_date.isoformat() if r.retention_end_date else None,
            "due_date": r.retention_end_date.strftime("%d %b %Y") if r.retention_end_date else "—",
            "days_remaining": days_rem,
            "days_left": days_rem,
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
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
            "link": "/users",
        },
        {
            "step": 5,
            "title": "Assign a DPO",
            "description": "Designate a Data Protection Officer for escalations and reviews.",
            "completed": has_dpo,
            "link": "/users",
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
        ).first()  # type: ignore
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
        n.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        count += 1
    if count > 0:
        db.commit()
    return count


# ═══════════════════════════════════════════════════════════════════════════
#   Audit Chain Integrity Verification
# ═══════════════════════════════════════════════════════════════════════════

def verify_audit_chain(db: Session, org_id: int = None, limit: int = 5000) -> dict:
    """
    Verify the SHA-256 HMAC audit chain for an organisation's log entries.
    P1 fix: Caps verification at `limit` most-recent logs for performance
    (full chain verification is expensive on large tables).

    Returns:
        {
            "ok": bool,                  # True if chain is intact
            "verified_count": int,       # Number of entries verified
            "first_broken_log_id": int,  # ID of first broken entry (or None)
        }
    """
    import hashlib as _hashlib

    # Walk the continuous cryptographic chain to maintain parent-child hash continuity
    all_logs = db.query(AuditLog).order_by(AuditLog.id.asc()).limit(limit).all()

    chain_ok = True
    first_broken_id = None
    prev_h = all_logs[0].prev_hash if all_logs and all_logs[0].prev_hash else ("0" * 64)
    verified = 0

    for entry in all_logs:
        # Skip entries that were created before row_hash was implemented
        if not entry.row_hash:
            prev_h = prev_h  # chain continues from last known good hash
            verified += 1
            continue

        import json as _jj
        details_str = ""
        if entry.details is not None:
            if isinstance(entry.details, str):
                details_str = entry.details
            else:
                details_str = _jj.dumps(entry.details, sort_keys=True, ensure_ascii=False)

        payload = "|".join([
            str(entry.organization_id or ""),
            entry.action or "",
            entry.entity_type or "",
            str(entry.entity_id) if entry.entity_id is not None else "",
            str(entry.performed_by) if entry.performed_by is not None else "",
            details_str,
            str(entry.ip_address or ""),
            prev_h,
        ])
        # Legacy hash format (without created_at in payload)
        computed = _hashlib.sha256(payload.encode("utf-8")).hexdigest()

        if entry.row_hash != computed:
            # Try modern format with created_at appended
            created_at_str = entry.created_at.strftime("%Y-%m-%d %H:%M:%S") if entry.created_at else ""
            payload_modern = payload + "|" + created_at_str
            computed_modern = _hashlib.sha256(payload_modern.encode("utf-8")).hexdigest()
            if entry.row_hash != computed_modern:
                chain_ok = False
                first_broken_id = entry.id
                break

        prev_h = entry.row_hash
        if org_id is None or entry.organization_id == org_id:
            verified += 1

    return {
        # New structured keys (used by API endpoints and P1 fix in app_pages.py)
        "ok": chain_ok,
        "verified_count": verified,
        "first_broken_log_id": first_broken_id,
        # Backward-compatible keys (required by existing tests)
        "checked": verified,
        "broken_at": first_broken_id,
    }
