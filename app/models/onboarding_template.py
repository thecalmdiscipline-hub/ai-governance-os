from sqlalchemy import Boolean, Column, Integer, String, UniqueConstraint

from app.db.base import Base


class OnboardingTemplate(Base):
    """A versioned onboarding checklist (Batch I, Fase 2.2) — e.g. 'standard-v1'. Seeded by
    scripts/seed_onboarding_templates.py. A project COPIES these tasks at creation time (see
    OnboardingProject/OnboardingTask) so a later template edit never changes a running project."""

    __tablename__ = "onboarding_templates"

    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False)  # e.g. "standard-v1"
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("key", name="uq_onboarding_templates_key"),
    )
