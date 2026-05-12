from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class MicrosoftDocument(Base):
    __tablename__ = "microsoft_documents"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)

    source_type = Column(String, nullable=False, default="microsoft_365")
    drive_id = Column(String, nullable=True)
    item_id = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False)
    web_url = Column(String, nullable=True)
    mime_type = Column(String, nullable=True)
    last_modified = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization")
