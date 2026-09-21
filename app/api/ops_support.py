"""Support requests, HQ side (Batch G): read all requests and change their status. Only for ops access
(super-admin of HQ with MFA). A status change is audited in the HQ chain and in the source organization's chain."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_ops_access
from app.core.ops_audit import log_ops_action
from app.models.organization import Organization
from app.models.support_request import SupportRequest
from app.models.user import User
from app.services.support_requests import STATUSES

router = APIRouter(prefix="/ops", tags=["Ops"], dependencies=[Depends(require_ops_access)])


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")  # nothing but the status can be changed
    status: Literal["new", "in_progress", "done"]


def _full(row: SupportRequest, organization_name: Optional[str], username: Optional[str]) -> dict:
    return {
        "id": row.id,
        "reference": row.reference,
        "organization_id": row.organization_id,
        "organization_name": organization_name,
        "user_id": row.user_id,
        "username": username,
        "category": row.category,
        "subject": row.subject,
        "message": row.message,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "notified_at": row.notified_at.isoformat() if row.notified_at else None,
        "notify_status": row.notify_status,
        "notify_error": row.notify_error,
    }


@router.get("/support-requests")
def list_support_requests(
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    if status is not None and status not in STATUSES:
        return JSONResponse(status_code=422, content={"error": "invalid_status", "allowed": list(STATUSES)})
    query = (
        db.query(SupportRequest, Organization.name, User.username)
        .outerjoin(Organization, Organization.id == SupportRequest.organization_id)
        .outerjoin(User, User.id == SupportRequest.user_id)
    )
    if status is not None:
        query = query.filter(SupportRequest.status == status)
    rows = query.order_by(SupportRequest.id.desc()).limit(200).all()
    return {"items": [_full(r, org_name, username) for r, org_name, username in rows]}


@router.patch("/support-requests/{request_id}")
def change_support_request_status(
    request_id: int,
    body: StatusChange,
    current_user: User = Depends(require_ops_access),
    db: Session = Depends(get_db),
):
    from datetime import datetime  # local: keeps the module header short

    row = db.query(SupportRequest).filter(SupportRequest.id == request_id).first()
    if row is None:
        return JSONResponse(status_code=404, content={"error": "support_request_not_found"})

    old = row.status
    changed = old != body.status
    if changed:
        row.status = body.status
        row.updated_at = datetime.utcnow()
        db.commit()
        log_ops_action(
            db,
            current_user,
            "support_request_status_changed",
            target_org_id=row.organization_id,
            details=f"reference={row.reference}; {old}->{body.status}",
        )
    return {"reference": row.reference, "status": row.status, "changed": changed}
