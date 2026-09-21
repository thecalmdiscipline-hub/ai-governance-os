from typing import Callable, Optional

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_hq_organization_id
from app.db.session import SessionLocal
from app.core.security import SECRET_KEY, ALGORITHM
from app.models.user import User
from app.models import Organization, AISystem, AIRisk, CorrectiveAction

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class PasswordChangeRequired(Exception):
    """Raised for users with must_change_password=True; app/main.py turns it into
    403 {"error": "password_change_required"}."""


def _authenticate(token: str, db: Session, allow_password_change: bool) -> User:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials"
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        org_id = payload.get("org_id")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Short-lived tokens for a special step (the MFA step of the login) carry a "purpose"
    # claim and are never valid as access tokens.
    if payload.get("purpose") is not None:
        raise credentials_exception

    q = db.query(User).filter(User.username == username)

    if org_id is not None:
        q = q.filter(User.organization_id == org_id)

    user = q.first()

    if user is None:
        raise credentials_exception

    # A deactivated user must lose access at once, also with a token that was issued before
    # the deactivation (tokens live up to 60 minutes). Same generic 401 as any invalid token.
    if not user.is_active:
        raise credentials_exception

    # The "mfa" claim only counts while MFA is still enabled for the user, so resetting or
    # disabling MFA also invalidates the elevated rights of tokens that were issued before.
    user.mfa_verified = bool(payload.get("mfa")) and bool(user.mfa_enabled)

    if user.must_change_password and not allow_password_change:
        raise PasswordChangeRequired()

    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    return _authenticate(token, db, allow_password_change=False)


def get_current_user_allow_password_change(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Same as get_current_user, but for the few endpoints a user with must_change_password
    may still call: change-password, me and the MFA endpoints."""
    return _authenticate(token, db, allow_password_change=True)


def has_super_admin_powers(user: User) -> bool:
    """is_super_admin only counts together with an MFA-verified token (claim mfa=true and
    MFA still enabled). Without it a super-admin is an ordinary user of their own tenant, so
    the cross-tenant exceptions below need the MFA login."""
    return bool(user.is_super_admin) and bool(getattr(user, "mfa_verified", False))


def require_ops_access(current_user: User = Depends(get_current_user)) -> User:
    """Control plane guard: active super-admin of the HQ tenant with an MFA-verified token."""
    hq_org_id = get_hq_organization_id()
    allowed = (
        bool(current_user.is_active)
        and bool(current_user.is_super_admin)
        and hq_org_id is not None
        and current_user.organization_id == hq_org_id
        and bool(current_user.mfa_verified)
    )
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Operations access requires a super-admin of the HQ organization with two-step verification",
        )
    return current_user


def require_role(required_role: str) -> Callable:
    def role_checker(current_user: User = Depends(get_current_user)):
        if not has_super_admin_powers(current_user) and current_user.role != required_role:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return role_checker


def get_org_scoped_org(organization_id: int, current_user: User, db: Session):
    q = db.query(Organization).filter(Organization.id == organization_id)
    if not has_super_admin_powers(current_user):
        q = q.filter(Organization.id == current_user.organization_id)
    org = q.first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def get_org_scoped_system(system_id: int, current_user: User, db: Session):
    system = db.query(AISystem).filter(
        AISystem.id == system_id,
        AISystem.organization_id == current_user.organization_id,
        AISystem.is_deleted == False,
    ).first()
    if not system:
        raise HTTPException(status_code=404, detail="AI System not found")
    return system


def get_org_scoped_risk(risk_id: int, current_user: User, db: Session):
    risk = db.query(AIRisk).join(AISystem).filter(
        AIRisk.id == risk_id,
        AISystem.organization_id == current_user.organization_id,
        AIRisk.is_deleted == False,
    ).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")
    return risk


def require_module_access(workflow_key: str) -> Callable:
    def checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        from app.services.module_access import has_workflow_access
        if not has_workflow_access(current_user, workflow_key, db):
            raise HTTPException(
                status_code=403,
                detail=f"Your organization does not have access to the '{workflow_key}' module.",
            )
        return current_user

    return checker


def get_org_scoped_action(action_id: int, current_user: User, db: Session):
    action = db.query(CorrectiveAction).join(AIRisk).join(AISystem).filter(
        CorrectiveAction.id == action_id,
        AISystem.organization_id == current_user.organization_id,
    ).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action
