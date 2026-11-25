from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class DocumentScopeCode(Base):
    """One scope code of a document (V4: a document has one or more codes).

    Codes are fixed after upload (V7). The allowed codes live in
    app/services/document_scope_codes.py, not in this table.
    """

    __tablename__ = "document_scope_codes"
    __table_args__ = (
        UniqueConstraint("document_id", "code", name="uq_document_scope_codes_document_code"),
    )

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    code = Column(String(24), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="scope_codes")
