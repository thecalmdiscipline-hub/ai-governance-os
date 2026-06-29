import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class OutboundReply(Base):
    __tablename__ = "outbound_replies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)

    # Nullable: soms kunnen we niet matchen aan een specifiek touchpoint
    touchpoint_id = Column(
        String(36), ForeignKey("outbound_touchpoints.id"), nullable=True, index=True
    )
    prospect_id = Column(
        String(36), ForeignKey("outbound_prospects.id"), nullable=True, index=True
    )

    from_email = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=True)
    body_text = Column(Text, nullable=False)
    body_html = Column(Text, nullable=True)

    received_at = Column(DateTime(timezone=True), nullable=False)
    raw_headers = Column(Text, nullable=True)

    esp_inbound_id = Column(String, nullable=True, index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    touchpoint = relationship("OutboundTouchpoint", back_populates="replies")
    prospect = relationship("OutboundProspect", backref="replies")
    classifications = relationship("OutboundReplyClassification", back_populates="reply")
