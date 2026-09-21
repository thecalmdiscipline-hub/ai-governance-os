"""add mfa and password-change columns to users

Additive only (Batch E, deel 1): every column is nullable or has a safe server default,
so existing rows and the existing login flow are unaffected.

Revision ID: b5b6de818bba
Revises: 010738c8a744
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b5b6de818bba"
down_revision: Union[str, Sequence[str], None] = "010738c8a744"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("mfa_secret_enc", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("mfa_last_step", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("mfa_backup_codes", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("mfa_failed_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("mfa_locked_until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for column in (
        "mfa_locked_until",
        "mfa_failed_attempts",
        "mfa_backup_codes",
        "mfa_last_step",
        "mfa_secret_enc",
        "mfa_enabled",
        "password_changed_at",
        "must_change_password",
    ):
        op.drop_column("users", column)
