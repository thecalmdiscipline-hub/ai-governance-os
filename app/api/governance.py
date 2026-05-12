import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_db,
    get_current_user,
    require_role,
    get_org_scoped_org,
    get_org_scoped_system,
    get_org_scoped_risk,
    get_org_scoped_action,
)
from app.core.audit import create_audit_log
from app.core.deployment_service import check_deployment_readiness
from app.models import (
    AIIncident,
    AIPolicy,
    AIRisk,
    AISystem,
    CorrectiveAction,
    Evidence,
    Organization,
    ProductionApproval,
)
from app.models.user import User
from app.schemas.ai_policy import AIPolicyCreate, AIPolicyResponse
from app.schemas.ai_risk import AIRiskCreate, AIRiskResponse
from app.schemas.ai_system import AISystemCreate, AISystemResponse, AISystemUpdate
from app.schemas.corrective_action import (
    CorrectiveActionCreate,
    CorrectiveActionResponse,
    CorrectiveActionStatusUpdate,
)
from app.schemas.evidence import EvidenceCreate
from app.schemas.organization import OrganizationCreate, OrganizationResponse

router = APIRouter(tags=["Governance"])


class GovernanceConfigUpdate(BaseModel):
    required_production_approvals: Optional[int] = None
    max_review_age_days: Optional[int] = None


# -------------------------
# ORGANIZATIONS
# -------------------------

@router.post("/organizations", response_model=OrganizationResponse, status_code=201)
def create_organization(
    org: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Only super admins can create organizations")

    db_org = Organization(**org.dict())
    db.add(db_org)
    db.commit()
    db.refresh(db_org)

    create_audit_log(
        db=db,
        organization_id=db_org.id,
        entity_type="organization",
        entity_id=db_org.id,
        action="created",
        details=f"Organization {db_org.name} created by {current_user.username}",
        performed_by=current_user.username,
    )

    return db_org


@router.patch("/organizations/{organization_id}/governance-config")
def update_governance_config(
    organization_id: int,
    config: GovernanceConfigUpdate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == organization_id).first()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if config.required_production_approvals is not None:
        if config.required_production_approvals < 1:
            raise HTTPException(status_code=400, detail="Minimum 1 approval required")
        org.required_production_approvals = config.required_production_approvals

    if config.max_review_age_days is not None:
        if config.max_review_age_days < 1:
            raise HTTPException(status_code=400, detail="Review age must be positive")
        org.max_review_age_days = config.max_review_age_days

    db.commit()
    db.refresh(org)

    create_audit_log(
        db=db,
        organization_id=org.id,
        entity_type="organization",
        entity_id=org.id,
        action="governance_config_updated",
        details=f"Governance config updated by {current_user.username}",
        performed_by=current_user.username,
    )

    return {
        "organization_id": org.id,
        "required_production_approvals": org.required_production_approvals,
        "max_review_age_days": org.max_review_age_days,
    }


@router.get("/organizations/{organization_id}/iso-score")
def iso_governance_score(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = get_org_scoped_org(organization_id, current_user, db)

    high_risks = (
        db.query(AIRisk)
        .join(AISystem)
        .filter(
            AISystem.organization_id == org.id,
            AIRisk.risk_level == "high",
            AIRisk.is_deleted == False,
        )
        .all()
    )

    effective_high = 0
    aged_high = 0

    for risk in high_risks:
        action = db.query(CorrectiveAction).filter(
            CorrectiveAction.ai_risk_id == risk.id,
            CorrectiveAction.status == "closed",
        ).first()

        if not action:
            effective_high += 1
            if risk.created_at and risk.created_at < datetime.utcnow() - timedelta(days=30):
                aged_high += 1

    medium_risks = (
        db.query(AIRisk)
        .join(AISystem)
        .filter(
            AISystem.organization_id == org.id,
            AIRisk.risk_level == "medium",
            AIRisk.is_deleted == False,
        )
        .count()
    )

    open_incidents = (
        db.query(AIIncident)
        .join(AISystem)
        .filter(
            AISystem.organization_id == org.id,
            AIIncident.is_deleted == False,
        )
        .count()
    )

    score = 100
    score -= (effective_high - aged_high) * 20
    score -= aged_high * 35
    score -= medium_risks * 10
    score -= open_incidents * 5
    score = max(score, 0)

    readiness_level = "High"
    if score < 75:
        readiness_level = "Moderate"
    if score < 50:
        readiness_level = "Low"

    return {
        "organization_id": org.id,
        "effective_high_risks": effective_high,
        "aged_high_risks": aged_high,
        "medium_risks": medium_risks,
        "open_incidents": open_incidents,
        "iso_42001_score": score,
        "readiness_level": readiness_level,
    }


@router.get("/organizations/{organization_id}/governance-snapshot")
def governance_snapshot(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = get_org_scoped_org(organization_id, current_user, db)

    systems = db.query(AISystem).filter(
        AISystem.organization_id == org.id,
        AISystem.is_deleted == False,
    ).all()

    production = sum(1 for s in systems if s.lifecycle_stage == "production")
    restricted = sum(1 for s in systems if s.lifecycle_stage == "restricted")
    other = len(systems) - production - restricted

    high_risks = (
        db.query(AIRisk)
        .join(AISystem)
        .filter(
            AISystem.organization_id == org.id,
            AIRisk.risk_level == "high",
            AIRisk.is_deleted == False,
        )
        .all()
    )

    aged_high = sum(
        1 for risk in high_risks
        if risk.created_at and risk.created_at < datetime.utcnow() - timedelta(days=30)
    )

    maturity_score = 100
    if restricted > 0:
        maturity_score -= 10
    if aged_high > 0:
        maturity_score -= 20
    if len(high_risks) > 0:
        maturity_score -= 10
    maturity_score = max(maturity_score, 0)

    return {
        "organization_id": org.id,
        "systems": {
            "total": len(systems),
            "production": production,
            "restricted": restricted,
            "other": other,
        },
        "risk_exposure": {
            "high_risks": len(high_risks),
            "aged_high_risks": aged_high,
        },
        "approval_policy": {
            "required_production_approvals": org.required_production_approvals or 1,
        },
        "audit_integrity": "valid",
        "governance_maturity_percentage": maturity_score,
    }


# -------------------------
# AI SYSTEMS
# -------------------------

@router.post("/ai-systems", response_model=AISystemResponse)
def create_ai_system(
    system: AISystemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_system = AISystem(
        **system.dict(exclude={"organization_id"}),
        organization_id=current_user.organization_id,
    )
    db.add(db_system)
    db.commit()
    db.refresh(db_system)
    return db_system


@router.delete("/ai-systems/{ai_system_id}")
def soft_delete_ai_system(
    ai_system_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    system = get_org_scoped_system(ai_system_id, current_user, db)
    system.is_deleted = True
    system.lifecycle_stage = "archived"
    db.commit()

    create_audit_log(
        db=db,
        organization_id=int(current_user.organization_id),
        entity_type="ai_system",
        entity_id=int(system.id),
        action="archived",
        details=f"AI System {system.name} archived by {current_user.username}",
        performed_by=current_user.username,
    )

    return {"message": "AI system archived"}


@router.patch("/ai-systems/{system_id}/governance")
def update_ai_system_governance(
    system_id: int,
    update: AISystemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    system = get_org_scoped_system(system_id, current_user, db)

    if not update.reason or update.reason.strip() == "":
        raise HTTPException(status_code=400, detail="Justification reason is required")

    if update.lifecycle_stage == "production" and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin users can move system to production")

    if update.lifecycle_stage == "production":
        high_risks = db.query(AIRisk).filter(
            AIRisk.ai_system_id == system.id,
            AIRisk.risk_level == "high",
            AIRisk.is_deleted == False,
        ).all()

        last_approval = (
            db.query(ProductionApproval)
            .filter(ProductionApproval.ai_system_id == system.id)
            .order_by(ProductionApproval.timestamp.desc())
            .first()
        )

        if last_approval is not None:
            if int(last_approval.approved_by_user_id) == int(current_user.id):
                raise HTTPException(
                    status_code=403,
                    detail="Separation of duties violation. Approver cannot deploy.",
                )

        for risk in high_risks:
            action = db.query(CorrectiveAction).filter(
                CorrectiveAction.ai_risk_id == risk.id,
                CorrectiveAction.status == "closed",
            ).first()

            if not action:
                raise HTTPException(
                    status_code=400,
                    detail=f"Open high risk '{risk.title}' requires closed corrective action before production",
                )

            if risk.created_at and risk.created_at < datetime.utcnow() - timedelta(days=30):
                raise HTTPException(
                    status_code=400,
                    detail=f"Aged high risk '{risk.title}' blocks production deployment",
                )

        if not update.conformity_assessed:
            raise HTTPException(
                status_code=400,
                detail="High-risk systems require conformity assessment before production",
            )

        org = db.query(Organization).filter(Organization.id == system.organization_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        required = org.required_production_approvals or 1
        count = db.query(ProductionApproval).filter(
            ProductionApproval.ai_system_id == system.id
        ).count()

        if count < required:
            raise HTTPException(
                status_code=400,
                detail=f"{required} production approvals required. Current: {count}",
            )

    if update.risk_category is not None:
        system.risk_category = update.risk_category
    if update.lifecycle_stage is not None:
        system.lifecycle_stage = update.lifecycle_stage
    if update.conformity_assessed is not None:
        system.conformity_assessed = update.conformity_assessed
    if update.last_reviewed_at is not None:
        system.last_reviewed_at = update.last_reviewed_at

    org = db.query(Organization).filter(Organization.id == system.organization_id).first()
    if org and system.last_reviewed_at:
        max_age = org.max_review_age_days or 30
        if system.last_reviewed_at < datetime.utcnow() - timedelta(days=max_age):
            system.lifecycle_stage = "restricted"
            create_audit_log(
                db=db,
                organization_id=int(system.organization_id),
                entity_type="ai_system",
                entity_id=int(system.id),
                action="auto_downgrade",
                details=f"System auto-restricted due to expired review period ({max_age} days)",
                performed_by="system",
            )

    db.commit()
    db.refresh(system)

    create_audit_log(
        db=db,
        organization_id=int(current_user.organization_id),
        entity_type="ai_system",
        entity_id=int(system.id),
        action="governance_updated",
        details=f"Governance updated by user {current_user.username}. Reason: {update.reason}",
        performed_by=current_user.username,
    )

    return {
        "system_id": system.id,
        "risk_category": system.risk_category,
        "lifecycle_stage": system.lifecycle_stage,
        "conformity_assessed": system.conformity_assessed,
        "last_reviewed_at": system.last_reviewed_at,
    }


@router.get("/ai-systems/{system_id}/readiness-check")
def production_readiness_check(
    system_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    system = get_org_scoped_system(system_id, current_user, db)
    org = get_org_scoped_org(system.organization_id, current_user, db)

    required = org.required_production_approvals or 1
    approvals = db.query(ProductionApproval).filter(
        ProductionApproval.ai_system_id == system.id
    ).all()
    approval_count = len(approvals)

    high_risks = db.query(AIRisk).filter(
        AIRisk.ai_system_id == system.id,
        AIRisk.risk_level == "high",
        AIRisk.is_deleted == False,
    ).all()

    open_high = 0
    aged_high = 0
    for risk in high_risks:
        action = db.query(CorrectiveAction).filter(
            CorrectiveAction.ai_risk_id == risk.id,
            CorrectiveAction.status == "closed",
        ).first()
        if not action:
            open_high += 1
        if risk.created_at and risk.created_at < datetime.utcnow() - timedelta(days=30):
            aged_high += 1

    separation_block = bool(
        approvals and int(approvals[-1].approved_by_user_id) == int(current_user.id)
    )

    allowed = (
        approval_count >= required
        and open_high == 0
        and aged_high == 0
        and system.conformity_assessed
        and not separation_block
    )

    return {
        "system_id": system.id,
        "approvals": {"current": approval_count, "required": required},
        "risk_status": {"open_high_risks": open_high, "aged_high_risks": aged_high},
        "conformity_assessed": system.conformity_assessed,
        "separation_of_duties_block": separation_block,
        "deployment_allowed": allowed,
    }


@router.post("/ai-systems/{system_id}/deploy")
def deploy_ai_system(
    system_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    system = get_org_scoped_system(system_id, current_user, db)
    check_deployment_readiness(system, db, current_user)

    system.lifecycle_stage = "production"
    db.commit()
    db.refresh(system)

    create_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        entity_type="ai_system",
        entity_id=system.id,
        action="deployed",
        details=f"System deployed to production by {current_user.username}",
        performed_by=current_user.username,
    )

    return {
        "system_id": system.id,
        "status": "production",
        "deployed_by": current_user.username,
    }


# -------------------------
# AI RISKS
# -------------------------

@router.post("/ai-risks", response_model=AIRiskResponse)
def create_ai_risk(
    risk: AIRiskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    system = get_org_scoped_system(risk.ai_system_id, current_user, db)

    db_risk = AIRisk(
        title=risk.title,
        description=risk.description,
        risk_level=risk.risk_level,
        mitigation=risk.mitigation,
        ai_system_id=system.id,
    )
    db.add(db_risk)
    db.commit()
    db.refresh(db_risk)
    return db_risk


@router.delete("/ai-risks/{risk_id}")
def delete_ai_risk(
    risk_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    risk = get_org_scoped_risk(risk_id, current_user, db)

    if risk.risk_level == "high" and not current_user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="High-risk records are immutable. Super-admin required.",
        )

    risk.is_deleted = True
    db.commit()
    return {"message": "Risk deleted"}


# -------------------------
# CORRECTIVE ACTIONS
# -------------------------

@router.post("/corrective-actions", response_model=CorrectiveActionResponse)
def create_corrective_action(
    action: CorrectiveActionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_org_scoped_risk(action.ai_risk_id, current_user, db)

    db_action = CorrectiveAction(**action.dict())
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    return db_action


@router.put("/corrective-actions/{action_id}/status")
def update_corrective_action_status(
    action_id: int,
    update: CorrectiveActionStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    action = get_org_scoped_action(action_id, current_user, db)

    if update.new_status not in ["open", "in_progress", "closed"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    if not update.reason or update.reason.strip() == "":
        raise HTTPException(status_code=400, detail="Justification required")

    action.status = update.new_status
    db.commit()

    return {"action_id": action.id, "new_status": action.status}


# -------------------------
# PRODUCTION APPROVALS
# -------------------------

@router.post("/production-approvals/{system_id}")
def approve_production(
    system_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    system = get_org_scoped_system(system_id, current_user, db)

    approval = ProductionApproval(
        ai_system_id=system.id,
        approved_by_user_id=current_user.id,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)

    return {
        "system_id": system.id,
        "approved_by": current_user.username,
        "timestamp": approval.timestamp,
    }


# -------------------------
# AI POLICY
# -------------------------

@router.post("/ai-policy", response_model=AIPolicyResponse)
def generate_ai_policy(
    policy: AIPolicyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = get_org_scoped_org(policy.organization_id, current_user, db)

    generated_policy = AIPolicy(
        purpose=f"The organization {org.name} uses AI responsibly.",
        principles="Transparency, Human Oversight, Risk-Based Control.",
        risk_commitment="All AI systems undergo risk assessment.",
        monitoring_commitment="AI systems are continuously monitored.",
        organization_id=org.id,
    )
    db.add(generated_policy)
    db.commit()
    db.refresh(generated_policy)

    create_audit_log(
        db=db,
        organization_id=org.id,
        entity_type="ai_policy",
        entity_id=generated_policy.id,
        action="created",
        details=f"AI policy generated by {current_user.username}",
        performed_by=current_user.username,
    )

    return generated_policy


# -------------------------
# EVIDENCE
# -------------------------

@router.post("/evidence")
def create_evidence(
    evidence_data: EvidenceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if evidence_data.ai_system_id:
        get_org_scoped_system(evidence_data.ai_system_id, current_user, db)

    if evidence_data.ai_risk_id:
        get_org_scoped_risk(evidence_data.ai_risk_id, current_user, db)

    evidence = Evidence(**evidence_data.dict())
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    return {"evidence_id": evidence.id, "title": evidence.title}
