import uuid
from sqlalchemy import Column, String, Integer, Numeric, JSON, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base

_COMPANY_STATUS = Enum(
    "pending", "enriched", "disqualified", "blocked",
    name="outbound_company_status",
)


class OutboundCompany(Base):
    __tablename__ = "outbound_companies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)

    name = Column(String, nullable=False)
    domain = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    employee_count = Column(Integer, nullable=True)
    annual_revenue = Column(Numeric, nullable=True)
    country = Column(String(2), nullable=True)
    region_code = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    website = Column(String, nullable=True)
    icp_score = Column(Integer, nullable=True)
    enrichment_source = Column(String, nullable=True)
    enrichment_data = Column(JSON, nullable=True)

    status = Column(
        _COMPANY_STATUS,
        nullable=False,
        default="pending",
        server_default="pending",
    )

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    prospects = relationship("OutboundProspect", back_populates="company")
