"""
MFA endpoints (Batch E, deel 2): enrollment, second login step, disable.

Security rules (see app/core/mfa.py for the primitives):
  - A secret, code or backup code is never logged, never put in an audit line and never part of
    an exception message. Audit lines only say *that* something happened.
  - All failures on the login step are the same generic 401 ("Invalid credentials"), whether the
    token is wrong, the user unknown/inactive/locked, or the code wrong.
  - 5 consecutive wrong codes lock MFA for the user for 15 minutes; a success resets the counter.
  - A TOTP step can be used once (mfa_last_step); a backup code works once.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_allow_password_change, get_db
from app.core import mfa
from app.core.audit import create_audit_log
from app.core.rate_limiter import rate_limit_login
from app.core.security import ALGORITHM, SECRET_KEY, create_access_token, verify_password
from app.models.user import User

router = APIRouter(tags=["MFA"])

_UNAVAILABLE = HTTPException(status_code=503, detail="Two-step verification is not available on this server")


class CodeBody(BaseModel):
    code: str


class DisableBody(BaseModel):
    password: str
    code: str


class MFALoginBody(BaseModel):
    mfa_token: str
    code: str


def _audit(db: Session, user: User, action: str, details: str) -> None:
    if user.organization_id is None:
        return
    create_audit_log(
        db,
        organization_id=user.organization_id,
        entity_type="user_mfa",
        entity_id=user.id,
        action=action,
        details=details,
        performed_by=user.username,
    )


def _is_locked(user: User) -> bool:
    return bool(user.mfa_locked_until and user.mfa_locked_until > datetime.utcnow())


def _register_failure(db: Session, user: User) -> None:
    """Count a failed MFA attempt; lock for 15 minutes on the 5th in a row."""
    user.mfa_failed_attempts = (user.mfa_failed_attempts or 0) + 1
    locked = user.mfa_failed_attempts >= mfa.MAX_FAILED_ATTEMPTS
    if locked:
        user.mfa_locked_until = datetime.utcnow() + timedelta(minutes=mfa.LOCK_MINUTES)
        user.mfa_failed_attempts = 0
    db.commit()
    if locked:
        _audit(db, user, "mfa_locked", f"MFA locked for {mfa.LOCK_MINUTES} minutes after repeated failed attempts")
    else:
        _audit(db, user, "mfa_failed", "Failed MFA attempt")


def _reset_counters(user: User) -> None:
    user.mfa_failed_attempts = 0
    user.mfa_locked_until = None


def _check_code(user: User, code: str, allow_backup: bool = True) -> Optional[str]:
    """Verify a TOTP code or (optionally) a backup code and update the in-memory user.

    Returns "totp", "backup" or None. The caller commits on success.
    """
    code = mfa.normalize_code(code)
    if mfa.is_totp_format(code):
        step = mfa.verify_totp(mfa.decrypt_secret(user.mfa_secret_enc), code, user.mfa_last_step)
        if step is None:
            return None
        user.mfa_last_step = step
        return "totp"
    if not allow_backup:
        return None
    remaining = mfa.consume_backup_code(user.mfa_backup_codes, code)
    if remaining is None:
        return None
    user.mfa_backup_codes = remaining
    return "backup"


def _locked_user(db: Session, user_id: int) -> User:
    """Re-read the user row with a row lock so two parallel requests can't both use one code."""
    return db.query(User).filter(User.id == user_id).with_for_update().first()


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------

@router.post("/auth/mfa/setup")
def mfa_setup(
    response: Response,
    user: User = Depends(get_current_user_allow_password_change),
    db: Session = Depends(get_db),
):
    """Create a new TOTP secret (stored encrypted, MFA still off) and return it once for the app."""
    if user.mfa_enabled:
        raise HTTPException(status_code=409, detail="Two-step verification is already enabled")
    try:
        secret = mfa.new_secret()
        user.mfa_secret_enc = mfa.encrypt_secret(secret)
    except mfa.MFAConfigError:
        raise _UNAVAILABLE
    user.mfa_last_step = None
    db.commit()
    _audit(db, user, "mfa_enrollment_started", "MFA enrollment started")
    response.headers["Cache-Control"] = "no-store"
    return {"secret": secret, "otpauth_uri": mfa.provisioning_uri(secret, user.username)}


@router.post("/auth/mfa/enable")
def mfa_enable(
    body: CodeBody,
    response: Response,
    user: User = Depends(get_current_user_allow_password_change),
    db: Session = Depends(get_db),
):
    """Confirm enrollment with a valid code; returns the 10 backup codes exactly once."""
    user = _locked_user(db, user.id)
    if user.mfa_enabled:
        raise HTTPException(status_code=409, detail="Two-step verification is already enabled")
    if not user.mfa_secret_enc:
        raise HTTPException(status_code=400, detail="Start the setup first")
    if _is_locked(user):
        raise HTTPException(status_code=401, detail="Invalid code")
    try:
        kind = _check_code(user, body.code, allow_backup=False)
    except mfa.MFAConfigError:
        raise _UNAVAILABLE
    if kind is None:
        _register_failure(db, user)
        raise HTTPException(status_code=401, detail="Invalid code")

    codes = mfa.generate_backup_codes()
    user.mfa_backup_codes = mfa.hash_backup_codes(codes)
    user.mfa_enabled = True
    _reset_counters(user)
    db.commit()
    _audit(db, user, "mfa_enrollment_confirmed", f"MFA enabled; {len(codes)} backup codes issued")
    response.headers["Cache-Control"] = "no-store"
    return {"backup_codes": codes}


@router.post("/auth/mfa/disable")
def mfa_disable(
    body: DisableBody,
    user: User = Depends(get_current_user_allow_password_change),
    db: Session = Depends(get_db),
):
    """Turn MFA off (password + current code). Not allowed for super-admins."""
    user = _locked_user(db, user.id)
    if user.is_super_admin:
        raise HTTPException(status_code=403, detail="Two-step verification cannot be disabled for a super-admin account")
    if not user.mfa_enabled:
        raise HTTPException(status_code=409, detail="Two-step verification is not enabled")
    if _is_locked(user):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        kind = _check_code(user, body.code) if verify_password(body.password, user.password_hash) else None
    except mfa.MFAConfigError:
        raise _UNAVAILABLE
    if kind is None:
        _register_failure(db, user)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    clear_mfa(user)
    db.commit()
    _audit(db, user, "mfa_disabled", "MFA disabled by the user")
    return {"status": "disabled"}


def clear_mfa(user: User) -> None:
    """Wipe every MFA field of a user (used by disable and by scripts/mfa_reset.py)."""
    user.mfa_enabled = False
    user.mfa_secret_enc = None
    user.mfa_last_step = None
    user.mfa_backup_codes = None
    _reset_counters(user)


# ---------------------------------------------------------------------------
# Second login step
# ---------------------------------------------------------------------------

@router.post("/login/mfa", dependencies=[Depends(rate_limit_login)])
def login_mfa(request: Request, body: MFALoginBody, db: Session = Depends(get_db)):
    error = HTTPException(status_code=401, detail="Invalid credentials")

    try:
        payload = jwt.decode(body.mfa_token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise error
    if payload.get("purpose") != "mfa" or not payload.get("sub"):
        raise error

    candidate = (
        db.query(User)
        .filter(User.username == payload["sub"], User.organization_id == payload.get("org_id"))
        .first()
    )
    if not candidate:
        raise error
    user = _locked_user(db, candidate.id)
    if not user.is_active or not user.mfa_enabled or not user.mfa_secret_enc or _is_locked(user):
        raise error

    try:
        kind = _check_code(user, body.code)
    except mfa.MFAConfigError:
        raise _UNAVAILABLE
    if kind is None:
        _register_failure(db, user)
        raise error

    _reset_counters(user)
    db.commit()
    if kind == "backup":
        _audit(db, user, "mfa_backup_code_used", "A backup code was used to log in")

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "org_id": user.organization_id, "mfa": True}
    )
    result = {"access_token": access_token, "token_type": "bearer"}
    if user.must_change_password:
        result["must_change_password"] = True
    return result
