"""add performance indexes

Revision ID: 06a3ddd7e042
Revises: f3a21c8b9d05
Create Date: 2026-05-15

"""
from alembic import op

revision = "06a3ddd7e042"
down_revision = "f3a21c8b9d05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_ai_risks_ai_system_id",
        "ai_risks",
        ["ai_system_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_corrective_actions_ai_risk_id",
        "corrective_actions",
        ["ai_risk_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_workflow_runs_organization_id",
        "workflow_runs",
        ["organization_id"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_runs_organization_id", table_name="workflow_runs")
    op.drop_index("ix_corrective_actions_ai_risk_id", table_name="corrective_actions")
    op.drop_index("ix_ai_risks_ai_system_id", table_name="ai_risks")
