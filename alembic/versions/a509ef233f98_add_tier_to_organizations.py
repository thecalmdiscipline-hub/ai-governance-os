"""add tier to organizations

Additive only (Batch F, deel 1): a nullable text column. Existing organizations keep NULL
("grandfathered": no tier, no automatic backfill).

Revision ID: a509ef233f98
Revises: b5b6de818bba
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a509ef233f98"
down_revision: Union[str, Sequence[str], None] = "b5b6de818bba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("tier", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "tier")
