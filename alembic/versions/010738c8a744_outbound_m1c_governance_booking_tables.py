"""outbound_m1c_governance_booking_tables

Revision ID: 010738c8a744
Revises: 9d1ec3bfd078
Create Date: 2026-05-27

Milestone 1c: outbound_scheduled_calls, outbound_region_policies, outbound_suppression_list
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "010738c8a744"
down_revision: Union[str, Sequence[str], None] = "9d1ec3bfd078"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create outbound_scheduled_calls, outbound_region_policies, outbound_suppression_list."""

    # 1. outbound_scheduled_calls (FK to outbound_prospects, organizations)
    op.create_table(
        "outbound_scheduled_calls",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("prospect_id", sa.String(36), nullable=False),
        sa.Column(
            "call_type",
            sa.Enum("intake_b", "sales_c", name="outbound_call_type"),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "meeting_platform",
            sa.Enum("zoom", "google_meet", "teams", "whereby", name="outbound_meeting_platform"),
            nullable=False,
            server_default="zoom",
        ),
        sa.Column("meeting_link", sa.String(), nullable=False),
        sa.Column("calcom_event_id", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "scheduled", "completed", "no_show", "cancelled", "rescheduled",
                name="outbound_call_status",
            ),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["prospect_id"], ["outbound_prospects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbound_scheduled_calls_organization_id", "outbound_scheduled_calls", ["organization_id"])
    op.create_index("ix_outbound_scheduled_calls_prospect_id", "outbound_scheduled_calls", ["prospect_id"])
    op.create_index("ix_outbound_scheduled_calls_calcom_event_id", "outbound_scheduled_calls", ["calcom_event_id"])

    # 2. outbound_region_policies (FK to organizations; unique on org+country)
    op.create_table(
        "outbound_region_policies",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("region_name", sa.String(), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("legal_basis_text", sa.Text(), nullable=False),
        sa.Column("footer_template_id", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "country_code", name="uq_region_policy_org_country"),
    )
    op.create_index("ix_outbound_region_policies_organization_id", "outbound_region_policies", ["organization_id"])
    op.create_index("ix_outbound_region_policies_country_code", "outbound_region_policies", ["country_code"])

    # 3. outbound_suppression_list (FK to organizations; unique on org+email)
    op.create_table(
        "outbound_suppression_list",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "unsubscribed", "hard_bounce", "manual", "spam_complaint", "dnc_list",
                name="outbound_suppression_reason",
            ),
            nullable=False,
        ),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "email", name="uq_suppression_org_email"),
    )
    op.create_index("ix_outbound_suppression_list_organization_id", "outbound_suppression_list", ["organization_id"])
    op.create_index("ix_outbound_suppression_list_email", "outbound_suppression_list", ["email"])


def downgrade() -> None:
    """Drop governance/booking tables in reverse order."""

    # 3 → 2 → 1
    op.drop_index("ix_outbound_suppression_list_email", table_name="outbound_suppression_list")
    op.drop_index("ix_outbound_suppression_list_organization_id", table_name="outbound_suppression_list")
    op.drop_table("outbound_suppression_list")

    op.drop_index("ix_outbound_region_policies_country_code", table_name="outbound_region_policies")
    op.drop_index("ix_outbound_region_policies_organization_id", table_name="outbound_region_policies")
    op.drop_table("outbound_region_policies")

    op.drop_index("ix_outbound_scheduled_calls_calcom_event_id", table_name="outbound_scheduled_calls")
    op.drop_index("ix_outbound_scheduled_calls_prospect_id", table_name="outbound_scheduled_calls")
    op.drop_index("ix_outbound_scheduled_calls_organization_id", table_name="outbound_scheduled_calls")
    op.drop_table("outbound_scheduled_calls")

    # Drop named enum types (PostgreSQL only)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="outbound_suppression_reason").drop(bind, checkfirst=True)
        sa.Enum(name="outbound_call_status").drop(bind, checkfirst=True)
        sa.Enum(name="outbound_meeting_platform").drop(bind, checkfirst=True)
        sa.Enum(name="outbound_call_type").drop(bind, checkfirst=True)
