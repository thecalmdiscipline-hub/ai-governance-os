from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("")
def get_audit_logs(
    limit: int = Query(default=20, ge=1, le=200),
    entity_type: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    q = db.query(AuditLog).filter(
        AuditLog.organization_id == current_user.organization_id
    )

    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)

    if action:
        q = q.filter(AuditLog.action == action)

    rows = q.order_by(AuditLog.id.desc()).limit(limit).all()

    items = []
    for row in rows:
        items.append({
            "id": row.id,
            "organization_id": row.organization_id,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "action": row.action,
            "performed_by": row.performed_by,
            "details": row.details,
            "timestamp": row.timestamp.isoformat() if row.timestamp else "",
            "previous_hash": row.previous_hash,
            "record_hash": row.record_hash,
        })

    return {
        "status": "ok",
        "total": len(items),
        "items": items,
    }
