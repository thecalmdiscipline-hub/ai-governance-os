from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from fastapi import HTTPException

from app.models import (
    AISystem,
    AIRisk,
    CorrectiveAction,
    ProductionApproval,
    Organization
)


def check_deployment_readiness(
    system: AISystem,
    db: Session,
    current_user
):

    if system.lifecycle_stage != "restricted":
        raise HTTPException(
            status_code=400,
            detail="System must be in restricted state before deployment"
        )

    # High risk check
    high_risks = db.query(AIRisk).filter(
        AIRisk.ai_system_id == system.id,
        AIRisk.risk_level == "high",
        AIRisk.is_deleted == False
    ).all()

    for risk in high_risks:

        action = db.query(CorrectiveAction).filter(
            CorrectiveAction.ai_risk_id == risk.id,
            CorrectiveAction.status == "closed"
        ).first()

        if not action:
            raise HTTPException(
                status_code=403,
                detail=f"Open high risk '{risk.title}' blocks deployment"
            )

        if risk.created_at and risk.created_at < datetime.utcnow() - timedelta(days=30):
            raise HTTPException(
                status_code=403,
                detail=f"Aged high risk '{risk.title}' blocks deployment"
            )

    if not system.conformity_assessed:
        raise HTTPException(
            status_code=403,
            detail="Conformity assessment required before deployment"
        )

    # Approval policy
    org = db.query(Organization).filter(
        Organization.id == system.organization_id
    ).first()

    required = org.required_production_approvals or 1

    count = db.query(ProductionApproval).filter(
        ProductionApproval.ai_system_id == system.id
    ).count()

    if count < required:
        raise HTTPException(
            status_code=403,
            detail=f"{required} approvals required. Current: {count}"
        )

    # Separation of duties
    last_approval = db.query(ProductionApproval).filter(
        ProductionApproval.ai_system_id == system.id
    ).order_by(ProductionApproval.timestamp.desc()).first()

    if last_approval and last_approval.approved_by_user_id == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Separation of duties violation. Approver cannot deploy."
        )

    return True