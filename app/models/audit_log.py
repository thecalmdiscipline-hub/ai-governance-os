from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # FK MUST exist for governance integrity
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False
    )

    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
    action = Column(String, nullable=False)
    performed_by = Column(String, nullable=True)

    timestamp = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    details = Column(Text, nullable=True)

    # 🔐 Immutability / blockchain-style chain
    previous_hash = Column(String, nullable=True)
    record_hash = Column(String, nullable=True)

    # Relationship
    organization = relationship(
        "Organization",
        back_populates="audit_logs"
    )

from sqlalchemy import event
from sqlalchemy.orm import mapper


@event.listens_for(AuditLog, "before_update")
def prevent_update(mapper, connection, target):
    raise Exception("Audit logs are immutable and cannot be updated")


@event.listens_for(AuditLog, "before_delete")
def prevent_delete(mapper, connection, target):
    raise Exception("Audit logs are immutable and cannot be deleted")