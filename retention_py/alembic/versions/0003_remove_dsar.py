"""remove the data subject access request (DSAR) module

SafeData does not handle DSARs. Drops the unused ``dsar_requests`` table and the
``notifications.related_dsar_id`` column that pointed at it.

Revision ID: 0003_remove_dsar
Revises: 0002_worker_tables
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_remove_dsar"
down_revision: Union[str, None] = "0002_worker_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "related_dsar_id" in {c["name"] for c in insp.get_columns("notifications")}:
        with op.batch_alter_table("notifications") as batch:
            batch.drop_column("related_dsar_id")  # Postgres drops the FK with the column
    if "dsar_requests" in insp.get_table_names():
        op.drop_table("dsar_requests")


def downgrade() -> None:
    """Recreate the (empty) table and column so a rollback to the previous release starts."""
    op.create_table(
        "dsar_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=False),
        sa.Column("request_type", sa.Enum("access", "rectification", "erasure", "restriction", "portability",
                                          "objection", native_enum=False, create_constraint=True), nullable=False),
        sa.Column("compliance_framework", sa.String(length=50), nullable=False),
        sa.Column("data_subject_name", sa.String(length=255), nullable=False),
        sa.Column("data_subject_email", sa.String(length=255), nullable=True),
        sa.Column("data_subject_phone", sa.String(length=50), nullable=True),
        sa.Column("data_subject_type", sa.String(length=100), nullable=True),
        sa.Column("identity_verified", sa.Boolean(), nullable=False),
        sa.Column("identity_verified_at", sa.DateTime(), nullable=True),
        sa.Column("identity_verified_by", sa.Integer(), nullable=True),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("extended_due_date", sa.Date(), nullable=True),
        sa.Column("extension_reason", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("open", "identity_check", "in_progress", "completed", "rejected", "extended",
                                    native_enum=False, create_constraint=True), nullable=False),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("response_notes", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["identity_verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("related_dsar_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("notifications_related_dsar_id_fkey", "dsar_requests",
                                 ["related_dsar_id"], ["id"], ondelete="SET NULL")
