"""add data_records.relationship_ended_on

The retention clock for "account_closure" categories starts on the day the
relationship ends (account closed, contract ended, event over). That day used to be
folded into consent_withdrawn_at or lost; it now has its own column.

Revision ID: 0004_relationship_ended_on
Revises: 0003_remove_dsar
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_relationship_ended_on"
down_revision: Union[str, None] = "0003_remove_dsar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "relationship_ended_on" not in {c["name"] for c in insp.get_columns("data_records")}:
        with op.batch_alter_table("data_records") as batch:
            batch.add_column(sa.Column("relationship_ended_on", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("data_records") as batch:
        batch.drop_column("relationship_ended_on")
