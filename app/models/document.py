from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    filename = Column(String, nullable=False)
    stored_name = Column(String, unique=True, nullable=False, index=True)
    path = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    size = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Fase B: 'uncoded' | 'coded' | 'archived'. Only 'coded' documents are read by a workflow
    # (see app/services/document_access.py).
    scope_status = Column(String(16), nullable=False, default="uncoded", server_default="uncoded", index=True)

    organization = relationship("Organization", back_populates="documents")
    uploaded_by = relationship("User")
    scope_codes = relationship(
        "DocumentScopeCode",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentScopeCode.code",
    )
