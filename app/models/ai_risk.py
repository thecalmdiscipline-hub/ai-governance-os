from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class AIRisk(Base):
    __tablename__ = "ai_risks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    risk_level = Column(String, nullable=False)
    mitigation = Column(Text, nullable=True)

    status = Column(String, default="open")
    is_deleted = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    ai_system_id = Column(Integer, ForeignKey("ai_systems.id"))

    ai_system = relationship("AISystem", back_populates="risks")