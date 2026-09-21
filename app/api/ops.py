"""Control plane (/ops): only for a super-admin of the HQ tenant who logged in with MFA.

Deliberately minimal in Batch E (whoami only); the real operations endpoints come in Batch F.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_ops_access
from app.core.ops_audit import log_ops_action
from app.models.user import User

router = APIRouter(prefix="/ops", tags=["Ops"], dependencies=[Depends(require_ops_access)])


@router.get("/whoami")
def whoami(current_user: User = Depends(require_ops_access), db: Session = Depends(get_db)):
    log_ops_action(db, current_user, "ops_whoami")
    return {
        "username": current_user.username,
        "organization_id": current_user.organization_id,
        "is_super_admin": True,
        "mfa": True,
    }
