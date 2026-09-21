"""Support requests (Batch G): a customer writes to Valqeron (HQ) from the portal.

POST /support-requests  – store a request for the caller's own organization and user, audit it (without the
                          text), answer 201 {reference, status, created_at}. 5 per hour / 20 per day per user.
GET  /support-requests  – the caller's own organization only, newest first, no internal (notify_*) fields.
The organization always comes from the token, never from the body.
"""
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.audit import create_audit_log
from app.models.support_request import SupportRequest
from app.models.user import User
from app.services import support_requests as svc
from app.services.support_mail import notify_support_request

router = APIRouter(prefix="/support-requests", tags=["Support"])


class SupportRequestCreate(BaseModel):
    category: Literal["question", "problem", "access", "other"]
    subject: str = Field(max_length=svc.SUBJECT_MAX)
    message: str = Field(max_length=svc.MESSAGE_MAX)

    @field_validator("subject", "message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v


def _public(row: SupportRequest) -> dict:
    return {
        "reference": row.reference,
        "category": row.category,
        "subject": row.subject,
        "message": row.message,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.post("", status_code=201)
def create_support_request(
    body: SupportRequestCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        row = svc.create_support_request(db, current_user, body.category, body.subject, body.message)
    except svc.RateLimited as exc:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(exc.retry_after_seconds)},
            content={
                "error": "too_many_requests",
                "message": f"You have sent too many support requests. Please wait before sending another (limit: {svc.HOURLY_LIMIT} per hour, {svc.DAILY_LIMIT} per day).",
                "retry_after_seconds": exc.retry_after_seconds,
            },
        )

    # Audit in the caller's own organization chain: that a request was made, never what it says.
    create_audit_log(
        db,
        organization_id=current_user.organization_id,
        entity_type="support_request",
        entity_id=row.id,
        action="support_request_created",
        details=f"reference={row.reference}; category={row.category}",
        performed_by=current_user.username,
    )

    # After the commit, outside the request's transaction; never able to fail the request.
    background_tasks.add_task(notify_support_request, row.id)

    return {"reference": row.reference, "status": row.status, "created_at": row.created_at.isoformat()}


@router.get("")
def list_own_support_requests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(SupportRequest)
        .filter(SupportRequest.organization_id == current_user.organization_id)
        .order_by(SupportRequest.id.desc())
        .limit(100)
        .all()
    )
    return {"items": [_public(r) for r in rows]}
