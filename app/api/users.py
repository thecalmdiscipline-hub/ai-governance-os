import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.core.security import hash_password
from app.models.user import User

router = APIRouter(prefix="/users", tags=["Users"])

_VALID_ROLES = {"admin", "auditor", "operator"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    organization_id: Optional[int] = None  # super_admin only; omit to use caller's org

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username cannot be empty")
        if not re.match(r"^[a-zA-Z0-9_.\-]+$", v):
            raise ValueError("Username may only contain letters, digits, _, . and -")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in _VALID_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(_VALID_ROLES))}")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    organization_id: Optional[int]
    is_active: bool
    is_super_admin: bool

    model_config = {"from_attributes": True}


class PasswordReset(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin" and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def _get_target_user(user_id: int, current_user: User, db: Session) -> User:
    """Fetch a user by id, scoping to caller's org unless super_admin."""
    q = db.query(User).filter(User.id == user_id)
    if not current_user.is_super_admin:
        q = q.filter(User.organization_id == current_user.organization_id)
    target = q.first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    return target


def _guard_super_admin_target(target: User, current_user: User) -> None:
    """Prevent non-super-admins from acting on super_admin accounts."""
    if target.is_super_admin and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    payload: UserCreate,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    if payload.organization_id is not None and not current_user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Only super admins can create users in other organizations",
        )

    org_id = (
        payload.organization_id
        if current_user.is_super_admin and payload.organization_id is not None
        else current_user.organization_id
    )

    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        organization_id=org_id,
        is_active=True,
        is_super_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("", response_model=List[UserResponse])
def list_users(
    organization_id: Optional[int] = Query(default=None),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    if organization_id is not None and not current_user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Only super admins can list users in other organizations",
        )

    org_id = (
        organization_id
        if current_user.is_super_admin and organization_id is not None
        else current_user.organization_id
    )

    return db.query(User).filter(User.organization_id == org_id).all()


@router.delete("/{user_id}")
def deactivate_user(
    user_id: int,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")

    target = _get_target_user(user_id, current_user, db)
    _guard_super_admin_target(target, current_user)

    if not target.is_active:
        raise HTTPException(status_code=409, detail="User is already deactivated")

    target.is_active = False
    db.commit()

    return {"user_id": target.id, "username": target.username, "status": "deactivated"}


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: PasswordReset,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    target = _get_target_user(user_id, current_user, db)
    _guard_super_admin_target(target, current_user)

    target.password_hash = hash_password(payload.new_password)
    target.failed_login_attempts = 0
    target.account_locked_until = None
    db.commit()

    return {"user_id": target.id, "username": target.username, "status": "password_reset"}
