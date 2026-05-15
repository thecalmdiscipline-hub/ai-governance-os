import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user, get_org_scoped_org
from app.core.audit import generate_hmac_signature
from app.models.user import User
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/audit", tags=["Audit"])
org_audit_router = APIRouter(tags=["Audit"])


@router.get("")
def get_audit_logs(
    limit: int = Query(default=20, ge=1, le=200),
    entity_type: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    q = db.query(AuditLog).filter(
        AuditLog.organization_id == current_user.organization_id
    )

    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)

    if action:
        q = q.filter(AuditLog.action == action)

    rows = q.order_by(AuditLog.id.desc()).limit(limit).all()

    items = []
    for row in rows:
        items.append({
            "id": row.id,
            "organization_id": row.organization_id,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "action": row.action,
            "performed_by": row.performed_by,
            "details": row.details,
            "timestamp": row.timestamp.isoformat() if row.timestamp else "",
            "previous_hash": row.previous_hash,
            "record_hash": row.record_hash,
        })

    return {
        "status": "ok",
        "total": len(items),
        "items": items,
    }


@router.get("/verify")
def verify_audit_chain(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == current_user.organization_id)
        .order_by(AuditLog.id.asc())
        .all()
    )

    previous_hash = None
    expected_id = logs[0].id if logs else 1

    for log in logs:
        if log.id != expected_id:
            return {
                "status": "compromised",
                "log_id": log.id,
                "message": "Audit ID sequence broken",
            }

        expected_id += 1

        raw_string = (
            f"{log.organization_id}{log.entity_type}{log.entity_id}"
            f"{log.action}{log.details}{log.performed_by}"
            f"{log.timestamp}{log.previous_hash}"
        )
        recalculated_hash = hashlib.sha256(raw_string.encode()).hexdigest()

        if log.record_hash and log.record_hash != recalculated_hash:
            return {
                "status": "compromised",
                "log_id": log.id,
                "message": "Hash mismatch detected",
            }

        if log.previous_hash != previous_hash:
            if log.previous_hash is not None:
                return {
                    "status": "compromised",
                    "log_id": log.id,
                    "message": "Broken hash chain detected",
                }

        previous_hash = log.record_hash

    return {"status": "valid", "message": "Audit chain integrity verified"}


@org_audit_router.get("/organizations/{organization_id}/audit-export")
def audit_export(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = get_org_scoped_org(organization_id, current_user, db)

    logs = db.query(AuditLog).filter(
        AuditLog.organization_id == org.id
    ).order_by(AuditLog.id.asc()).all()

    export = [
        {
            "id": log.id,
            "entity_type": log.entity_type,
            "action": log.action,
            "details": log.details,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "previous_hash": log.previous_hash,
            "record_hash": log.record_hash,
        }
        for log in logs
    ]

    chain_hash = export[-1]["record_hash"] if export else None
    export_payload = {
        "organization_id": org.id,
        "total_records": len(export),
        "chain_hash": chain_hash,
        "audit_chain": export,
    }

    export_signature = generate_hmac_signature(json.dumps(export_payload, sort_keys=True))

    return {"export": export_payload, "export_signature": export_signature}
