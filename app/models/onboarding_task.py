from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.db.base import Base


class OnboardingTask(Base):
    """One copied-from-template task inside a running OnboardingProject (Batch I, Fase 2.2).
    Copied at project creation; later template edits never change a running project's tasks."""

    __tablename__ = "onboarding_tasks"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("onboarding_projects.id"), nullable=False, index=True)
    phase = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    owner = Column(String, nullable=False)  # valqeron | customer | both
    customer_visible = Column(Boolean, nullable=False, default=False)

    status = Column(String, nullable=False, default="todo", index=True)  # todo|doing|done|skipped|blocked
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    completed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(String(500), nullable=True)
