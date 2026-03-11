from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    # Governance policy controls
    max_review_age_days = Column(Integer, default=30)
    required_production_approvals = Column(Integer, default=1)

    # Existing DB columns (DO NOT REMOVE if they exist in DB)
    country = Column(String, nullable=True)
    sector = Column(String, nullable=True)

    # Relationships
    ai_systems = relationship("AISystem", back_populates="organization")
    audit_logs = relationship("AuditLog", back_populates="organization")
    ai_policies = relationship("AIPolicy", back_populates="organization")