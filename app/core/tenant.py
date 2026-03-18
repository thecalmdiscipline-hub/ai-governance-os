from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import Organization, AISystem, AIRisk, CorrectiveAction
from app.models.user import User


def get_org_scoped_org(organization_id: int, current_user: User, db: Session):
    org = db.query(Organization).filter(
        Organization.id == organization_id,
        Organization.id == current_user.organization_id
    ).first()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return org


def get_org_scoped_system(system_id: int, current_user: User, db: Session):
    system = db.query(AISystem).filter(
        AISystem.id == system_id,
        AISystem.organization_id == current_user.organization_id,
        AISystem.is_deleted == False
    ).first()

    if not system:
        raise HTTPException(status_code=404, detail="AI System not found")

    return system


def get_org_scoped_risk(risk_id: int, current_user: User, db: Session):
    risk = db.query(AIRisk).join(AISystem).filter(
        AIRisk.id == risk_id,
        AISystem.organization_id == current_user.organization_id,
        AIRisk.is_deleted == False
    ).first()

    if not risk:
        raise HTTPException(status_code=404, detail="AI Risk not found")

    return risk


def get_org_scoped_action(action_id: int, current_user: User, db: Session):
    action = db.query(CorrectiveAction).join(AIRisk).join(AISystem).filter(
        CorrectiveAction.id == action_id,
        AISystem.organization_id == current_user.organization_id
    ).first()

    if not action:
        raise HTTPException(status_code=404, detail="Corrective Action not found")

    return action