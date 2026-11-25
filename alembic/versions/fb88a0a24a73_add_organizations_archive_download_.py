"""add organizations.archive_download_enabled

Fase B7 (B5b, decision Dennis 24 Nov 2026): archived documents can be downloaded only by a Valqeron
administrator, unless this flag is on for the document's organization. Additive only, default false.

Revision ID: fb88a0a24a73
Revises: bab4f26df0b0
Create Date: 2026-11-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fb88a0a24a73'
down_revision: Union[str, Sequence[str], None] = 'bab4f26df0b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("archive_download_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_column("archive_download_enabled")
