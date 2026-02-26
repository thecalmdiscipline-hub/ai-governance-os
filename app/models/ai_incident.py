from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class AIIncident(Base):
    __tablename__ = "ai_incidents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String, nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow)

    status = Column(String, default="open")
    is_deleted = Column(Boolean, default=False)

    ai_system_id = Column(Integer, ForeignKey("ai_systems.id"))

    ai_system = relationship("AISystem", back_populates="incidents")