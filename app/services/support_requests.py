"""
Support requests from customers to Valqeron (HQ): creation with per-user limits.

The message text is written by the customer for Valqeron; it lives in the support_requests table and in the
notification e-mail, and nowhere else: not in audit details, not in log lines (see app/services/support_mail.py).
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.support_request import SupportRequest
from app.models.user import User

CATEGORIES = ("question", "problem", "access", "other")
STATUSES = ("new", "in_progress", "done")

SUBJECT_MAX = 200
MESSAGE_MAX = 5000
HOURLY_LIMIT = 5
DAILY_LIMIT = 20


class RateLimited(Exception):
    def __init__(self, retry_after_seconds: int):
        super().__init__("rate_limited")
        self.retry_after_seconds = retry_after_seconds


def _oldest_in_window(db: Session, user_id: int, since: datetime) -> Optional[datetime]:
    return (
        db.query(func.min(SupportRequest.created_at))
        .filter(SupportRequest.user_id == user_id, SupportRequest.created_at >= since)
        .scalar()
    )


def check_limits(db: Session, user_id: int, now: Optional[datetime] = None) -> None:
    """At most 5 requests per hour and 20 per day per user (counted from the table itself)."""
    now = now or datetime.utcnow()
    for window, limit in ((timedelta(hours=1), HOURLY_LIMIT), (timedelta(days=1), DAILY_LIMIT)):
        since = now - window
        count = db.query(func.count(SupportRequest.id)).filter(SupportRequest.user_id == user_id, SupportRequest.created_at >= since).scalar()
        if count >= limit:
            oldest = _oldest_in_window(db, user_id, since) or now
            wait = int((oldest + window - now).total_seconds())
            raise RateLimited(max(wait, 1))


def create_support_request(db: Session, user: User, category: str, subject: str, message: str) -> SupportRequest:
    """Store a request for the user's OWN organization and user. Commits. Raises RateLimited."""
    check_limits(db, user.id)
    now = datetime.utcnow()
    row = SupportRequest(
        reference=f"TMP-{uuid4().hex}",  # replaced by SR-<id> below, in the same transaction
        organization_id=user.organization_id,
        user_id=user.id,
        category=category,
        subject=subject.strip(),
        message=message.strip(),
        status="new",
        created_at=now,
        updated_at=now,
        notify_status="pending",
    )
    db.add(row)
    db.flush()
    row.reference = f"SR-{row.id:06d}"
    db.commit()
    db.refresh(row)
    return row
