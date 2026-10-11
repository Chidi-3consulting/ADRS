"""Legacy column patching for databases created by the pre-Alembic import-time create_all.

Used only by `python -m app.cli adopt-legacy-db`."""

import logging

from sqlalchemy import inspect, text

log = logging.getLogger(__name__)


def ensure_legacy_columns(bind_engine):
    try:
        inspector = inspect(bind_engine)
        with bind_engine.connect() as conn:
            if inspector.has_table("organizations"):
                cols = [c["name"] for c in inspector.get_columns("organizations")]
                if "trial_ends_at" not in cols:
                    conn.execute(text("ALTER TABLE organizations ADD COLUMN trial_ends_at DATETIME NULL"))
                    conn.commit()
            if inspector.has_table("notifications"):
                cols = [c["name"] for c in inspector.get_columns("notifications")]
                if "follow_up_sent_at" not in cols:
                    conn.execute(text("ALTER TABLE notifications ADD COLUMN follow_up_sent_at DATETIME NULL"))
                    conn.commit()
            if inspector.has_table("data_categories"):
                cols = [c["name"] for c in inspector.get_columns("data_categories")]
                if "processing_role" not in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE data_categories ADD COLUMN processing_role VARCHAR(20) DEFAULT 'controller' NOT NULL"  # noqa: E501
                        )
                    )
                    conn.commit()
                if "processor_name" not in cols:
                    conn.execute(text("ALTER TABLE data_categories ADD COLUMN processor_name VARCHAR(255) NULL"))
                    conn.commit()
                if "processor_contact" not in cols:
                    conn.execute(text("ALTER TABLE data_categories ADD COLUMN processor_contact VARCHAR(255) NULL"))
                    conn.commit()
                if "dpa_reference" not in cols:
                    conn.execute(text("ALTER TABLE data_categories ADD COLUMN dpa_reference VARCHAR(255) NULL"))
                    conn.commit()
                if "processor_retention_status" not in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE data_categories ADD COLUMN processor_retention_status VARCHAR(50) DEFAULT 'compliant' NULL"  # noqa: E501
                        )
                    )
                    conn.commit()
                if "data_classification" not in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE data_categories ADD COLUMN data_classification VARCHAR(50) DEFAULT 'standard' NOT NULL"  # noqa: E501
                        )
                    )
                    conn.commit()
                if "approval_type" not in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE data_categories ADD COLUMN approval_type VARCHAR(50) DEFAULT 'single_approval' NOT NULL"  # noqa: E501
                        )
                    )
                    conn.commit()
            if inspector.has_table("data_records"):
                cols = [c["name"] for c in inspector.get_columns("data_records")]
                if "processor_name" not in cols:
                    conn.execute(text("ALTER TABLE data_records ADD COLUMN processor_name VARCHAR(255) NULL"))
                    conn.commit()
                if "processor_sync_status" not in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE data_records ADD COLUMN processor_sync_status VARCHAR(50) DEFAULT 'synced' NULL"  # noqa: E501
                        )
                    )
                    conn.commit()
            # ROPA enhancements: add role_type, processor_name, processor_contact
            if inspector.has_table("ropa_entries"):
                cols = [c["name"] for c in inspector.get_columns("ropa_entries")]
                if "role_type" not in cols:
                    conn.execute(
                        text("ALTER TABLE ropa_entries ADD COLUMN role_type VARCHAR(20) DEFAULT 'controller' NOT NULL")
                    )
                    conn.commit()
                if "processor_name" not in cols:
                    conn.execute(text("ALTER TABLE ropa_entries ADD COLUMN processor_name VARCHAR(255) NULL"))
                    conn.commit()
                if "processor_contact" not in cols:
                    conn.execute(text("ALTER TABLE ropa_entries ADD COLUMN processor_contact VARCHAR(255) NULL"))
                    conn.commit()
    except Exception as e:
        log.error("Legacy column patch failed: %s", e)
        raise
