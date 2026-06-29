import uuid
from sqlalchemy import Column, String, Integer, JSON, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base

_SEQUENCE_STATE = Enum(
    "pending",
    "person_a_sent",
    "person_b_pending",
    "person_b_sent",
    "person_c_pending",
    "person_c_sent",
    "replied",
    "disqualified",
    name="outbound_prospect_sequence_state",
)


class OutboundProspect(Base):
    __tablename__ = "outbound_prospects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("outbound_companies.id"), nullable=False, index=True)

    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    person_rank = Column(Integer, nullable=False, default=1)

    sequence_state = Column(
        _SEQUENCE_STATE,
        nullable=False,
        default="pending",
        server_default="pending",
    )

    last_touched_at = Column(DateTime, nullable=True)
    enrichment_data = Column(JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("OutboundCompany", back_populates="prospects")
