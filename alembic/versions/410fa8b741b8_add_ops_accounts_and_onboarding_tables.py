"""add ops_accounts and onboarding tables

Additive only (Batch I, Fase 2.1 + 2.2): five new tables. All global on purpose (HQ reads them,
see app/api/ops_accounts.py and app/api/ops_onboarding.py) — no organization_id tenant filter,
only an optional link from ops_accounts to an existing organization and, optionally, to an
Outbound Engine company row.

Revision ID: 410fa8b741b8
Revises: ba0b699d34f4
Create Date: 2026-10-06 11:05:21.976957

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '410fa8b741b8'
down_revision: Union[str, Sequence[str], None] = 'ba0b699d34f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ops_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("sector", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="lead"),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("proposed_tier", sa.String(), nullable=True),
        sa.Column("primary_contact_name", sa.String(length=120), nullable=True),
        sa.Column("primary_contact_email", sa.String(length=254), nullable=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("outbound_company_id", sa.String(length=36), sa.ForeignKey("outbound_companies.id"), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", name="uq_ops_accounts_organization_id"),
    )
    op.create_index("ix_ops_accounts_status", "ops_accounts", ["status"])

    op.create_table(
        "onboarding_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("key", name="uq_onboarding_templates_key"),
    )

    op.create_table(
        "onboarding_template_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("onboarding_templates.id"), nullable=False),
        sa.Column("phase", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column("customer_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_onboarding_template_tasks_template_id", "onboarding_template_tasks", ["template_id"])

    op.create_table(
        "onboarding_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("ops_accounts.id"), nullable=False),
        sa.Column("template_key", sa.String(), nullable=False),
        sa.Column("template_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("target_golive_date", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_onboarding_projects_account_id", "onboarding_projects", ["account_id"])
    op.create_index("ix_onboarding_projects_status", "onboarding_projects", ["status"])
    op.create_index(
        "ix_onboarding_projects_account_id_status", "onboarding_projects", ["account_id", "status"]
    )

    op.create_table(
        "onboarding_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("onboarding_projects.id"), nullable=False),
        sa.Column("phase", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column("customer_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(), nullable=False, server_default="todo"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
    )
    op.create_index("ix_onboarding_tasks_project_id", "onboarding_tasks", ["project_id"])
    op.create_index("ix_onboarding_tasks_status", "onboarding_tasks", ["status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_onboarding_tasks_status", table_name="onboarding_tasks")
    op.drop_index("ix_onboarding_tasks_project_id", table_name="onboarding_tasks")
    op.drop_table("onboarding_tasks")

    op.drop_index("ix_onboarding_projects_account_id_status", table_name="onboarding_projects")
    op.drop_index("ix_onboarding_projects_status", table_name="onboarding_projects")
    op.drop_index("ix_onboarding_projects_account_id", table_name="onboarding_projects")
    op.drop_table("onboarding_projects")

    op.drop_index("ix_onboarding_template_tasks_template_id", table_name="onboarding_template_tasks")
    op.drop_table("onboarding_template_tasks")

    op.drop_table("onboarding_templates")

    op.drop_index("ix_ops_accounts_status", table_name="ops_accounts")
    op.drop_table("ops_accounts")
