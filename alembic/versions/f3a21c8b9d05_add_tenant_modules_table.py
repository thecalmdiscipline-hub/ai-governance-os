"""add tenant_modules table

Revision ID: f3a21c8b9d05
Revises: 65d192baeb3e
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a21c8b9d05"
down_revision: Union[str, Sequence[str], None] = "65d192baeb3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_modules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("module_key", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "module_key", name="uq_tenant_module"),
    )
    op.create_index("ix_tenant_modules_id", "tenant_modules", ["id"], unique=False)
    op.create_index(
        "ix_tenant_modules_organization_id",
        "tenant_modules",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_modules_organization_id", table_name="tenant_modules")
    op.drop_index("ix_tenant_modules_id", table_name="tenant_modules")
    op.drop_table("tenant_modules")
