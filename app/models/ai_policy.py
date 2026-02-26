from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class AIPolicy(Base):
    __tablename__ = "ai_policies"

    id = Column(Integer, primary_key=True, index=True)

    purpose = Column(Text, nullable=False)
    principles = Column(Text, nullable=False)
    risk_commitment = Column(Text, nullable=False)
    monitoring_commitment = Column(Text, nullable=False)

    organization_id = Column(Integer, ForeignKey("organizations.id"))

    organization = relationship("Organization")