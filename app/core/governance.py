from datetime import datetime, timedelta
from app.models import AIRisk, AISystem, CorrectiveAction
from app.core.audit import create_audit_log


def enforce_production_integrity(db, system, user):

    if system.lifecycle_stage != "production":
        return

    high_risks = db.query(AIRisk).filter(
        AIRisk.ai_system_id == system.id,
        AIRisk.risk_level == "high",
        AIRisk.is_deleted == False
    ).all()

    risk_ids = [r.id for r in high_risks]
    closed_risk_ids = {
        row.ai_risk_id
        for row in db.query(CorrectiveAction.ai_risk_id)
        .filter(
            CorrectiveAction.ai_risk_id.in_(risk_ids),
            CorrectiveAction.status == "closed",
        )
        .all()
    }

    for risk in high_risks:
        # Open high risk
        if risk.id not in closed_risk_ids:
            system.lifecycle_stage = "restricted"
            db.commit()

            create_audit_log(
                db=db,
                organization_id=system.organization_id,
                entity_type="ai_system",
                entity_id=system.id,
                action="auto_rollback",
                details=f"System rolled back due to open high risk '{risk.title}'",
                performed_by="system"
            )
            return

        # Aged high risk
        if risk.created_at and risk.created_at < datetime.utcnow() - timedelta(days=30):
            system.lifecycle_stage = "restricted"
            db.commit()

            create_audit_log(
                db=db,
                organization_id=system.organization_id,
                entity_type="ai_system",
                entity_id=system.id,
                action="auto_rollback",
                details=f"System rolled back due to aged high risk '{risk.title}'",
                performed_by="system"
            )
            return