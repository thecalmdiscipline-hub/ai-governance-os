"""
Provisioning: a new customer (organization + first admin + modules + default governance records) in one call.

Used by POST /ops/tenants/provision and scripts/provision_tenant.py.

Guarantees:
  - One database transaction for everything that ends up in the database; any error rolls it all back
    (and removes the demo file, which is the one thing written outside the database).
  - Idempotent on `idempotency_key`: the same key with the same parameters answers with what exists and
    never shows the password again; the same key with other parameters is a conflict.
  - The first admin gets a random one-time password (>= 20 characters), stored only as a hash, with
    must_change_password=True; never MFA, never super-admin. The password exists in exactly one place: the
    return value of provision_tenant() (created=True). It is never logged, audited or stored.
  - Tier rules come from app/services/tenant_modules.py (the single home of those rules).
  - The audit lines (HQ chain + the new tenant's chain) and the optional demo run happen after the commit;
    a failing audit or demo run never undoes the tenant.
"""
import hashlib
import json
import logging
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import provisioning_defaults as defaults
from app.core.ops_audit import log_ops_action
from app.core.security import hash_password
from app.models.ai_policy import AIPolicy
from app.models.ai_risk import AIRisk
from app.models.ai_system import AISystem
from app.models.document import Document
from app.models.organization import Organization
from app.models.provisioning_request import ProvisioningRequest
from app.models.tenant_module import TenantModule
from app.models.user import User
from app.services import document_storage
from app.services import tenant_modules as tm
from app.services.module_access import BASE_MODULES

logger = logging.getLogger(__name__)

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]{3,64}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_BYTES = 24  # secrets.token_urlsafe(24) -> 32 characters


class ProvisioningError(Exception):
    """A refusal with an HTTP-like status: 422 (validation) or 409 (conflict). Never carries secrets."""

    def __init__(self, status: int, code: str, problems: Optional[List[str]] = None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.problems = problems or []


@dataclass
class ProvisionParams:
    idempotency_key: str
    organization_name: str
    tier: str
    modules: List[str]
    admin_username: str
    country: Optional[str] = None
    sector: Optional[str] = None
    admin_email: Optional[str] = None  # validated only; there is no place to store it (users has no e-mail column)
    include_demo_document: bool = True
    include_demo_run: bool = False

    def fingerprint(self) -> str:
        """Hash of every parameter except the key itself; equal parameters give an equal hash."""
        canonical = {
            "organization_name": self.organization_name.strip(),
            "country": self.country,
            "sector": self.sector,
            "tier": self.tier,
            "modules": sorted(self.modules),
            "admin_username": self.admin_username,
            "admin_email": (self.admin_email or "").strip().lower() or None,
            "include_demo_document": self.include_demo_document,
            "include_demo_run": self.include_demo_run,
        }
        return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


@dataclass
class _Context:
    params: ProvisionParams
    created_by: str
    org: Optional[Organization] = None
    admin: Optional[User] = None
    password: Optional[str] = None
    demo_file: Optional[Path] = None
    counts: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation and conflicts
# ---------------------------------------------------------------------------

def validate_params(p: ProvisionParams) -> List[str]:
    problems: List[str] = []
    if not p.idempotency_key or not p.idempotency_key.strip() or len(p.idempotency_key) > 200:
        problems.append("idempotency_key is required (at most 200 characters)")
    if not p.organization_name or not p.organization_name.strip() or len(p.organization_name) > 200:
        problems.append("organization_name is required (at most 200 characters)")
    if not _USERNAME_RE.match(p.admin_username or ""):
        problems.append("admin_username must be 3-64 characters: letters, digits, _, . and -")
    if p.admin_email and not _EMAIL_RE.match(p.admin_email):
        problems.append("admin_email is not a valid e-mail address")
    problems.extend(tm.validate_tier_modules(p.tier, p.modules))
    return problems


def _find_replay(db: Session, p: ProvisionParams) -> Optional[ProvisioningRequest]:
    row = db.query(ProvisioningRequest).filter(ProvisioningRequest.idempotency_key == p.idempotency_key).first()
    if row is None:
        return None
    if row.request_hash != p.fingerprint():
        raise ProvisioningError(409, "idempotency_key_conflict", ["this key was used with different parameters"])
    return row


def _check_conflicts(db: Session, p: ProvisionParams) -> None:
    name = p.organization_name.strip().lower()
    if db.query(Organization).filter(func.lower(func.trim(Organization.name)) == name).first() is not None:
        raise ProvisioningError(409, "organization_name_taken", ["an organization with this name already exists"])
    if db.query(User).filter(User.username == p.admin_username).first() is not None:
        raise ProvisioningError(409, "username_taken", ["this admin_username is already in use"])


# ---------------------------------------------------------------------------
# Steps (module-level functions so tests can force a failure after any of them)
# ---------------------------------------------------------------------------

def _create_organization(db: Session, ctx: _Context) -> None:
    p = ctx.params
    ctx.org = Organization(name=p.organization_name.strip(), country=p.country, sector=p.sector, tier=p.tier)
    db.add(ctx.org)
    db.flush()


def _create_admin(db: Session, ctx: _Context) -> None:
    ctx.password = secrets.token_urlsafe(PASSWORD_BYTES)
    ctx.admin = User(
        username=ctx.params.admin_username,
        password_hash=hash_password(ctx.password),
        role="admin",
        organization_id=ctx.org.id,
        is_active=True,
        is_super_admin=False,
        must_change_password=True,
        mfa_enabled=False,
    )
    db.add(ctx.admin)
    db.flush()


def _create_modules(db: Session, ctx: _Context) -> None:
    for key in sorted(set(ctx.params.modules)):
        db.add(TenantModule(organization_id=ctx.org.id, module_key=key, is_active=True))
    db.flush()
    ctx.counts["modules"] = len(set(ctx.params.modules))


def _create_governance_defaults(db: Session, ctx: _Context) -> None:
    db.add(AIPolicy(organization_id=ctx.org.id, **defaults.policy_texts(ctx.org.name)))
    by_key = {m["key"]: m for m in BASE_MODULES}
    systems = risks = 0
    for key in sorted(set(ctx.params.modules) & tm.workflow_keys()):
        module = by_key[key]
        system = AISystem(
            name=module["name"],
            description=module["description"],
            purpose=defaults.SYSTEM_PURPOSE,
            organization_id=ctx.org.id,
        )
        db.add(system)
        db.flush()
        db.add(AIRisk(ai_system_id=system.id, **defaults.starter_risk(key)))
        systems += 1
        risks += 1
    db.flush()
    ctx.counts.update({"ai_policies": 1, "ai_systems": systems, "ai_risks": risks})


def _create_demo_document(db: Session, ctx: _Context) -> None:
    ctx.counts["documents"] = 0
    if not ctx.params.include_demo_document:
        return
    org_dir = document_storage.ensure_org_dir(ctx.org.id)
    stored_name = f"{uuid4().hex}_{defaults.DEMO_DOCUMENT_FILENAME}"
    path = org_dir / stored_name
    content = defaults.DEMO_DOCUMENT_TEXT.encode()
    path.write_bytes(content)
    ctx.demo_file = path  # removed again if the transaction fails
    db.add(
        Document(
            organization_id=ctx.org.id,
            uploaded_by_user_id=ctx.admin.id,
            filename=defaults.DEMO_DOCUMENT_FILENAME,
            stored_name=stored_name,
            path=str(path),
            content_type="text/plain",
            size=len(content),
        )
    )
    db.flush()
    ctx.counts["documents"] = 1


def _record_request(db: Session, ctx: _Context) -> None:
    db.add(
        ProvisioningRequest(
            idempotency_key=ctx.params.idempotency_key,
            request_hash=ctx.params.fingerprint(),
            organization_id=ctx.org.id,
            admin_username=ctx.params.admin_username,
            created_by=ctx.created_by,
            created_at=datetime.utcnow(),
        )
    )
    db.flush()


_STEPS = (
    "_create_organization",
    "_create_admin",
    "_create_modules",
    "_create_governance_defaults",
    "_create_demo_document",
    "_record_request",
)


def _cleanup_file(ctx: _Context) -> None:
    if ctx.demo_file is not None:
        try:
            ctx.demo_file.unlink(missing_ok=True)
            ctx.demo_file.parent.rmdir()  # only succeeds if the directory is empty
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Summary of what exists (used for replays and for the created response)
# ---------------------------------------------------------------------------

def _summary(db: Session, org_id: int) -> Dict[str, Any]:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    active = sorted(tm.active_module_keys(db, org_id))
    systems = db.query(func.count(AISystem.id)).filter(AISystem.organization_id == org_id).scalar()
    risks = (
        db.query(func.count(AIRisk.id)).join(AISystem, AIRisk.ai_system_id == AISystem.id).filter(AISystem.organization_id == org_id).scalar()
    )
    policies = db.query(func.count(AIPolicy.id)).filter(AIPolicy.organization_id == org_id).scalar()
    documents = db.query(func.count(Document.id)).filter(Document.organization_id == org_id).scalar()
    return {
        "organization_id": org.id,
        "organization_name": org.name,
        "tier": org.tier,
        "modules": active,
        "counts": {
            "modules": len(active),
            "ai_policies": policies,
            "ai_systems": systems,
            "ai_risks": risks,
            "documents": documents,
        },
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def plan(db: Session, p: ProvisionParams) -> Dict[str, Any]:
    """Validate everything without writing (for --dry-run). Raises ProvisioningError like provision_tenant."""
    problems = validate_params(p)
    if problems:
        raise ProvisioningError(422, "validation_failed", problems)
    replay = _find_replay(db, p)
    if replay is not None:
        return {"would_create": False, "reason": "idempotent replay", **_summary(db, replay.organization_id)}
    _check_conflicts(db, p)
    workflows = set(p.modules) & tm.workflow_keys()
    return {
        "would_create": True,
        "organization_name": p.organization_name.strip(),
        "tier": p.tier,
        "modules": sorted(set(p.modules)),
        "admin_username": p.admin_username,
        "counts": {
            "modules": len(set(p.modules)),
            "ai_policies": 1,
            "ai_systems": len(workflows),
            "ai_risks": len(workflows),
            "documents": 1 if p.include_demo_document else 0,
        },
    }


def provision_tenant(
    db: Session,
    p: ProvisionParams,
    *,
    actor: Optional[User],
    performed_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Create the tenant, or answer an idempotent replay. Raises ProvisioningError (422/409)."""
    problems = validate_params(p)
    if problems:
        raise ProvisioningError(422, "validation_failed", problems)

    replay = _find_replay(db, p)
    if replay is not None:
        return {"created": False, **_summary(db, replay.organization_id), "admin_username": replay.admin_username, "demo_run": "not_repeated"}

    _check_conflicts(db, p)

    who = performed_by or (actor.username if actor is not None else "system")
    ctx = _Context(params=p, created_by=who)
    try:
        for name in _STEPS:
            globals()[name](db, ctx)
        db.commit()
    except IntegrityError:
        # Two identical calls racing on the unique key/name: roll back, then answer like a replay if it is one.
        db.rollback()
        _cleanup_file(ctx)
        replay = _find_replay(db, p)
        if replay is not None:
            return {"created": False, **_summary(db, replay.organization_id), "admin_username": replay.admin_username, "demo_run": "not_repeated"}
        raise ProvisioningError(409, "conflict", ["the organization or admin username already exists"])
    except Exception:
        db.rollback()
        _cleanup_file(ctx)
        raise

    org_id = ctx.org.id
    admin_id = ctx.admin.id
    password = ctx.password
    result: Dict[str, Any] = {"created": True, **_summary(db, org_id), "admin_username": p.admin_username, "admin_password": password}

    # After the commit: audit (HQ chain + the new tenant's chain). The details hold no secret.
    try:
        log_ops_action(
            db,
            actor,
            "tenant_provisioned",
            target_org_id=org_id,
            details=(
                f"tier={p.tier}; modules={result['counts']['modules']}; systems={result['counts']['ai_systems']}; "
                f"risks={result['counts']['ai_risks']}; demo_document={bool(result['counts']['documents'])}; admin={p.admin_username}"
            ),
            performed_by=performed_by,
        )
        result["audit_logged"] = True
    except Exception:  # noqa: BLE001 - the tenant exists; report instead of failing
        logger.error("provisioning: tenant %s was created but writing the audit lines failed", org_id)
        result["audit_logged"] = False

    result["demo_run"] = _demo_run(p, org_id, admin_id)
    return result


def _demo_run(p: ProvisionParams, org_id: int, admin_id: int) -> str:
    """Optional demo workflow run, after the commit; a failure only changes this status."""
    if not p.include_demo_run:
        return "not_requested"
    workflow = next((w for w in defaults.DEMO_RUN_ORDER if _module_for(w) in p.modules), None)
    if workflow is None:
        return "skipped"
    try:
        from app.workflows.services.runner import run_workflow  # local import: pulls in the whole workflow layer

        res = run_workflow(
            workflow,
            {"input": defaults.DEMO_RUN_INPUTS[workflow], "context": {}, "user": p.admin_username},
            user_id=admin_id,
            org_id=org_id,
        )
        return "ok" if res.get("status") == "ok" else "failed"
    except Exception:  # noqa: BLE001
        logger.error("provisioning: demo run failed for organization %s", org_id)
        return "failed"


def _module_for(workflow_key: str) -> str:
    for m in BASE_MODULES:
        if m.get("workflow_key") == workflow_key:
            return m["key"]
    return ""
