from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from datetime import datetime


def create_audit_log(
    db: Session,
    organization_id: int,
    entity_type: str,
    entity_id: int,
    action: str,
    performed_by: str = "system",
    details: str = None,
):
    log = AuditLog(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        performed_by=performed_by,
        timestamp=datetime.utcnow(),
        details=details,
    )

    db.add(log)
    db.commit()