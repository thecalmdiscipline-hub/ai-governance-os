"""archive all existing documents

Fase B7 (decision Dennis, 24 Nov 2026): every existing document is archived. Workflows then only
read new, coded documents. No row is deleted, no file is moved.

This is deliberately the LAST revision and stands on its own (no application code depends on it),
so it can be rolled out separately from the rest of Fase B. Without it, existing documents keep
their status ('uncoded' since B1, which no workflow reads either).

- new column documents.scope_status_before_archive (nullable): the status a document had just
  before this migration archived it. NULL for documents this migration did not touch (already
  archived) and for every document created afterwards. The application never reads or writes it.
- every row with scope_status <> 'archived' gets scope_status_before_archive = its old status and
  scope_status = 'archived'.

Downgrade: puts back the saved status, but only for rows that are still 'archived' and still have a
saved status. A document a Valqeron administrator restored in the meantime is 'coded' and keeps that
status. Limitation: a document that was restored and later archived again (V29/V30) still has its
saved pre-migration status, and a downgrade puts that back. Then the column is dropped.

Revision ID: 96a4f064fbef
Revises: fb88a0a24a73
Create Date: 2026-11-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '96a4f064fbef'
down_revision: Union[str, Sequence[str], None] = 'fb88a0a24a73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("scope_status_before_archive", sa.String(16), nullable=True))
    op.execute(
        "UPDATE documents SET scope_status_before_archive = scope_status, scope_status = 'archived' "
        "WHERE scope_status <> 'archived'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE documents SET scope_status = scope_status_before_archive "
        "WHERE scope_status = 'archived' AND scope_status_before_archive IS NOT NULL"
    )
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("scope_status_before_archive")
