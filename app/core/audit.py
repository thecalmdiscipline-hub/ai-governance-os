import os
import hmac
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from app.models import AuditLog
load_dotenv()

AUDIT_SECRET = os.getenv("AUDIT_SECRET_KEY")


def generate_hmac_signature(data_string: str):
    return hmac.new(
        AUDIT_SECRET.encode(),
        data_string.encode(),
        hashlib.sha256
    ).hexdigest()


def create_audit_log(
    db,
    organization_id: int,
    entity_type: str,
    entity_id: int,
    action: str,
    details: str,
    performed_by: str = "system"
):
    last_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()

    previous_hash = last_log.record_hash if last_log else None

    timestamp = datetime.utcnow()

    raw_string = f"{organization_id}{entity_type}{entity_id}{action}{details}{performed_by}{timestamp}{previous_hash}"

    # HMAC signed hash
    record_hash = generate_hmac_signature(raw_string)

    new_log = AuditLog(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        performed_by=performed_by,
        timestamp=timestamp,
        details=details,
        previous_hash=previous_hash,
        record_hash=record_hash
    )

    db.add(new_log)
    db.commit()