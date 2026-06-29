import uuid
from sqlalchemy import Column, String, Integer, Enum, DateTime, ForeignKey, UniqueConstraint, func
from app.db.base import Base

_SUPPRESSION_REASON = Enum(
    "unsubscribed", "hard_bounce", "manual", "spam_complaint", "dnc_list",
    name="outbound_suppression_reason",
)


class OutboundSuppressionListEntry(Base):
    __tablename__ = "outbound_suppression_list"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)

    email = Column(String, nullable=False, index=True)
    reason = Column(_SUPPRESSION_REASON, nullable=False)
    source = Column(String, nullable=True)

    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_suppression_org_email"),
    )
