"""merge_heads_pre_outbound

Revision ID: 557050adf97b
Revises: 06a3ddd7e042, b7e4d92f1a38
Create Date: 2026-05-25 15:24:47.684093

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '557050adf97b'
down_revision: Union[str, Sequence[str], None] = ('06a3ddd7e042', 'b7e4d92f1a38')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
