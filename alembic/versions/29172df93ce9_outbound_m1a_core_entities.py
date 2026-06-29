"""outbound_m1a_core_entities

Revision ID: 29172df93ce9
Revises: 557050adf97b
Create Date: 2026-05-25 15:24:57.188747

Milestone 1a: outbound_companies, outbound_prospects, outbound_campaigns
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "29172df93ce9"
down_revision: Union[str, Sequence[str], None] = "557050adf97b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create outbound_companies, outbound_prospects, outbound_campaigns."""

    # 1. outbound_companies (no FK dependencies on outbound tables)
    op.create_table(
        "outbound_companies",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("annual_revenue", sa.Numeric(), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("region_code", sa.String(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("website", sa.String(), nullable=True),
        sa.Column("icp_score", sa.Integer(), nullable=True),
        sa.Column("enrichment_source", sa.String(), nullable=True),
        sa.Column("enrichment_data", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "enriched", "disqualified", "blocked",
                name="outbound_company_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbound_companies_organization_id", "outbound_companies", ["organization_id"])

    # 2. outbound_prospects (FK to outbound_companies)
    op.create_table(
        "outbound_prospects",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("person_rank", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "sequence_state",
            sa.Enum(
                "pending",
                "person_a_sent",
                "person_b_pending",
                "person_b_sent",
                "person_c_pending",
                "person_c_sent",
                "replied",
                "disqualified",
                name="outbound_prospect_sequence_state",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("last_touched_at", sa.DateTime(), nullable=True),
        sa.Column("enrichment_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["outbound_companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbound_prospects_organization_id", "outbound_prospects", ["organization_id"])
    op.create_index("ix_outbound_prospects_company_id", "outbound_prospects", ["company_id"])
    op.create_index("ix_outbound_prospects_email", "outbound_prospects", ["email"])

    # 3. outbound_campaigns (FK to users)
    op.create_table(
        "outbound_campaigns",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "active", "paused", "completed",
                name="outbound_campaign_status",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "campaign_type",
            sa.Enum(
                "cold", "warm",
                name="outbound_campaign_type",
            ),
            nullable=False,
            server_default="cold",
        ),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbound_campaigns_organization_id", "outbound_campaigns", ["organization_id"])


def downgrade() -> None:
    """Drop outbound tables in reverse order (prospects depends on companies)."""

    # Drop in reverse FK order
    op.drop_index("ix_outbound_campaigns_organization_id", table_name="outbound_campaigns")
    op.drop_table("outbound_campaigns")

    op.drop_index("ix_outbound_prospects_email", table_name="outbound_prospects")
    op.drop_index("ix_outbound_prospects_company_id", table_name="outbound_prospects")
    op.drop_index("ix_outbound_prospects_organization_id", table_name="outbound_prospects")
    op.drop_table("outbound_prospects")

    op.drop_index("ix_outbound_companies_organization_id", table_name="outbound_companies")
    op.drop_table("outbound_companies")

    # Drop named enum types (PostgreSQL only; SQLite uses CHECK constraints)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="outbound_campaign_type").drop(bind, checkfirst=True)
        sa.Enum(name="outbound_campaign_status").drop(bind, checkfirst=True)
        sa.Enum(name="outbound_prospect_sequence_state").drop(bind, checkfirst=True)
        sa.Enum(name="outbound_company_status").drop(bind, checkfirst=True)
