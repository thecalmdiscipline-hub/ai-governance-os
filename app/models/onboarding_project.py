from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String

from app.db.base import Base


class OnboardingProject(Base):
    """One onboarding run for one OpsAccount, started from a named/versioned template snapshot
    (Batch I, Fase 2.2). At most one project with status active/paused per account — enforced in
    app/services/onboarding.py, not at the database level."""

    __tablename__ = "onboarding_projects"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("ops_accounts.id"), nullable=False, index=True)
    template_key = Column(String, nullable=False)
    template_version = Column(String, nullable=False)

    status = Column(String, nullable=False, default="active", index=True)  # active|paused|completed|cancelled
    target_golive_date = Column(Date, nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_onboarding_projects_account_id_status", "account_id", "status"),
    )
