"""Audit logging for control-plane (/ops) actions: two lines, in two chains.

Every ops action is recorded in the audit chain of tenant 0 (HQ), and, when it concerns a
customer tenant, also in that tenant's own chain, so the customer can see that Valqeron staff
acted on their tenant. Both go through create_audit_log (HMAC chain per organization).
No secrets or customer content belong in `details`.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.core.audit import create_audit_log
from app.core.config import get_hq_organization_id
from app.models.user import User


def log_ops_action(
    db: Session,
    actor: Optional[User],
    action: str,
    target_org_id: Optional[int] = None,
    details: str = "",
    performed_by: Optional[str] = None,
) -> None:
    # `performed_by` overrides the actor's username (used by server-side scripts, e.g. "system:provision_cli").
    who = performed_by or (actor.username if actor is not None else "system")
    hq_org_id = get_hq_organization_id()
    if hq_org_id is None:
        raise RuntimeError("HQ_ORGANIZATION_ID is not configured; cannot write ops audit lines")

    target_part = f" on organization {target_org_id}" if target_org_id is not None else ""
    suffix = f": {details}" if details else ""

    create_audit_log(
        db,
        organization_id=hq_org_id,
        entity_type="ops",
        entity_id=target_org_id if target_org_id is not None else 0,
        action=action,
        details=f"{action} by {who}{target_part}{suffix}",
        performed_by=who,
    )

    if target_org_id is not None and target_org_id != hq_org_id:
        create_audit_log(
            db,
            organization_id=target_org_id,
            entity_type="ops_access",
            entity_id=hq_org_id,
            action=action,
            details=f"Valqeron HQ operator {who} performed {action}{suffix}",
            performed_by=who,
        )
