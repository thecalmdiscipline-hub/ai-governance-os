from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    file_reference = Column(String, nullable=True)  # future file storage
    created_at = Column(DateTime, default=datetime.utcnow)

    ai_system_id = Column(Integer, ForeignKey("ai_systems.id"), nullable=True)
    ai_risk_id = Column(Integer, ForeignKey("ai_risks.id"), nullable=True)

    ai_system = relationship("AISystem")
    ai_risk = relationship("AIRisk")