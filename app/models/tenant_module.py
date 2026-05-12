from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class TenantModule(Base):
    __tablename__ = "tenant_modules"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    module_key = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    organization = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("organization_id", "module_key", name="uq_tenant_module"),
    )
