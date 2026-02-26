from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AISystemUpdate(BaseModel):
    risk_category: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    conformity_assessed: Optional[bool] = None
    last_reviewed_at: Optional[datetime] = None

class AISystem(Base):
    __tablename__ = "ai_systems"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    purpose = Column(Text, nullable=True)

    status = Column(String, default="active")
    is_deleted = Column(Boolean, default=False)

    organization_id = Column(Integer, ForeignKey("organizations.id"))

    organization = relationship("Organization", back_populates="ai_systems")
    risks = relationship("AIRisk", back_populates="ai_system", cascade="all, delete")
    incidents = relationship("AIIncident", back_populates="ai_system", cascade="all, delete")
    risk_category = Column(String, nullable=True)
    lifecycle_stage = Column(String, nullable=True)
    conformity_assessed = Column(Boolean, default=False)
    last_reviewed_at = Column(DateTime, nullable=True)