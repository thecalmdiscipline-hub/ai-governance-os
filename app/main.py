import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.audit import create_audit_log

# Load environment
load_dotenv()

# FastAPI app (slechts één keer)
app = FastAPI(
    title=os.getenv("APP_NAME", "AI Governance OS"),
    version=os.getenv("APP_VERSION", "0.1.0")
)

# Database setup
from app.db.session import engine, SessionLocal
from app.db.base import Base

from app.models import (
    Organization,
    AISystem,
    AIRisk,
    AIIncident,
    AuditLog,
    CorrectiveAction,
    AIPolicy,
    Evidence,
)

Base.metadata.create_all(bind=engine)

# Schemas
from app.schemas.organization import OrganizationCreate, OrganizationResponse
from app.schemas.ai_system import AISystemCreate, AISystemResponse, AISystemUpdate
from app.schemas.ai_risk import AIRiskCreate, AIRiskResponse
from app.schemas.ai_incident import AIIncidentCreate, AIIncidentResponse
from app.schemas.ai_policy import AIPolicyCreate, AIPolicyResponse
from app.schemas.evidence import EvidenceCreate

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Basic routes
@app.get("/")
def root():
    return {"status": "AI Governance OS running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

# -------------------------
# ORGANIZATIONS
# -------------------------

@app.post("/organizations", response_model=OrganizationResponse)
def create_organization(org: OrganizationCreate, db: Session = Depends(get_db)):
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
        details=f"Organization {db_org.name} created"
    )

    return db_org

# -------------------------
# AI SYSTEMS
# -------------------------

@app.post("/ai-systems", response_model=AISystemResponse)
def create_ai_system(system: AISystemCreate, db: Session = Depends(get_db)):
    db_system = AISystem(**system.dict())
    db.add(db_system)
    db.commit()
    db.refresh(db_system)
    return db_system

@app.delete("/ai-systems/{ai_system_id}")
def soft_delete_ai_system(ai_system_id: int, db: Session = Depends(get_db)):
    system = db.query(AISystem).filter(AISystem.id == ai_system_id).first()
    if not system:
        return {"error": "AI system not found"}
    system.is_deleted = True
    system.status = "archived"
    db.commit()
    return {"message": "AI system archived"}

# -------------------------
# AI RISKS
# -------------------------

@app.post("/ai-risks", response_model=AIRiskResponse)
def create_ai_risk(risk: AIRiskCreate, db: Session = Depends(get_db)):
    db_risk = AIRisk(**risk.dict())
    db.add(db_risk)
    db.commit()
    db.refresh(db_risk)
    return db_risk

# -------------------------
# AI INCIDENTS
# -------------------------

@app.post("/ai-incidents", response_model=AIIncidentResponse)
def create_ai_incident(incident: AIIncidentCreate, db: Session = Depends(get_db)):
    db_incident = AIIncident(**incident.dict())
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)
    return db_incident

# -------------------------
# POLICY
# -------------------------

@app.post("/ai-policy", response_model=AIPolicyResponse)
def generate_ai_policy(policy: AIPolicyCreate, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == policy.organization_id).first()
    if not org:
        return {"error": "Organization not found"}

    generated_policy = AIPolicy(
        purpose=f"The organization {org.name} uses AI responsibly.",
        principles="Transparency, Human Oversight, Risk-Based Control.",
        risk_commitment="All AI systems undergo risk assessment.",
        monitoring_commitment="AI systems are continuously monitored.",
        organization_id=org.id
    )

    db.add(generated_policy)
    db.commit()
    db.refresh(generated_policy)
    return generated_policy

# -------------------------
# EVIDENCE
# -------------------------

@app.post("/evidence")
def create_evidence(evidence_data: EvidenceCreate, db: Session = Depends(get_db)):
    evidence = Evidence(**evidence_data.dict())
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return {
        "evidence_id": evidence.id,
        "title": evidence.title,
        "linked_system": evidence.ai_system_id,
        "linked_risk": evidence.ai_risk_id
    }

# -------------------------
# GOVERNANCE UPDATE (ISO control)
# -------------------------

@app.patch("/ai-systems/{system_id}/governance")
def update_ai_system_governance(
    system_id: int,
    update: AISystemUpdate,
    db: Session = Depends(get_db)
):
    system = db.query(AISystem).filter(AISystem.id == system_id).first()

    if not system:
        return {"error": "AI System not found"}

    if update.risk_category is not None:
        system.risk_category = update.risk_category

    if update.lifecycle_stage is not None:
        system.lifecycle_stage = update.lifecycle_stage

    if update.conformity_assessed is not None:
        system.conformity_assessed = update.conformity_assessed

    if update.last_reviewed_at is not None:
        system.last_reviewed_at = update.last_reviewed_at

    db.commit()
    db.refresh(system)

    return {
        "system_id": system.id,
        "risk_category": system.risk_category,
        "lifecycle_stage": system.lifecycle_stage,
        "conformity_assessed": system.conformity_assessed,
        "last_reviewed_at": system.last_reviewed_at
    }
# -------------------------
# ISO 42001 GOVERNANCE SCORE
# -------------------------

@app.get("/organizations/{organization_id}/iso-score")
def iso_governance_score(
    organization_id: int,
    db: Session = Depends(get_db)
):

    org = db.query(Organization).filter(
        Organization.id == organization_id
    ).first()

    if not org:
        return {"error": "Organization not found"}

    # High risks scoped per organization
    high_risks = db.query(AIRisk).join(AISystem).filter(
        AISystem.organization_id == organization_id,
        AIRisk.risk_level == "high",
        AIRisk.is_deleted == False
    ).all()

    effective_high = 0

    for risk in high_risks:
        action = db.query(CorrectiveAction).filter(
            CorrectiveAction.ai_risk_id == risk.id,
            CorrectiveAction.status == "closed"
        ).first()

        if not action:
            effective_high += 1

    # Medium risks scoped per organization
    medium_risks = db.query(AIRisk).join(AISystem).filter(
        AISystem.organization_id == organization_id,
        AIRisk.risk_level == "medium",
        AIRisk.is_deleted == False
    ).count()

    # Incidents scoped per organization
    open_incidents = db.query(AIIncident).join(AISystem).filter(
        AISystem.organization_id == organization_id,
        AIIncident.is_deleted == False
    ).count()

    score = 100
    score -= effective_high * 20
    score -= medium_risks * 10
    score -= open_incidents * 5

    if score < 0:
        score = 0

    readiness_level = "High"
    if score < 75:
        readiness_level = "Moderate"
    if score < 50:
        readiness_level = "Low"

    return {
        "organization_id": organization_id,
        "effective_high_risks": effective_high,
        "medium_risks": medium_risks,
        "open_incidents": open_incidents,
        "iso_42001_score": score,
        "readiness_level": readiness_level
    }
# -------------------------
# UPDATE CORRECTIVE ACTION STATUS
# -------------------------

@app.put("/corrective-actions/{action_id}/status")
def update_corrective_action_status(
    action_id: int,
    new_status: str,
    db: Session = Depends(get_db)
):

    action = db.query(CorrectiveAction).filter(
        CorrectiveAction.id == action_id
    ).first()

    if not action:
        return {"error": "Action not found"}

    if new_status not in ["open", "in_progress", "closed"]:
        return {"error": "Invalid status"}

    action.status = new_status
    db.commit()

    return {
        "action_id": action.id,
        "new_status": action.status
    }