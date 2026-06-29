import uuid
from sqlalchemy import Column, String, Integer, Text, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base

_TOUCHPOINT_CHANNEL = Enum(
    "email",
    name="outbound_touchpoint_channel",
)

_TOUCHPOINT_STATUS = Enum(
    "scheduled", "sent", "delivered", "bounced", "failed",
    name="outbound_touchpoint_status",
)


class OutboundTouchpoint(Base):
    __tablename__ = "outbound_touchpoints"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    campaign_id = Column(String(36), ForeignKey("outbound_campaigns.id"), nullable=False, index=True)
    prospect_id = Column(String(36), ForeignKey("outbound_prospects.id"), nullable=False, index=True)

    sequence_step = Column(Integer, nullable=False, default=1)

    channel = Column(
        _TOUCHPOINT_CHANNEL,
        nullable=False,
        default="email",
        server_default="email",
    )

    subject = Column(String, nullable=False)
    body_text = Column(Text, nullable=False)
    body_html = Column(Text, nullable=True)

    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    esp_message_id = Column(String, nullable=True, index=True)

    status = Column(
        _TOUCHPOINT_STATUS,
        nullable=False,
        default="scheduled",
        server_default="scheduled",
    )

    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    campaign = relationship("OutboundCampaign", backref="touchpoints")
    prospect = relationship("OutboundProspect", backref="touchpoints")
    replies = relationship("OutboundReply", back_populates="touchpoint")
