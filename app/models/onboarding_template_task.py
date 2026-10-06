from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text

from app.db.base import Base


class OnboardingTemplateTask(Base):
    """One task within an OnboardingTemplate's checklist (Batch I, Fase 2.2). phase is 1-8 per the
    Client Onboarding Playbook; position orders tasks within a phase."""

    __tablename__ = "onboarding_template_tasks"

    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("onboarding_templates.id"), nullable=False, index=True)
    phase = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    owner = Column(String, nullable=False)  # valqeron | customer | both
    customer_visible = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)
