from typing import Callable, Optional

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

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


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
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

    q = db.query(User).filter(User.username == username)

    if org_id is not None:
        q = q.filter(User.organization_id == org_id)

    user = q.first()

    if user is None:
        raise credentials_exception

    return user


def require_role(required_role: str) -> Callable:
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role != required_role:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return role_checker


def get_org_scoped_org(organization_id: int, current_user: User, db: Session):
    org = db.query(Organization).filter(
        Organization.id == organization_id,
        Organization.id == current_user.organization_id,
    ).first()
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


def get_org_scoped_action(action_id: int, current_user: User, db: Session):
    action = db.query(CorrectiveAction).join(AIRisk).join(AISystem).filter(
        CorrectiveAction.id == action_id,
        AISystem.organization_id == current_user.organization_id,
    ).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action
