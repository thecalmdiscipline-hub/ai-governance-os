from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="open")  # open / in_progress / closed

    ai_risk_id = Column(Integer, ForeignKey("ai_risks.id"))

    ai_risk = relationship("AIRisk")