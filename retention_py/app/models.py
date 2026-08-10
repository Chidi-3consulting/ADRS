from sqlalchemy import (
    Column, Integer, String, Text, Enum, ForeignKey, 
    DateTime, Date, Boolean, JSON, func, Table
)
from sqlalchemy.orm import relationship
from app.database import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    primary_domain = Column(String(255), unique=True, nullable=False)
    country = Column(String(2), nullable=True)
    tier = Column(Enum("core", "enterprise"), default="core", nullable=False)
    status = Column(Enum("active", "trial", "suspended"), default="trial", nullable=False)
    subscription_status = Column(Enum("trial", "active", "past_due", "cancelled"), default="trial", nullable=False)
    billing_email = Column(String(255), nullable=True)
    last_payment_at = Column(DateTime, nullable=True)
    paystack_customer_code = Column(String(100), nullable=True)
    enterprise_licence_key = Column(String(64), nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum("admin", "dpo", "data_owner"), default="data_owner", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    must_change_password = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    email_verified_at = Column(DateTime, nullable=True)
    verification_token_hash = Column(String(64), nullable=True)
    is_platform_admin = Column(Boolean, default=False, nullable=False)
    twofa_secret = Column(String(64), nullable=True)
    twofa_enabled = Column(Boolean, default=False, nullable=False)
    twofa_recovery = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    organization = relationship("Organization")

class Regulation(Base):
    __tablename__ = "regulations"

    code = Column(String(20), primary_key=True)
    name = Column(String(255), nullable=False)
    country = Column(String(2), nullable=True)
    continent = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

class DataCategory(Base):
    __tablename__ = "data_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    retention_reason = Column(Text, nullable=True)
    compliance_framework = Column(String(50), default="GDPR", nullable=False)
    legal_basis = Column(Enum("legal_obligation", "contract", "consent", "legitimate_interest", "vital_interest", "public_task"), default="legitimate_interest", nullable=False)
    retention_period_days = Column(Integer, default=0, nullable=False)
    retention_period_label = Column(String(100), default="1 year", nullable=False)
    disposal_method = Column(Enum("delete", "anonymise", "archive"), default="delete", nullable=False)
    disposal_trigger = Column(Enum("date_based", "consent_withdrawal", "account_closure"), default="date_based", nullable=False)
    requires_dual_approval = Column(Boolean, default=False, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_frequency = Column(Enum("monthly", "quarterly", "annually"), default="quarterly", nullable=False)
    source = Column(Enum("seeded", "custom"), default="custom", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    owner = relationship("User", foreign_keys=[owner_id])
    organization = relationship("Organization")

class CategoryRetentionRule(Base):
    __tablename__ = "category_retention_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    category_id = Column(Integer, ForeignKey("data_categories.id", ondelete="CASCADE"), nullable=False)
    rule_name = Column(String(255), nullable=False)
    legal_basis = Column(Enum("legal_obligation", "contract", "consent", "legitimate_interest", "vital_interest", "public_task"), nullable=False)
    processing_purpose = Column(String(500), nullable=True)
    institution_type = Column(Enum("all", "banking", "insurance", "healthcare", "public_sector", "telecom", "retail", "general"), default="all", nullable=False)
    retention_period_days = Column(Integer, default=0, nullable=False)
    retention_period_label = Column(String(100), nullable=False)
    disposal_method = Column(Enum("delete", "anonymise", "archive"), default="delete", nullable=False)
    disposal_trigger = Column(Enum("date_based", "consent_withdrawal", "account_closure"), default="date_based", nullable=False)
    requires_dual_approval = Column(Boolean, default=False, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    category = relationship("DataCategory")
    organization = relationship("Organization")

class DataRecord(Base):
    __tablename__ = "data_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    category_id = Column(Integer, ForeignKey("data_categories.id"), nullable=False)
    retention_rule_id = Column(Integer, ForeignKey("category_retention_rules.id", ondelete="SET NULL"), nullable=True)
    original_category_id = Column(Integer, ForeignKey("data_categories.id", ondelete="SET NULL"), nullable=True)
    record_reference = Column(String(255), nullable=False)
    data_subject_type = Column(String(100), nullable=True)
    collection_date = Column(Date, default=func.current_date(), nullable=False)
    retention_end_date = Column(Date, nullable=True)
    status = Column(Enum("active", "due_review", "disposal_requested", "legal_hold", "disposed"), default="active", nullable=False)
    created_by_owner = Column(Boolean, default=False, nullable=False)
    consent_withdrawn_at = Column(DateTime, nullable=True)
    consent_withdrawn_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    category_reassigned_at = Column(DateTime, nullable=True)
    category_reassigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    disposal_requested_at = Column(DateTime, nullable=True)
    disposal_requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_flagged_at = Column(DateTime, nullable=True)
    escalation_sent_at = Column(DateTime, nullable=True)
    legal_hold = Column(Boolean, default=False, nullable=False)
    legal_hold_reason = Column(Text, nullable=True)
    legal_hold_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    legal_hold_at = Column(DateTime, nullable=True)
    legal_hold_lifted_at = Column(DateTime, nullable=True)
    disposed_at = Column(DateTime, nullable=True)
    disposed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    category = relationship("DataCategory", foreign_keys=[category_id])
    rule = relationship("CategoryRetentionRule")
    organization = relationship("Organization")
    attachments = relationship("Attachment", back_populates="record", cascade="all, delete-orphan")

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=True)
    performed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    prev_hash = Column(String(64), nullable=True)
    row_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    executor = relationship("User")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(100), nullable=False)
    related_record_id = Column(Integer, ForeignKey("data_records.id", ondelete="SET NULL"), nullable=True)
    related_dsar_id = Column(Integer, ForeignKey("dsar_requests.id", ondelete="SET NULL"), nullable=True)
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    owner_missing = Column(Boolean, default=False, nullable=False)
    status = Column(Enum("sent", "failed", "pending"), default="pending", nullable=False)
    read_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    follow_up_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class DsarRequest(Base):
    __tablename__ = "dsar_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    reference = Column(String(100), unique=True, nullable=False)
    request_type = Column(Enum("access", "rectification", "erasure", "restriction", "portability", "objection"), nullable=False)
    compliance_framework = Column(String(50), default="GDPR", nullable=False)
    data_subject_name = Column(String(255), nullable=False)
    data_subject_email = Column(String(255), nullable=True)
    data_subject_phone = Column(String(50), nullable=True)
    data_subject_type = Column(String(100), nullable=True)
    identity_verified = Column(Boolean, default=False, nullable=False)
    identity_verified_at = Column(DateTime, nullable=True)
    identity_verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    received_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    extended_due_date = Column(Date, nullable=True)
    extension_reason = Column(Text, nullable=True)
    status = Column(Enum("open", "identity_check", "in_progress", "completed", "rejected", "extended"), default="open", nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    description = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)
    response_notes = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class SystemSetting(Base):
    __tablename__ = "system_settings"

    setting_key = Column(String(100), primary_key=True)
    setting_value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class OrganizationSetting(Base):
    __tablename__ = "organization_settings"

    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    setting_key = Column(String(100), primary_key=True)
    setting_value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class ConnectedSystem(Base):
    __tablename__ = "connected_systems"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    name = Column(String(255), nullable=False)
    system_type = Column(Enum("crm", "core_banking", "hr_platform", "customer_db", "loan_management", "ecommerce", "custom"), default="custom", nullable=False)
    base_url = Column(String(500), nullable=True)
    signing_secret = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    health_status = Column(Enum("healthy", "degraded", "offline", "unknown"), default="unknown", nullable=False)
    last_ping_at = Column(DateTime, nullable=True)
    records_synced = Column(Integer, default=0, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    system_id = Column(Integer, ForeignKey("connected_systems.id"), nullable=False)
    key_name = Column(String(100), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False)
    key_prefix = Column(String(12), nullable=False)
    permissions = Column(JSON, nullable=True)
    rate_limit_per_min = Column(Integer, default=60, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    revoked_at = Column(DateTime, nullable=True)

class FieldMapping(Base):
    __tablename__ = "field_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    system_id = Column(Integer, ForeignKey("connected_systems.id"), nullable=False)
    external_object_type = Column(String(100), nullable=False)
    category_id = Column(Integer, ForeignKey("data_categories.id"), nullable=False)
    external_field = Column(String(255), nullable=False)
    adrs_field = Column(String(100), nullable=False)
    transform = Column(String(255), nullable=True)
    is_required = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class AutoCategorizationRule(Base):
    __tablename__ = "auto_categorization_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    system_id = Column(Integer, ForeignKey("connected_systems.id"), nullable=False)
    rule_name = Column(String(255), default="Auto Rule", nullable=False)
    object_type = Column(String(100), nullable=False)
    condition_field = Column(String(255), nullable=True)
    condition_value = Column(String(255), nullable=True)
    category_id = Column(Integer, ForeignKey("data_categories.id"), nullable=False)
    priority = Column(Integer, default=10, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class IntegrationLog(Base):
    __tablename__ = "integration_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    system_id = Column(Integer, ForeignKey("connected_systems.id", ondelete="SET NULL"), nullable=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True)
    direction = Column(Enum("inbound", "outbound"), nullable=False)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    request_body = Column(JSON, nullable=True)
    response_body = Column(JSON, nullable=True)
    records_affected = Column(Integer, default=0, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class IntakeQueue(Base):
    __tablename__ = "intake_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    system_id = Column(Integer, ForeignKey("connected_systems.id"), nullable=False)
    api_key_id = Column(Integer, ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True)
    batch_id = Column(String(64), nullable=True)
    payload = Column(JSON, nullable=False)
    status = Column(Enum("pending", "processing", "completed", "failed", "duplicate"), default="pending", nullable=False)
    category_id = Column(Integer, ForeignKey("data_categories.id", ondelete="SET NULL"), nullable=True)
    record_id = Column(Integer, ForeignKey("data_records.id", ondelete="SET NULL"), nullable=True)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class DisposalDispatch(Base):
    __tablename__ = "disposal_dispatches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    record_id = Column(Integer, ForeignKey("data_records.id"), nullable=False)
    system_id = Column(Integer, ForeignKey("connected_systems.id"), nullable=False)
    dispatch_type = Column(Enum("delete", "anonymise", "archive"), nullable=False)
    external_ref = Column(String(255), nullable=True)
    endpoint_url = Column(String(500), nullable=True)
    payload = Column(JSON, nullable=True)
    status = Column(Enum("pending", "sent", "confirmed", "failed"), default="pending", nullable=False)
    response_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class ConsentSignal(Base):
    __tablename__ = "consent_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    system_id = Column(Integer, ForeignKey("connected_systems.id"), nullable=False)
    external_ref = Column(String(255), nullable=False)
    signal_type = Column(Enum("withdrawal", "restriction", "erasure_request"), default="withdrawal", nullable=False)
    category_id = Column(Integer, ForeignKey("data_categories.id", ondelete="SET NULL"), nullable=True)
    record_id = Column(Integer, ForeignKey("data_records.id", ondelete="SET NULL"), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    status = Column(Enum("pending", "matched", "processed", "unmatched", "error"), default="pending", nullable=False)
    processed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class RopaEntry(Base):
    __tablename__ = "ropa_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    category_id = Column(Integer, ForeignKey("data_categories.id", ondelete="SET NULL"), nullable=True)
    activity_name = Column(String(255), nullable=False)
    role_type = Column(Enum("controller", "processor"), default="controller", nullable=False)
    controller_name = Column(String(255), nullable=True)
    controller_contact = Column(String(255), nullable=True)
    processor_name = Column(String(255), nullable=True)
    processor_contact = Column(String(255), nullable=True)
    dpo_contact = Column(String(255), nullable=True)
    purpose = Column(Text, nullable=True)
    lawful_basis = Column(String(100), nullable=True)
    data_subjects = Column(Text, nullable=True)
    data_categories = Column(Text, nullable=True)
    recipients = Column(Text, nullable=True)
    third_country_transfers = Column(Text, nullable=True)
    retention_summary = Column(String(255), nullable=True)
    security_measures = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    category = relationship("DataCategory")
    processors = relationship("RopaProcessor", back_populates="ropa_entry", cascade="all, delete-orphan")
    organization = relationship("Organization")


class RopaProcessor(Base):
    """Linked processor sub-entries for a ROPA entry (third-party processors)."""
    __tablename__ = "ropa_processors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ropa_entry_id = Column(Integer, ForeignKey("ropa_entries.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    processor_name = Column(String(255), nullable=False)
    processor_contact = Column(String(255), nullable=True)
    processing_purpose = Column(Text, nullable=True)
    data_categories_handled = Column(Text, nullable=True)
    security_measures = Column(Text, nullable=True)
    sub_processors = Column(Text, nullable=True)
    contract_reference = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    ropa_entry = relationship("RopaEntry", back_populates="processors")


class DpiaAssessment(Base):
    __tablename__ = "dpia_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    title = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey("data_categories.id", ondelete="SET NULL"), nullable=True)
    description = Column(Text, nullable=True)
    necessity_score = Column(Integer, default=1, nullable=False)
    proportionality_score = Column(Integer, default=1, nullable=False)
    likelihood_score = Column(Integer, default=1, nullable=False)
    severity_score = Column(Integer, default=1, nullable=False)
    risk_score = Column(Integer, default=0, nullable=False)
    risk_level = Column(Enum("low", "medium", "high"), default="low", nullable=False)
    mitigation = Column(Text, nullable=True)
    status = Column(Enum("draft", "in_review", "approved", "rejected"), default="draft", nullable=False)
    assessed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class BreachIncident(Base):
    __tablename__ = "breach_incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    reference = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    discovered_at = Column(DateTime, nullable=False)
    occurred_at = Column(DateTime, nullable=True)
    severity = Column(Enum("low", "medium", "high", "critical"), default="medium", nullable=False)
    affected_records = Column(Integer, nullable=True)
    status = Column(Enum("open", "contained", "notified", "closed"), default="open", nullable=False)
    notify_deadline = Column(DateTime, nullable=False)
    notified_authority_at = Column(DateTime, nullable=True)
    notified_subjects_at = Column(DateTime, nullable=True)
    reported_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class ConsentReceipt(Base):
    __tablename__ = "consent_receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    record_id = Column(Integer, ForeignKey("data_records.id", ondelete="SET NULL"), nullable=True)
    data_subject_ref = Column(String(255), nullable=False)
    purpose = Column(String(255), nullable=False)
    lawful_basis = Column(String(100), nullable=True)
    channel = Column(String(100), nullable=True)
    given_at = Column(DateTime, nullable=False)
    withdrawn_at = Column(DateTime, nullable=True)
    receipt_hash = Column(String(64), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    event_types = Column(String(500), default="*", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_fired_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class EnterpriseLicenceKey(Base):
    __tablename__ = "enterprise_licence_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_hash = Column(String(64), unique=True, nullable=False)
    key_prefix = Column(String(32), nullable=False)
    redeemed_by_organization_id = Column(Integer, nullable=True)
    redeemed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    reference = Column(String(100), unique=True, nullable=False)
    amount_kobo = Column(Integer, nullable=False)
    currency = Column(String(3), default="NGN", nullable=False)
    plan_tier = Column(Enum("core", "enterprise"), nullable=False)
    status = Column(Enum("pending", "success", "failed"), default="pending", nullable=False)
    provider = Column(String(32), default="paystack", nullable=False)
    provider_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)

class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(Enum("admin", "dpo", "data_owner"), default="data_owner", nullable=False)
    token_hash = Column(String(64), nullable=False)
    invited_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    record_id = Column(Integer, ForeignKey("data_records.id", ondelete="CASCADE"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    record = relationship("DataRecord", back_populates="attachments")
    uploader = relationship("User")
    organization = relationship("Organization")

class PasswordReset(Base):
    __tablename__ = "password_resets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False)
    token_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class ScheduleReview(Base):
    __tablename__ = "schedule_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    category_id = Column(Integer, ForeignKey("data_categories.id"), nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    review_date = Column(Date, nullable=False)
    outcome = Column(Enum("no_change", "updated", "flagged", "escalated"), default="no_change", nullable=False)
    notes = Column(Text, nullable=True)
    next_review_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    category = relationship("DataCategory")
    reviewer = relationship("User")

class PendingRecalculation(Base):
    __tablename__ = "pending_recalculations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    record_id = Column(Integer, ForeignKey("data_records.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("data_categories.id"), nullable=False)
    old_retention_end_date = Column(Date, nullable=False)
    new_retention_end_date = Column(Date, nullable=False)
    triggered_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(Enum("pending", "recalculate", "keep_original", "ignored"), default="pending", nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    record = relationship("DataRecord")
    category = relationship("DataCategory")

class ImportJob(Base):
    __tablename__ = "import_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), default=1, nullable=False)
    imported_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    total_rows = Column(Integer, default=0, nullable=False)
    valid_rows = Column(Integer, default=0, nullable=False)
    imported_rows = Column(Integer, default=0, nullable=False)
    skipped_rows = Column(Integer, default=0, nullable=False)
    error_rows = Column(Integer, default=0, nullable=False)
    status = Column(Enum("pending", "validated", "imported", "failed"), default="pending", nullable=False)
    error_report = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    importer = relationship("User")

class BackupLog(Base):
    __tablename__ = "backup_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    size_bytes = Column(Integer, nullable=True)
    status = Column(Enum("success", "failed"), nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    success = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)



