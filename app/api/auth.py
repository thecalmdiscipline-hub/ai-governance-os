import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.core.rate_limiter import rate_limit_login
from app.core.security import verify_password, create_access_token
from app.models.user import User

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

    access_token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role,
            "org_id": user.organization_id,
        }
    )

    security_logger.info(f"Successful login for user: {user.username}")

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/modules")
def get_modules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.module_access import get_modules_for_user
    return get_modules_for_user(user, db)
