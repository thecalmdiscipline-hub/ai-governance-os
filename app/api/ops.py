"""Control plane (/ops): only for a super-admin of the HQ tenant who logged in with MFA.

Batch E: whoami. Batch F: tenant overview and module management (tier rules live in
app/services/tenant_modules.py), and provisioning (app/api/ops_provisioning.py).
Every write goes through log_ops_action (one line in the HQ chain, one in the target tenant's chain).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_ops_access
from app.core.ops_audit import log_ops_action
from app.models.organization import Organization
from app.models.tenant_module import TenantModule
from app.models.user import User
from app.services import tenant_modules as tm

router = APIRouter(prefix="/ops", tags=["Ops"], dependencies=[Depends(require_ops_access)])


@router.get("/whoami")
def whoami(current_user: User = Depends(require_ops_access), db: Session = Depends(get_db)):
    log_ops_action(db, current_user, "ops_whoami")
    return {
        "username": current_user.username,
        "organization_id": current_user.organization_id,
        "is_super_admin": True,
        "mfa": True,
    }


# ---------------------------------------------------------------------------
# Tenants (read)
# ---------------------------------------------------------------------------

def _tenant_summary(db: Session, org: Organization) -> dict:
    module_count = (
        db.query(func.count(TenantModule.id))
        .filter(TenantModule.organization_id == org.id, TenantModule.is_active.is_(True))
        .scalar()
    )
    active_users = (
        db.query(func.count(User.id)).filter(User.organization_id == org.id, User.is_active.is_(True)).scalar()
    )
    return {
        "id": org.id,
        "name": org.name,
        "tier": org.tier,
        "module_count": module_count,  # active modules including core
        "active_users": active_users,
    }


def _get_org_or_404(db: Session, organization_id: int):
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if org is None:
        return None
    return org


def _not_found() -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": "tenant_not_found"})


def _module_list(db: Session, organization_id: int) -> List[dict]:
    active = tm.active_module_keys(db, organization_id)
    return [{**m, "active": m["key"] in active} for m in tm.catalog()]


@router.get("/tenants")
def list_tenants(db: Session = Depends(get_db)):
    orgs = db.query(Organization).order_by(Organization.id).all()
    return {"tenants": [_tenant_summary(db, o) for o in orgs]}


@router.get("/tenants/{organization_id}")
def get_tenant(organization_id: int, db: Session = Depends(get_db)):
    org = _get_org_or_404(db, organization_id)
    if org is None:
        return _not_found()
    return {**_tenant_summary(db, org), "modules": _module_list(db, org.id)}


@router.get("/tenants/{organization_id}/modules")
def get_tenant_modules(organization_id: int, db: Session = Depends(get_db)):
    org = _get_org_or_404(db, organization_id)
    if org is None:
        return _not_found()
    return {"organization_id": org.id, "tier": org.tier, "modules": _module_list(db, org.id)}


# ---------------------------------------------------------------------------
# Tenant modules (write)
# ---------------------------------------------------------------------------

class ModulesBody(BaseModel):
    tier: Optional[str] = None  # required while the organization has no tier yet
    modules: List[str]


@router.put("/tenants/{organization_id}/modules")
def put_tenant_modules(
    organization_id: int,
    body: ModulesBody,
    current_user: User = Depends(require_ops_access),
    db: Session = Depends(get_db),
):
    """Replace the tenant's module set, validated against the tier rules. Idempotent; nothing changes on a 422."""
    org = _get_org_or_404(db, organization_id)
    if org is None:
        return _not_found()

    tier = body.tier or org.tier
    if tier is None:
        return JSONResponse(
            status_code=422,
            content={"error": "tier_required", "problems": ["this organization has no tier yet; send 'tier' in the body"]},
        )

    problems = tm.validate_tier_modules(tier, body.modules)
    if problems:
        return JSONResponse(status_code=422, content={"error": "tier_rules_violated", "tier": tier, "problems": problems})

    added, removed = tm.replace_modules(db, org.id, body.modules)
    tier_changed = org.tier != tier
    org.tier = tier
    db.commit()

    changed = bool(added or removed or tier_changed)
    if changed:
        log_ops_action(
            db,
            current_user,
            "tenant_modules_updated",
            target_org_id=org.id,
            details=f"tier={tier}; added={','.join(added) or '-'}; removed={','.join(removed) or '-'}",
        )

    return {
        "organization_id": org.id,
        "tier": tier,
        "changed": changed,
        "added": added,
        "removed": removed,
        "modules": sorted(tm.active_module_keys(db, org.id)),
    }
