import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, func
from app.db.base import Base


class OutboundRegionPolicy(Base):
    __tablename__ = "outbound_region_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)

    country_code = Column(String(2), nullable=False, index=True)
    region_name = Column(String, nullable=False)

    allowed = Column(Boolean, nullable=False, default=False, server_default="false")
    legal_basis_text = Column(Text, nullable=False)

    footer_template_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("organization_id", "country_code", name="uq_region_policy_org_country"),
    )
