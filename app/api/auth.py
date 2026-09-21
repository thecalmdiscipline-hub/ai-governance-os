import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from pydantic import BaseModel, field_validator

from app.api.dependencies import get_current_user, get_current_user_allow_password_change, get_db
from app.core.audit import create_audit_log
from app.core.rate_limiter import rate_limit_login
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User

MFA_TOKEN_MINUTES = 5

router = APIRouter(tags=["Auth"])

security_logger = logging.getLogger("security")


@router.post("/login", dependencies=[Depends(rate_limit_login)])
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    error = HTTPException(status_code=401, detail="Invalid credentials")

    user = db.query(User).filter(User.username == form_data.username).first()

    if not user:
        security_logger.warning(f"Failed login attempt for username: {form_data.username}")
        raise error

    if not user.is_active:
        raise error

    if user.account_locked_until and user.account_locked_until > datetime.utcnow():
        raise error

    if not verify_password(form_data.password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= 5:
            user.account_locked_until = datetime.utcnow() + timedelta(minutes=15)
            security_logger.warning(f"Invalid password attempt for user: {user.username}")
        db.commit()
        raise error

    user.failed_login_attempts = 0
    user.account_locked_until = None
    db.commit()

    # Second factor: a correct password alone does not yield an access token when MFA is on.
    # The short-lived mfa_token is only valid for POST /login/mfa (see _authenticate: "purpose").
    if user.mfa_enabled:
        mfa_token = create_access_token(
            data={"sub": user.username, "org_id": user.organization_id, "purpose": "mfa"},
            expires_delta=timedelta(minutes=MFA_TOKEN_MINUTES),
        )
        return {"mfa_required": True, "mfa_token": mfa_token}

    access_token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role,
            "org_id": user.organization_id,
        }
    )

    security_logger.info(f"Successful login for user: {user.username}")

    response = {"access_token": access_token, "token_type": "bearer"}
    if user.must_change_password:
        response["must_change_password"] = True
    return response


@router.get("/modules")
def get_modules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.module_access import get_modules_for_user
    return get_modules_for_user(user, db)


# ---------------------------------------------------------------------------
# Batch E, deel 3: profile and password change
# These use get_current_user_allow_password_change: they must stay reachable for a user whose
# must_change_password flag is set (every other endpoint answers 403 password_change_required).
# ---------------------------------------------------------------------------

MIN_PASSWORD_LENGTH = 12


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
        return v


@router.get("/auth/me")
def me(user: User = Depends(get_current_user_allow_password_change)):
    return {
        "username": user.username,
        "role": user.role,
        "organization_id": user.organization_id,
        "is_super_admin": bool(user.is_super_admin),
        "mfa_enabled": bool(user.mfa_enabled),
        "mfa": bool(user.mfa_verified),
        "must_change_password": bool(user.must_change_password),
    }


@router.post("/auth/change-password")
def change_password(
    body: ChangePasswordBody,
    user: User = Depends(get_current_user_allow_password_change),
    db: Session = Depends(get_db),
):
    invalid = HTTPException(status_code=401, detail="Invalid credentials")

    if user.account_locked_until and user.account_locked_until > datetime.utcnow():
        raise invalid
    if not verify_password(body.current_password, user.password_hash):
        # Same counter and lock as /login: a stolen access token must not allow guessing the password.
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= 5:
            user.account_locked_until = datetime.utcnow() + timedelta(minutes=15)
        db.commit()
        raise invalid
    if body.new_password == body.current_password:
        raise HTTPException(status_code=400, detail="The new password must differ from the current password")

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.password_changed_at = datetime.utcnow()
    user.failed_login_attempts = 0
    user.account_locked_until = None
    db.commit()

    if user.organization_id is not None:
        create_audit_log(
            db,
            organization_id=user.organization_id,
            entity_type="user",
            entity_id=user.id,
            action="password_changed",
            details="Password changed by the user",
            performed_by=user.username,
        )
    return {"status": "password_changed"}
