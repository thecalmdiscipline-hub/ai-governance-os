from sqlalchemy import Boolean, Column, Integer, String, false
from sqlalchemy.orm import relationship
from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    max_review_age_days = Column(Integer, default=30)
    required_production_approvals = Column(Integer, default=1)

    country = Column(String, nullable=True)
    sector = Column(String, nullable=True)

    # starter | business | enterprise; NULL for organizations that existed before tiers (grandfathered).
    tier = Column(String, nullable=True)

    # Fase B7 (B5b): customer users may download archived documents only when this is on.
    # Valqeron administrators always may.
    archive_download_enabled = Column(Boolean, nullable=False, default=False, server_default=false())

    ai_systems = relationship("AISystem", back_populates="organization")
    audit_logs = relationship("AuditLog", back_populates="organization")
    ai_policies = relationship("AIPolicy", back_populates="organization")
    documents = relationship("Document", back_populates="organization", cascade="all, delete-orphan")
