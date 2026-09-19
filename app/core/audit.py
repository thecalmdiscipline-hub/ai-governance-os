import os
import hmac
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from app.models import AuditLog
from app.models.organization import Organization

load_dotenv()

AUDIT_SECRET = os.getenv("AUDIT_SECRET_KEY")

# Marker row that starts the per-organization ("v2") audit chain — see
# verify_audit_chain() in app/api/audit.py and CLAUDE.md sectie 5/6 for the
# full story. Before this marker existed, create_audit_log() chained
# previous_hash off the globally-last row across ALL organizations, not
# this organization's own last row, which made per-organization
# verification impossible for any organization that wasn't first to ever
# write a log. Rows before the marker ("legacy") are still individually
# HMAC-verifiable, just not chain-linkable to each other from this
# organization's point of view — no schema change, no rewriting history.
CHAIN_V2_ENTITY_TYPE = "audit_chain"
CHAIN_V2_ACTION = "chain_v2_started"
CHAIN_V2_ENTITY_ID = 0
CHAIN_V2_DETAILS = (
    "Per-organization audit chain (v2) started; earlier records belong "
    "to the legacy global chain"
)


def generate_hmac_signature(data_string: str) -> str:
    if not AUDIT_SECRET:
        raise RuntimeError(
            "AUDIT_SECRET_KEY is not configured. "
            "Audit chain integrity cannot be guaranteed without a secret key. "
            "Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return hmac.new(
        AUDIT_SECRET.encode(),
        data_string.encode(),
        hashlib.sha256,
    ).hexdigest()


def _insert_log_row(db, organization_id, entity_type, entity_id, action, details, performed_by, previous_hash):
    timestamp = datetime.utcnow()
    raw_string = f"{organization_id}{entity_type}{entity_id}{action}{details}{performed_by}{timestamp}{previous_hash}"
    record_hash = generate_hmac_signature(raw_string)

    row = AuditLog(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        performed_by=performed_by,
        timestamp=timestamp,
        details=details,
        previous_hash=previous_hash,
        record_hash=record_hash,
    )
    db.add(row)
    db.flush()
    return row


def create_audit_log(
    db,
    organization_id: int,
    entity_type: str,
    entity_id: int,
    action: str,
    details: str,
    performed_by: str = "system"
):
    # Row-lock the organization so two concurrent writers for the same
    # organization can't both read the same "last row" and fork the
    # chain. FOR UPDATE is a no-op on SQLite (fine for tests); the real
    # protection is on Postgres in production.
    db.query(Organization).filter(Organization.id == organization_id).with_for_update().first()

    marker_exists = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == organization_id,
            AuditLog.entity_type == CHAIN_V2_ENTITY_TYPE,
            AuditLog.action == CHAIN_V2_ACTION,
        )
        .first()
    )

    if marker_exists is None:
        _insert_log_row(
            db,
            organization_id=organization_id,
            entity_type=CHAIN_V2_ENTITY_TYPE,
            entity_id=CHAIN_V2_ENTITY_ID,
            action=CHAIN_V2_ACTION,
            details=CHAIN_V2_DETAILS,
            performed_by="system",
            previous_hash=None,
        )

    last_log = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    previous_hash = last_log.record_hash if last_log else None

    _insert_log_row(
        db,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        details=details,
        performed_by=performed_by,
        previous_hash=previous_hash,
    )

    db.commit()
