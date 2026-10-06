"""Accounts (Batch I, Fase 2.1): Valqeron HQ staff tracking customers/prospects through the sales
and onboarding pipeline. Only reachable under /ops/* (require_ops_access) — customers never read
this. Every write goes through log_ops_action (HQ chain, plus the linked organization's chain once
an account is linked to one)."""
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_ops_access
from app.core.ops_audit import log_ops_action
from app.models.ops_account import OpsAccount
from app.models.organization import Organization
from app.models.user import User
from app.services.ops_accounts import ALL_STATUSES, is_valid_status, validate_transition

router = APIRouter(prefix="/ops", tags=["Ops"], dependencies=[Depends(require_ops_access)])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SOURCES = ("inbound", "outbound", "referral", "manual")
TIERS = ("starter", "business", "enterprise")


def _validate_email(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not _EMAIL_RE.match(value):
        raise ValueError("primary_contact_email is not a valid e-mail address")
    return value


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    country: Optional[str] = None
    sector: Optional[str] = None
    source: Optional[str] = None
    proposed_tier: Optional[str] = None
    primary_contact_name: Optional[str] = None
    primary_contact_email: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("primary_contact_email")
    @classmethod
    def _check_email(cls, v):
        return _validate_email(v)


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    country: Optional[str] = None
    sector: Optional[str] = None
    source: Optional[str] = None
    proposed_tier: Optional[str] = None
    primary_contact_name: Optional[str] = None
    primary_contact_email: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("primary_contact_email")
    @classmethod
    def _check_email(cls, v):
        return _validate_email(v)


class LinkOrganizationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_id: int


class StatusChangeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str


def _account_dict(a: OpsAccount) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "country": a.country,
        "sector": a.sector,
        "status": a.status,
        "source": a.source,
        "proposed_tier": a.proposed_tier,
        "primary_contact_name": a.primary_contact_name,
        "primary_contact_email": a.primary_contact_email,
        "organization_id": a.organization_id,
        "outbound_company_id": a.outbound_company_id,
        "notes": a.notes,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat(),
    }


def _get_account_or_404(db: Session, account_id: int) -> Optional[OpsAccount]:
    return db.query(OpsAccount).filter(OpsAccount.id == account_id).first()


def _not_found() -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": "account_not_found"})


@router.get("/accounts")
def list_accounts(
    status: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, description="search by name (substring, case-insensitive)"),
    db: Session = Depends(get_db),
):
    if status is not None and not is_valid_status(status):
        return JSONResponse(status_code=422, content={"error": "invalid_status", "allowed": list(ALL_STATUSES)})
    query = db.query(OpsAccount)
    if status is not None:
        query = query.filter(OpsAccount.status == status)
    if q:
        query = query.filter(OpsAccount.name.ilike(f"%{q}%"))
    rows = query.order_by(OpsAccount.id.desc()).limit(200).all()
    return {"accounts": [_account_dict(a) for a in rows]}


@router.post("/accounts", status_code=201)
def create_account(
    body: AccountCreate,
    current_user: User = Depends(require_ops_access),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    if body.source is not None and body.source not in SOURCES:
        return JSONResponse(status_code=422, content={"error": "invalid_source", "allowed": list(SOURCES)})
    if body.proposed_tier is not None and body.proposed_tier not in TIERS:
        return JSONResponse(status_code=422, content={"error": "invalid_proposed_tier", "allowed": list(TIERS)})

    now = datetime.utcnow()
    account = OpsAccount(
        name=body.name,
        country=body.country,
        sector=body.sector,
        status="lead",
        source=body.source,
        proposed_tier=body.proposed_tier,
        primary_contact_name=body.primary_contact_name,
        primary_contact_email=body.primary_contact_email,
        notes=body.notes,
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    log_ops_action(db, current_user, "account_created", details=f"account_id={account.id}")
    return _account_dict(account)


@router.get("/accounts/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db)):
    account = _get_account_or_404(db, account_id)
    if account is None:
        return _not_found()
    return _account_dict(account)


@router.patch("/accounts/{account_id}")
def update_account(
    account_id: int,
    body: AccountUpdate,
    current_user: User = Depends(require_ops_access),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    account = _get_account_or_404(db, account_id)
    if account is None:
        return _not_found()

    if body.source is not None and body.source not in SOURCES:
        return JSONResponse(status_code=422, content={"error": "invalid_source", "allowed": list(SOURCES)})
    if body.proposed_tier is not None and body.proposed_tier not in TIERS:
        return JSONResponse(status_code=422, content={"error": "invalid_proposed_tier", "allowed": list(TIERS)})

    fields = body.model_dump(exclude_unset=True)
    changed = False
    for key, value in fields.items():
        if getattr(account, key) != value:
            setattr(account, key, value)
            changed = True

    if changed:
        account.updated_at = datetime.utcnow()
        db.commit()
        log_ops_action(db, current_user, "account_updated", target_org_id=account.organization_id, details=f"account_id={account.id}; fields={','.join(sorted(fields.keys()))}")
    db.refresh(account)
    return _account_dict(account)


@router.post("/accounts/{account_id}/link-organization")
def link_organization(
    account_id: int,
    body: LinkOrganizationBody,
    current_user: User = Depends(require_ops_access),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    account = _get_account_or_404(db, account_id)
    if account is None:
        return _not_found()
    if account.organization_id is not None:
        return JSONResponse(status_code=409, content={"error": "already_linked", "organization_id": account.organization_id})

    org = db.query(Organization).filter(Organization.id == body.organization_id).first()
    if org is None:
        return JSONResponse(status_code=404, content={"error": "organization_not_found"})

    already = db.query(OpsAccount).filter(OpsAccount.organization_id == org.id).first()
    if already is not None:
        return JSONResponse(status_code=409, content={"error": "organization_already_linked_to_another_account", "account_id": already.id})

    account.organization_id = org.id
    account.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(account)

    log_ops_action(db, current_user, "account_linked_organization", target_org_id=org.id, details=f"account_id={account.id}")
    return _account_dict(account)


@router.post("/accounts/{account_id}/status")
def change_account_status(
    account_id: int,
    body: StatusChangeBody,
    current_user: User = Depends(require_ops_access),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    account = _get_account_or_404(db, account_id)
    if account is None:
        return _not_found()

    if not is_valid_status(body.status):
        return JSONResponse(status_code=422, content={"error": "invalid_status", "allowed": list(ALL_STATUSES)})

    reason = validate_transition(account.status, body.status)
    if reason is not None:
        return JSONResponse(status_code=409, content={"error": reason, "from": account.status, "to": body.status})

    old = account.status
    changed = old != body.status
    if changed:
        account.status = body.status
        account.updated_at = datetime.utcnow()
        db.commit()
        log_ops_action(db, current_user, "account_status_changed", target_org_id=account.organization_id, details=f"account_id={account.id}; {old}->{body.status}")
    db.refresh(account)
    return {"id": account.id, "status": account.status, "changed": changed}
