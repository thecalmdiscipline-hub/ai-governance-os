from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.db.base import Base


class ProvisioningRequest(Base):
    """One row per successful provisioning call: the idempotency key, a hash of the parameters that were
    used, and what was created. Holds no password and no other secret."""

    __tablename__ = "provisioning_requests"

    id = Column(Integer, primary_key=True)
    idempotency_key = Column(String, nullable=False)
    request_hash = Column(String, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    admin_username = Column(String, nullable=False)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_provisioning_idempotency_key"),)
