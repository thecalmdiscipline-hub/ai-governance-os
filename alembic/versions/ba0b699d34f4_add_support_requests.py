"""add support_requests

Additive only (Batch G, deel 1): a new table. It is global on purpose (HQ reads it), but every row belongs
to the organization and user it came from.

Revision ID: ba0b699d34f4
Revises: 6963d4006ed2
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ba0b699d34f4"
down_revision: Union[str, Sequence[str], None] = "6963d4006ed2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "support_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("notified_at", sa.DateTime(), nullable=True),
        sa.Column("notify_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("notify_error", sa.String(), nullable=True),
        sa.UniqueConstraint("reference", name="uq_support_requests_reference"),
    )
    op.create_index("ix_support_requests_organization_id", "support_requests", ["organization_id"])
    op.create_index("ix_support_requests_user_id_created_at", "support_requests", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_support_requests_user_id_created_at", table_name="support_requests")
    op.drop_index("ix_support_requests_organization_id", table_name="support_requests")
    op.drop_table("support_requests")
