from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin / auditor / operator
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    is_super_admin = Column(Boolean, default=False)

    organization = relationship("Organization")