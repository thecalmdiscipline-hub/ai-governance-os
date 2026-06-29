import uuid
from sqlalchemy import Column, String, Integer, Text, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base

_CALL_TYPE = Enum(
    "intake_b", "sales_c",
    name="outbound_call_type",
)

_MEETING_PLATFORM = Enum(
    "zoom", "google_meet", "teams", "whereby",
    name="outbound_meeting_platform",
)

_CALL_STATUS = Enum(
    "scheduled", "completed", "no_show", "cancelled", "rescheduled",
    name="outbound_call_status",
)


class OutboundScheduledCall(Base):
    __tablename__ = "outbound_scheduled_calls"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    prospect_id = Column(String(36), ForeignKey("outbound_prospects.id"), nullable=False, index=True)

    call_type = Column(_CALL_TYPE, nullable=False)

    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=False)

    meeting_platform = Column(
        _MEETING_PLATFORM,
        nullable=False,
        default="zoom",
        server_default="zoom",
    )
    meeting_link = Column(String, nullable=False)

    calcom_event_id = Column(String, nullable=True, index=True)

    status = Column(
        _CALL_STATUS,
        nullable=False,
        default="scheduled",
        server_default="scheduled",
    )

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    prospect = relationship("OutboundProspect", backref="scheduled_calls")
