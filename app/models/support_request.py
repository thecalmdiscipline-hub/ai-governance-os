from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.db.base import Base


class SupportRequest(Base):
    """A support request from a customer to Valqeron (HQ). Global table, but every row belongs to the
    organization and user it came from; tenant-scoped endpoints only ever show their own rows."""

    __tablename__ = "support_requests"

    id = Column(Integer, primary_key=True)
    reference = Column(String, nullable=False)  # SR-000123, unique
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    category = Column(String, nullable=False)  # question | problem | access | other
    subject = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="new")  # new | in_progress | done

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # E-mail notification to Valqeron (internal fields, never shown to the customer).
    notified_at = Column(DateTime, nullable=True)
    notify_status = Column(String, nullable=False, default="pending")  # pending | sent | failed | skipped_no_config
    notify_error = Column(String, nullable=True)  # short, generic; never a key, an address or message text

    __table_args__ = (
        UniqueConstraint("reference", name="uq_support_requests_reference"),
        Index("ix_support_requests_user_id_created_at", "user_id", "created_at"),
    )
