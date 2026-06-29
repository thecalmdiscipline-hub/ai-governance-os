import uuid
from sqlalchemy import Column, String, Integer, Text, Float, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base

_REPLY_LABEL = Enum(
    "A_rejection",
    "B_interested",
    "C_ready",
    "needs_review",
    "ooo",
    "forwarded",
    "question",
    "referral",
    "hostile",
    "unsubscribe",
    name="outbound_reply_label",
)

_CLASSIFIED_BY = Enum(
    "llm", "human",
    name="outbound_reply_classified_by",
)


class OutboundReplyClassification(Base):
    __tablename__ = "outbound_reply_classifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    reply_id = Column(String(36), ForeignKey("outbound_replies.id"), nullable=False, index=True)

    label = Column(_REPLY_LABEL, nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=False)

    classified_by = Column(
        _CLASSIFIED_BY,
        nullable=False,
        default="llm",
        server_default="llm",
    )

    model = Column(String, nullable=True)
    tokens_used = Column(Integer, nullable=True)

    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    reply = relationship("OutboundReply", back_populates="classifications")
