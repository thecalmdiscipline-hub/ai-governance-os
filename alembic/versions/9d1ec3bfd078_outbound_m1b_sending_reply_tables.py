"""outbound_m1b_sending_reply_tables

Revision ID: 9d1ec3bfd078
Revises: 29172df93ce9
Create Date: 2026-05-27

Milestone 1b: outbound_touchpoints, outbound_replies, outbound_reply_classifications
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d1ec3bfd078"
down_revision: Union[str, Sequence[str], None] = "29172df93ce9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create outbound_touchpoints, outbound_replies, outbound_reply_classifications."""

    # 1. outbound_touchpoints (FK to outbound_campaigns, outbound_prospects, organizations)
    op.create_table(
        "outbound_touchpoints",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("prospect_id", sa.String(36), nullable=False),
        sa.Column("sequence_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "channel",
            sa.Enum("email", name="outbound_touchpoint_channel"),
            nullable=False,
            server_default="email",
        ),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("esp_message_id", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "scheduled", "sent", "delivered", "bounced", "failed",
                name="outbound_touchpoint_status",
            ),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["outbound_campaigns.id"]),
        sa.ForeignKeyConstraint(["prospect_id"], ["outbound_prospects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbound_touchpoints_organization_id", "outbound_touchpoints", ["organization_id"])
    op.create_index("ix_outbound_touchpoints_campaign_id", "outbound_touchpoints", ["campaign_id"])
    op.create_index("ix_outbound_touchpoints_prospect_id", "outbound_touchpoints", ["prospect_id"])
    op.create_index("ix_outbound_touchpoints_esp_message_id", "outbound_touchpoints", ["esp_message_id"])

    # 2. outbound_replies (FK to outbound_touchpoints [nullable], outbound_prospects [nullable])
    op.create_table(
        "outbound_replies",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("touchpoint_id", sa.String(36), nullable=True),
        sa.Column("prospect_id", sa.String(36), nullable=True),
        sa.Column("from_email", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_headers", sa.Text(), nullable=True),
        sa.Column("esp_inbound_id", sa.String(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["touchpoint_id"], ["outbound_touchpoints.id"]),
        sa.ForeignKeyConstraint(["prospect_id"], ["outbound_prospects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbound_replies_organization_id", "outbound_replies", ["organization_id"])
    op.create_index("ix_outbound_replies_touchpoint_id", "outbound_replies", ["touchpoint_id"])
    op.create_index("ix_outbound_replies_prospect_id", "outbound_replies", ["prospect_id"])
    op.create_index("ix_outbound_replies_from_email", "outbound_replies", ["from_email"])
    op.create_index("ix_outbound_replies_esp_inbound_id", "outbound_replies", ["esp_inbound_id"])

    # 3. outbound_reply_classifications (FK to outbound_replies, users)
    op.create_table(
        "outbound_reply_classifications",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("reply_id", sa.String(36), nullable=False),
        sa.Column(
            "label",
            sa.Enum(
                "A_rejection",
                "B_interested",
                "C_ready",
                "needs_review",
                "ooo",
                "forwarded",
                "question",
                "referral",
                "hostile",
                "unsubscribe",
                name="outbound_reply_label",
            ),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column(
            "classified_by",
            sa.Enum("llm", "human", name="outbound_reply_classified_by"),
            nullable=False,
            server_default="llm",
        ),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["reply_id"], ["outbound_replies.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outbound_reply_classifications_organization_id",
        "outbound_reply_classifications", ["organization_id"],
    )
    op.create_index(
        "ix_outbound_reply_classifications_reply_id",
        "outbound_reply_classifications", ["reply_id"],
    )


def downgrade() -> None:
    """Drop sending/reply tables in reverse FK order."""

    # 3 → 2 → 1
    op.drop_index("ix_outbound_reply_classifications_reply_id", table_name="outbound_reply_classifications")
    op.drop_index("ix_outbound_reply_classifications_organization_id", table_name="outbound_reply_classifications")
    op.drop_table("outbound_reply_classifications")

    op.drop_index("ix_outbound_replies_esp_inbound_id", table_name="outbound_replies")
    op.drop_index("ix_outbound_replies_from_email", table_name="outbound_replies")
    op.drop_index("ix_outbound_replies_prospect_id", table_name="outbound_replies")
    op.drop_index("ix_outbound_replies_touchpoint_id", table_name="outbound_replies")
    op.drop_index("ix_outbound_replies_organization_id", table_name="outbound_replies")
    op.drop_table("outbound_replies")

    op.drop_index("ix_outbound_touchpoints_esp_message_id", table_name="outbound_touchpoints")
    op.drop_index("ix_outbound_touchpoints_prospect_id", table_name="outbound_touchpoints")
    op.drop_index("ix_outbound_touchpoints_campaign_id", table_name="outbound_touchpoints")
    op.drop_index("ix_outbound_touchpoints_organization_id", table_name="outbound_touchpoints")
    op.drop_table("outbound_touchpoints")

    # Drop named enum types (PostgreSQL only)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="outbound_reply_classified_by").drop(bind, checkfirst=True)
        sa.Enum(name="outbound_reply_label").drop(bind, checkfirst=True)
        sa.Enum(name="outbound_touchpoint_status").drop(bind, checkfirst=True)
        sa.Enum(name="outbound_touchpoint_channel").drop(bind, checkfirst=True)
