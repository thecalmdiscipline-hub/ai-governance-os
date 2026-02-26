from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from datetime import datetime
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)

    action = Column(String, nullable=False)
    performed_by = Column(String, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    details = Column(Text, nullable=True)