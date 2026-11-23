"""add document scope codes and scope_status

Fase B, B1. Additive only:
- new table document_scope_codes (document_id, code, created_at), unique (document_id, code);
- new column documents.scope_status ('uncoded' | 'coded' | 'archived'), server default 'uncoded',
  so every existing row becomes 'uncoded'. No row or file is touched beyond that.

Archiving the existing rows is a separate migration (B7).

Revision ID: 507b3c60b20b
Revises: 3352c2c44255
Create Date: 2026-11-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '507b3c60b20b'
down_revision: Union[str, Sequence[str], None] = '3352c2c44255'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_scope_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_id", "code", name="uq_document_scope_codes_document_code"),
    )
    op.create_index("ix_document_scope_codes_document_id", "document_scope_codes", ["document_id"])
    op.create_index("ix_document_scope_codes_code", "document_scope_codes", ["code"])

    op.add_column(
        "documents",
        sa.Column("scope_status", sa.String(length=16), nullable=False, server_default="uncoded"),
    )
    op.create_index("ix_documents_scope_status", "documents", ["scope_status"])


def downgrade() -> None:
    op.drop_index("ix_documents_scope_status", table_name="documents")
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("scope_status")
    op.drop_index("ix_document_scope_codes_code", table_name="document_scope_codes")
    op.drop_index("ix_document_scope_codes_document_id", table_name="document_scope_codes")
    op.drop_table("document_scope_codes")
