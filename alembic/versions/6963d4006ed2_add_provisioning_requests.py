"""add provisioning_requests

Additive only (Batch F, deel 2): a new table that remembers the idempotency key of every provisioning
call (with a hash of its parameters), so a repeated call can be answered without creating anything twice.

Revision ID: 6963d4006ed2
Revises: a509ef233f98
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6963d4006ed2"
down_revision: Union[str, Sequence[str], None] = "a509ef233f98"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provisioning_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("request_hash", sa.String(), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("admin_username", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_provisioning_idempotency_key"),
    )
    op.create_index("ix_provisioning_requests_organization_id", "provisioning_requests", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_provisioning_requests_organization_id", table_name="provisioning_requests")
    op.drop_table("provisioning_requests")
