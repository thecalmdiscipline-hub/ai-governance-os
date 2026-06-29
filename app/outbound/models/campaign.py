import uuid
from sqlalchemy import Column, String, Integer, Text, JSON, Enum, DateTime, ForeignKey, func
from app.db.base import Base

_CAMPAIGN_STATUS = Enum(
    "draft", "active", "paused", "completed",
    name="outbound_campaign_status",
)

_CAMPAIGN_TYPE = Enum(
    "cold", "warm",
    name="outbound_campaign_type",
)


class OutboundCampaign(Base):
    __tablename__ = "outbound_campaigns"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    status = Column(
        _CAMPAIGN_STATUS,
        nullable=False,
        default="draft",
        server_default="draft",
    )
    campaign_type = Column(
        _CAMPAIGN_TYPE,
        nullable=False,
        default="cold",
        server_default="cold",
    )

    config = Column(JSON, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
