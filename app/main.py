# pyright: reportArgumentType=false
# pyright: reportOptionalMemberAccess=false


import hashlib
import os
import json
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import create_audit_log, generate_hmac_signature
from app.core.deployment_service import check_deployment_readiness
from app.core.rate_limiter import rate_limit_login
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.workflows.routers import router as workflows_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

security_logger = logging.getLogger("security")

# Load environment
load_dotenv()

# FastAPI app (slechts één keer)
app = FastAPI(
    title=os.getenv("APP_NAME", "AI Governance OS"),
    version=os.getenv("APP_VERSION", "0.1.0")
)

# Workflows router registreren
app.include_router(workflows_router)

login_attempts = defaultdict(list)

def check_login_rate_limit(request: Request):
    ip = request.client.host
    now = time.time()

    # Verwijder oude pogingen (ouder dan 60 sec)
    login_attempts[ip] = [
        t for t in login_attempts[ip] if now - t < 60
    ]

    if len(login_attempts[ip]) >= 5:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later."
        )

    login_attempts[ip].append(now)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later beperken naar je echte domein
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

    return response

from fastapi.responses import JSONResponse
from fastapi import Request
import logging

logger = logging.getLogger("uvicorn.error")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred."
        },
    )

# Database setup
from app.db.session import engine, SessionLocal
from app.db.base import Base
from app.models.user import User

from app.models import (
    Organization,
    AISystem,
    AIRisk,
    AIIncident,
    AuditLog,
    CorrectiveAction,
    AIPolicy,
    Evidence,
    ProductionApproval,
    User,
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

        # -------------------------
# SIMPLE RBAC DEPENDENCY
# -------------------------

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.core.security import SECRET_KEY, ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

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

        username: str = payload.get("sub")
        org_id: int = payload.get("org_id")

        if username is None or org_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(
        User.username == username,
        User.organization_id == org_id
    ).first()

    if user is None:
        raise credentials_exception

    return user

def require_role(required_role: str):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker


    system = db.query(AISystem).filter(
        AISystem.id == system_id,
        AISystem.organization_id == current_user.organization_id
    ).first()

    if not system:
        raise HTTPException(
            status_code=404,
            detail="AI System not found"
        )

    return system

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
        raise HTTPException(status_code=404, detail="Risk not found")

    return risk

def get_org_scoped_org(organization_id: int, current_user: User, db: Session):
    org = db.query(Organization).filter(
        Organization.id == organization_id,
        Organization.id == current_user.organization_id
    ).first()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return org

# Import routers (direct imports; avoid app.api __init__ circular imports)
from app.api import workflows

# Basic routes
@app.get("/")
def root():
    return {"status": "AI Governance OS running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

app.include_router(workflows.router)

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
        organization_id=(db_org.id),
        entity_type="organization",
        entity_id=(db_org.id),
        action="created",
        details=f"Organization {db_org.name} created"
    )

    return db_org

from pydantic import BaseModel
import json

class GovernanceConfigUpdate(BaseModel):
    required_production_approvals: Optional[int] = None
    max_review_age_days: Optional[int] = None


@app.patch("/organizations/{organization_id}/governance-config")
def update_governance_config(
    organization_id: int,
    config: GovernanceConfigUpdate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):

    org = db.query(Organization).filter(
        Organization.id == organization_id
    ).first()

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
        performed_by=current_user.username
    )

    return {
        "organization_id": org.id,
        "required_production_approvals": org.required_production_approvals,
        "max_review_age_days": org.max_review_age_days
    }

# -------------------------
# AI SYSTEMS
# -------------------------

@app.post("/ai-systems", response_model=AISystemResponse)
def create_ai_system(
    system: AISystemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_system = AISystem(
        **system.dict(exclude={"organization_id"}),
        organization_id=current_user.organization_id
    )

    db.add(db_system)
    db.commit()
    db.refresh(db_system)

    return db_system


@app.delete("/ai-systems/{ai_system_id}")
def soft_delete_ai_system(
    ai_system_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
        performed_by=current_user.username
    )

    return {"message": "AI system archived"}
# -------------------------
# AI RISKS
# -------------------------

@app.post("/ai-risks", response_model=AIRiskResponse)
def create_ai_risk(
    risk: AIRiskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 🔒 Tenant check
    system = get_org_scoped_system(risk.ai_system_id, current_user, db)

    db_risk = AIRisk(
        title=risk.title,
        description=risk.description,
        risk_level=risk.risk_level,
        mitigation=risk.mitigation,
        ai_system_id=system.id
    )

    db.add(db_risk)
    db.commit()
    db.refresh(db_risk)

    return db_risk

# -------------------------
# DELETE AI RISK (IMMUTABLE LOCK)
# -------------------------

@app.delete("/ai-risks/{risk_id}")
def delete_ai_risk(
    risk_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    risk = get_org_scoped_risk(risk_id, current_user, db)

    if risk.risk_level == "high" and not current_user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="High-risk records are immutable. Super-admin required."
        )

    risk.is_deleted = True
    db.commit()

    return {"message": "Risk deleted"}

# -------------------------
# CORRECTIVE ACTIONS
# -------------------------

from app.schemas.corrective_action import CorrectiveActionCreate, CorrectiveActionResponse

@app.post("/corrective-actions", response_model=CorrectiveActionResponse)
def create_corrective_action(
    action: CorrectiveActionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    risk = get_org_scoped_risk(action.ai_risk_id, current_user, db)

    db_action = CorrectiveAction(
        **action.dict()
    )

    db.add(db_action)
    db.commit()
    db.refresh(db_action)

    return db_action

# -------------------------
# POLICY
# -------------------------

@app.post("/ai-policy", response_model=AIPolicyResponse)
def generate_ai_policy(
    policy: AIPolicyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 🔒 Tenant isolation
    org = get_org_scoped_org(policy.organization_id, current_user, db)

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

    create_audit_log(
        db=db,
        organization_id=org.id,
        entity_type="ai_policy",
        entity_id=generated_policy.id,
        action="created",
        details=f"AI policy generated by {current_user.username}",
        performed_by=current_user.username
    )

    return generated_policy

# -------------------------
# EVIDENCE
# -------------------------

@app.post("/evidence")
def create_evidence(
    evidence_data: EvidenceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if evidence_data.ai_system_id:
        get_org_scoped_system(evidence_data.ai_system_id, current_user, db)

    if evidence_data.ai_risk_id:
        get_org_scoped_risk(evidence_data.ai_risk_id, current_user, db)

    evidence = Evidence(**evidence_data.dict())

    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    return {
        "evidence_id": evidence.id,
        "title": evidence.title
    }

# -------------------------
# GOVERNANCE UPDATE (ISO control + enforcement)
# -------------------------

from datetime import datetime, timedelta



@app.patch("/ai-systems/{system_id}/governance")
def update_ai_system_governance(
    system_id: int,
    update: AISystemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    system = get_org_scoped_system(system_id, current_user, db)
    # 🔒 Mandatory justification
    if not update.reason or update.reason.strip() == "":
        raise HTTPException(status_code=400, detail="Justification reason is required")

    # 🔒 Admin-only production control
    if update.lifecycle_stage == "production" and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin users can move system to production")

    # 🔒 High-risk production gate
    if update.lifecycle_stage == "production":

        high_risks = db.query(AIRisk).filter(
            AIRisk.ai_system_id == system.id,
            AIRisk.risk_level == "high",
            AIRisk.is_deleted == False
        ).all()

        # 🔒 Separation of Duties Enforcement
        last_approval = db.query(ProductionApproval).filter(
            ProductionApproval.ai_system_id == system.id
        ).order_by(ProductionApproval.timestamp.desc()).first()

        if last_approval is not None:
            if int(last_approval.approved_by_user_id) == int(current_user.id):
                raise HTTPException(
                    status_code=403,
                    detail="Separation of duties violation. Approver cannot deploy."
                )

        for risk in high_risks:

            action = db.query(CorrectiveAction).filter(
                CorrectiveAction.ai_risk_id == risk.id,
                CorrectiveAction.status == "closed"
            ).first()

            if not action:
                raise HTTPException(
                    status_code=400,
                    detail=f"Open high risk '{risk.title}' requires closed corrective action before production"
                )

            if risk.created_at and risk.created_at < datetime.utcnow() - timedelta(days=30):
                raise HTTPException(
                    status_code=400,
                    detail=f"Aged high risk '{risk.title}' blocks production deployment"
                )

        if not update.conformity_assessed:
            raise HTTPException(
                status_code=400,
                detail="High-risk systems require conformity assessment before production"
            )

        org = db.query(Organization).filter(
            Organization.id == system.organization_id
        ).first()

        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        required = org.required_production_approvals or 1

        count = db.query(ProductionApproval).filter(
            ProductionApproval.ai_system_id == system.id
        ).count()

        if count < required:
            raise HTTPException(
                status_code=400,
                detail=f"{required} production approvals required. Current: {count}"
            )
        
    

    # -------------------------
    # APPLY UPDATES
    # -------------------------

    if update.risk_category is not None:
        system.risk_category = update.risk_category

    if update.lifecycle_stage is not None:
        system.lifecycle_stage = update.lifecycle_stage

    if update.conformity_assessed is not None:
        system.conformity_assessed = update.conformity_assessed

    if update.last_reviewed_at is not None:
        system.last_reviewed_at = update.last_reviewed_at

    # -------------------------
    # PERIODIC REVIEW ENFORCEMENT
    # -------------------------

    org = db.query(Organization).filter(
        Organization.id == system.organization_id
    ).first()

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
                performed_by="system"
            )

    # -------------------------
    # COMMIT
    # -------------------------

    db.commit()
    db.refresh(system)

    # -------------------------
    # FORENSIC GOVERNANCE LOG
    # -------------------------

    create_audit_log(
        db=db,
        organization_id=int(current_user.organization_id),
        entity_type="ai_system",
        entity_id=int(system.id),
        action="governance_updated",
        details=f"Governance updated by user {current_user.username}. Reason: {update.reason}",
        performed_by=current_user.username
    )

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

from datetime import datetime, timedelta
from app.models import AIIncident

def get_org_scoped_org(org_id: int, current_user: User, db: Session):
    org = db.query(Organization).filter(
        Organization.id == org_id,
        Organization.id == current_user.organization_id
    ).first()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return org

@app.get("/organizations/{organization_id}/iso-score")
def iso_governance_score(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org = get_org_scoped_org(organization_id, current_user, db)

    high_risks = db.query(AIRisk).join(AISystem).filter(
        AISystem.organization_id == org.id,
        AIRisk.risk_level == "high",
        AIRisk.is_deleted == False
    ).all()

    effective_high = 0
    aged_high = 0

    for risk in high_risks:
        action = db.query(CorrectiveAction).filter(
            CorrectiveAction.ai_risk_id == risk.id,
            CorrectiveAction.status == "closed"
        ).first()

        if not action:
            effective_high += 1

            if risk.created_at and risk.created_at < datetime.utcnow() - timedelta(days=30):
                aged_high += 1

    medium_risks = db.query(AIRisk).join(AISystem).filter(
        AISystem.organization_id == org.id,
        AIRisk.risk_level == "medium",
        AIRisk.is_deleted == False
    ).count()

    open_incidents = db.query(AIIncident).join(AISystem).filter(
        AISystem.organization_id == org.id,
        AIIncident.is_deleted == False
    ).count()

    score = 100
    score -= (effective_high - aged_high) * 20
    score -= aged_high * 35
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
        "organization_id": org.id,
        "effective_high_risks": effective_high,
        "aged_high_risks": aged_high,
        "medium_risks": medium_risks,
        "open_incidents": open_incidents,
        "iso_42001_score": score,
        "readiness_level": readiness_level
    }

@app.get("/organizations/{organization_id}/governance-snapshot")
def governance_snapshot(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Tenant-safe organization ophalen
    org = get_org_scoped_org(organization_id, current_user, db)

    # Alleen systemen van deze organisatie
    systems = db.query(AISystem).filter(
        AISystem.organization_id == org.id,
        AISystem.is_deleted == False
    ).all()

    total_systems = len(systems)

    production = 0
    restricted = 0
    other = 0

    for s in systems:
        if s.lifecycle_stage == "production":
            production += 1
        elif s.lifecycle_stage == "restricted":
            restricted += 1
        else:
            other += 1

    # High risks scoped op organisatie
    high_risks = db.query(AIRisk).join(AISystem).filter(
        AISystem.organization_id == org.id,
        AIRisk.risk_level == "high",
        AIRisk.is_deleted == False
    ).all()

    aged_high = 0

    for risk in high_risks:
        if risk.created_at and risk.created_at < datetime.utcnow() - timedelta(days=30):
            aged_high += 1

    approvals_required = org.required_production_approvals or 1

    maturity_score = 100

    if restricted > 0:
        maturity_score -= 10

    if aged_high > 0:
        maturity_score -= 20

    if len(high_risks) > 0:
        maturity_score -= 10

    if maturity_score < 0:
        maturity_score = 0

    return {
        "organization_id": org.id,
        "systems": {
            "total": total_systems,
            "production": production,
            "restricted": restricted,
            "other": other
        },
        "risk_exposure": {
            "high_risks": len(high_risks),
            "aged_high_risks": aged_high
        },
        "approval_policy": {
            "required_production_approvals": approvals_required
        },
        "audit_integrity": "valid",
        "governance_maturity_percentage": maturity_score
    }

@app.get("/ai-systems/{system_id}/readiness-check")
def production_readiness_check(
    system_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # 🔒 Tenant-safe system ophalen
    system = get_org_scoped_system(system_id, current_user, db)

    # 🔒 Tenant-safe organisatie ophalen
    org = get_org_scoped_org(system.organization_id, current_user, db)

    required = org.required_production_approvals or 1

    approvals = db.query(ProductionApproval).filter(
        ProductionApproval.ai_system_id == system.id
    ).all()

    approval_count = len(approvals)

    high_risks = db.query(AIRisk).filter(
        AIRisk.ai_system_id == system.id,
        AIRisk.risk_level == "high",
        AIRisk.is_deleted == False
    ).all()

    open_high = 0
    aged_high = 0

    for risk in high_risks:
        action = db.query(CorrectiveAction).filter(
            CorrectiveAction.ai_risk_id == risk.id,
            CorrectiveAction.status == "closed"
        ).first()

        if not action:
            open_high += 1

        if risk.created_at and risk.created_at < datetime.utcnow() - timedelta(days=30):
            aged_high += 1

    separation_block = False

    if approvals:
        last_approval = approvals[-1]
        if int(last_approval.approved_by_user_id) == int(current_user.id):
            separation_block = True

    allowed = True

    if approval_count < required:
        allowed = False

    if open_high > 0:
        allowed = False

    if aged_high > 0:
        allowed = False

    if not system.conformity_assessed:
        allowed = False

    if separation_block:
        allowed = False

    return {
        "system_id": system.id,
        "approvals": {
            "current": approval_count,
            "required": required
        },
        "risk_status": {
            "open_high_risks": open_high,
            "aged_high_risks": aged_high
        },
        "conformity_assessed": system.conformity_assessed,
        "separation_of_duties_block": separation_block,
        "deployment_allowed": allowed
    }

@app.get("/organizations/{organization_id}/audit-export")
def audit_export(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org = get_org_scoped_org(organization_id, current_user, db)

    from app.models import AuditLog
    from app.core.audit import generate_hmac_signature
    import json

    logs = db.query(AuditLog).filter(
        AuditLog.organization_id == org.id
    ).order_by(AuditLog.id.asc()).all()

    export = []

    for log in logs:
        export.append({
            "id": log.id,
            "entity_type": log.entity_type,
            "action": log.action,
            "details": log.details,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "previous_hash": log.previous_hash,
            "record_hash": log.record_hash
        })

    chain_hash = export[-1]["record_hash"] if export else None

    export_payload = {
        "organization_id": org.id,
        "total_records": len(export),
        "chain_hash": chain_hash,
        "audit_chain": export
    }

    payload_string = json.dumps(export_payload, sort_keys=True)
    export_signature = generate_hmac_signature(payload_string)

    return {
        "export": export_payload,
        "export_signature": export_signature
    }

# -------------------------
# UPDATE CORRECTIVE ACTION STATUS
# -------------------------

from app.schemas.corrective_action import CorrectiveActionStatusUpdate


@app.put("/corrective-actions/{action_id}/status")
def update_corrective_action_status(
    action_id: int,
    update: CorrectiveActionStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    action = get_org_scoped_action(action_id, current_user, db)

    if update.new_status not in ["open", "in_progress", "closed"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    if not update.reason or update.reason.strip() == "":
        raise HTTPException(status_code=400, detail="Justification required")

    action.status = update.new_status
    db.commit()

    return {
        "action_id": action.id,
        "new_status": action.status
    }

@app.get("/audit/verify")
def verify_audit_chain(db: Session = Depends(get_db)):

    logs = db.query(AuditLog).order_by(AuditLog.id.asc()).all()

    previous_hash = None
    expected_id = 1

    for log in logs:

        if log.id != expected_id:
            return {
                "status": "compromised",
                "log_id": log.id,
                "message": "Audit ID sequence broken"
        }

        expected_id += 1

        raw_string = f"{log.organization_id}{log.entity_type}{log.entity_id}{log.action}{log.details}{log.performed_by}{log.timestamp}{log.previous_hash}"
        recalculated_hash = hashlib.sha256(raw_string.encode()).hexdigest()

        if log.record_hash and log.record_hash != recalculated_hash:
            return {
                "status": "compromised",
                "log_id": log.id,
                "message": "Hash mismatch detected"
            }

        if log.previous_hash != previous_hash:
            if log.previous_hash is not None:
                return {
                    "status": "compromised",
                    "log_id": log.id,
                    "message": "Broken hash chain detected"
                }

        previous_hash = log.record_hash

    return {"status": "valid", "message": "Audit chain integrity verified"}

# -------------------------
# PRODUCTION APPROVAL
# -------------------------

@app.post("/production-approvals/{system_id}")
def approve_production(
    system_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    system = get_org_scoped_system(system_id, current_user, db)

    approval = ProductionApproval(
        ai_system_id=system.id,
        approved_by_user_id=current_user.id
    )

    db.add(approval)
    db.commit()
    db.refresh(approval)

    return {
        "system_id": system.id,
        "approved_by": current_user.username,
        "timestamp": approval.timestamp
    }

@app.post("/ai-systems/{system_id}/deploy")
def deploy_ai_system(
    system_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    # 🔒 Tenant isolation
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
        performed_by=current_user.username
    )

    return {
        "system_id": system.id,
        "status": "production",
        "deployed_by": current_user.username
    }

from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends, HTTPException

@app.post("/login", dependencies=[Depends(rate_limit_login)])
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    check_login_rate_limit(request)   

    
    error = HTTPException(status_code=401, detail="Invalid credentials")

    user = db.query(User).filter(
        User.username == form_data.username
    ).first()

    # Geen user → generieke fout
    if not user:
        security_logger.warning(f"Failed login attempt for username: {form_data.username}")
        raise error

    # Account locked?
    if user.account_locked_until and user.account_locked_until > datetime.utcnow():
        raise error

    # Wachtwoord fout
    if not verify_password(form_data.password, user.password_hash):

        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

        if user.failed_login_attempts >= 5:
            user.account_locked_until = datetime.utcnow() + timedelta(minutes=15)
            security_logger.warning(f"Invalid password attempt for user: {user.username}")
        db.commit()
        raise error

    # Succes → reset counters
    user.failed_login_attempts = 0
    user.account_locked_until = None
    db.commit()

    access_token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role,
            "org_id": user.organization_id
        }
    )

    security_logger.info(f"Successful login for user: {user.username}")

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }