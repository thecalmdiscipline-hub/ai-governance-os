"""Fase B5a: Valqeron staff flags (/ops/staff). Only a super-admin of HQ with MFA (require_ops_access).

The flag is_valqeron_admin is set here and nowhere else (never through the customer API).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_ops_access
from app.core.config import get_hq_organization_id
from app.core.ops_audit import log_ops_action
from app.models.user import User

router = APIRouter(prefix="/ops", tags=["Ops"], dependencies=[Depends(require_ops_access)])


class StaffUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_valqeron_admin: bool


@router.put("/staff/{user_id}")
def set_staff_flags(
    user_id: int,
    body: StaffUpdate,
    current_user: User = Depends(require_ops_access),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.organization_id != get_hq_organization_id():
        raise HTTPException(
            status_code=422,
            detail={"error": "not_hq_user", "message": "Only users of the HQ organization can be Valqeron administrators."},
        )

    changed = bool(target.is_valqeron_admin) != body.is_valqeron_admin
    target.is_valqeron_admin = body.is_valqeron_admin
    db.commit()

    if changed:
        log_ops_action(
            db,
            current_user,
            "valqeron_admin_granted" if body.is_valqeron_admin else "valqeron_admin_revoked",
            target_org_id=target.organization_id,
            details=f"user {target.username}",
        )
    return {"id": target.id, "username": target.username, "is_valqeron_admin": target.is_valqeron_admin, "changed": changed}
