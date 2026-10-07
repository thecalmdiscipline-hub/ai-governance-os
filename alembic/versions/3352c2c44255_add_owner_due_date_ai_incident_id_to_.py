"""add owner due_date ai_incident_id to corrective_actions

Additive only (Batch O2): three nullable columns, no backfill, no NOT NULL. Existing rows stay
readable unchanged (all three come back NULL). ai_incident_id lets a corrective action attach to
an incident instead of (or alongside) a risk; ai_risk_id was already nullable on the model even
though every existing row has one.

Revision ID: 3352c2c44255
Revises: 410fa8b741b8
Create Date: 2026-10-07 20:30:45.354261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3352c2c44255'
down_revision: Union[str, Sequence[str], None] = '410fa8b741b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("corrective_actions", sa.Column("owner", sa.String(), nullable=True))
    op.add_column("corrective_actions", sa.Column("due_date", sa.Date(), nullable=True))
    # batch mode: adding a column with an inline FK via a plain ALTER TABLE ADD COLUMN works on
    # Postgres (production) but SQLite (local/CI) has no ALTER-of-constraints support at all —
    # batch mode's copy-and-move strategy is required there, and is a harmless no-op wrapper
    # around the same ALTER on backends that support it directly.
    with op.batch_alter_table("corrective_actions") as batch_op:
        batch_op.add_column(sa.Column("ai_incident_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_corrective_actions_ai_incident_id", "ai_incidents", ["ai_incident_id"], ["id"]
        )
    op.create_index(
        "ix_corrective_actions_ai_incident_id", "corrective_actions", ["ai_incident_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_corrective_actions_ai_incident_id", table_name="corrective_actions")
    with op.batch_alter_table("corrective_actions") as batch_op:
        batch_op.drop_constraint("fk_corrective_actions_ai_incident_id", type_="foreignkey")
        batch_op.drop_column("ai_incident_id")
    op.drop_column("corrective_actions", "due_date")
    op.drop_column("corrective_actions", "owner")
