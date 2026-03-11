from sqlalchemy import Column, Integer, ForeignKey, String, DateTime
from datetime import datetime
from app.db.base import Base


class ProductionApproval(Base):
    __tablename__ = "production_approvals"

    id = Column(Integer, primary_key=True, index=True)
    ai_system_id = Column(Integer, ForeignKey("ai_systems.id"))
    approved_by_user_id = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)