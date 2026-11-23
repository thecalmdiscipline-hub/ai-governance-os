"""add document_usage and users.is_valqeron_admin

Fase B5/B6. Additive only:
- new table document_usage (run_id, document_id, codes, created_at): which documents a workflow
  run read. Used to archive instead of delete a used document (V29) and for the audit (V19).
- new column users.is_valqeron_admin (default false): Valqeron staff who may assign scope codes
  (B5a). Set only through PUT /ops/staff/{user_id}.

Revision ID: bab4f26df0b0
Revises: 507b3c60b20b
Create Date: 2026-11-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'bab4f26df0b0'
down_revision: Union[str, Sequence[str], None] = '507b3c60b20b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("workflow_runs.run_id"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("codes", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_document_usage_run_id", "document_usage", ["run_id"])
    op.create_index("ix_document_usage_document_id", "document_usage", ["document_id"])

    op.add_column(
        "users",
        sa.Column("is_valqeron_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_valqeron_admin")
    op.drop_index("ix_document_usage_document_id", table_name="document_usage")
    op.drop_index("ix_document_usage_run_id", table_name="document_usage")
    op.drop_table("document_usage")
