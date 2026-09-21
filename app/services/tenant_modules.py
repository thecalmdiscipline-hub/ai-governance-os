"""
Tier rules and module sets per tenant: the single place that knows them.

Used by the ops endpoints (PUT /ops/tenants/{id}/modules), the provisioning endpoint and CLI, and
scripts/seed_modules.py. Nothing else may duplicate these rules.

Rules (confirmed by Dennis, 2026-09-21):
  - "workflow" = a catalog module that is not `core` (BASE_MODULES has core + 10 workflow modules).
  - `core` is always part of a tenant's set and does not count as a workflow.
  - starter: at least 2 workflows; business: at least 5, incl. compliance_monitor;
    enterprise: at least 7, incl. compliance_monitor.
Organizations that existed before tiers (tier NULL, e.g. HQ and the demo org) are grandfathered: the rules
apply to provisioning and to changes made through the module API, never retroactively.
"""
from typing import Dict, Iterable, List, Set, Tuple

from sqlalchemy.orm import Session

from app.models.tenant_module import TenantModule
from app.services.module_access import BASE_MODULES

CORE_KEY = "core"
COMPLIANCE_KEY = "compliance_monitor"

TIERS: Tuple[str, ...] = ("starter", "business", "enterprise")
MIN_WORKFLOWS: Dict[str, int] = {"starter": 2, "business": 5, "enterprise": 7}
REQUIRED_WORKFLOWS: Dict[str, Set[str]] = {
    "starter": set(),
    "business": {COMPLIANCE_KEY},
    "enterprise": {COMPLIANCE_KEY},
}


def catalog_keys() -> Set[str]:
    return {m["key"] for m in BASE_MODULES}


def workflow_keys() -> Set[str]:
    return catalog_keys() - {CORE_KEY}


def catalog() -> List[dict]:
    return [{"key": m["key"], "name": m["name"], "type": m["type"]} for m in BASE_MODULES]


def validate_tier_modules(tier: str, modules: Iterable[str]) -> List[str]:
    """Return a list of human-readable problems; an empty list means the combination is valid."""
    problems: List[str] = []
    if tier not in TIERS:
        return [f"unknown tier {tier!r}; allowed: {', '.join(TIERS)}"]

    keys = list(modules)
    key_set = set(keys)

    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        problems.append(f"duplicate modules: {', '.join(duplicates)}")

    unknown = sorted(key_set - catalog_keys())
    if unknown:
        problems.append(f"unknown modules: {', '.join(unknown)}")

    if CORE_KEY not in key_set:
        problems.append("the module 'core' is required")

    workflows = key_set & workflow_keys()
    minimum = MIN_WORKFLOWS[tier]
    if len(workflows) < minimum:
        problems.append(f"{tier} needs at least {minimum} workflows, got {len(workflows)}")

    missing_required = sorted(REQUIRED_WORKFLOWS[tier] - key_set)
    if missing_required:
        problems.append(f"{tier} requires: {', '.join(missing_required)}")

    return problems


def active_module_keys(db: Session, organization_id: int) -> Set[str]:
    rows = (
        db.query(TenantModule)
        .filter(TenantModule.organization_id == organization_id, TenantModule.is_active.is_(True))
        .all()
    )
    return {r.module_key for r in rows}


def ensure_modules(db: Session, organization_id: int, module_keys: Iterable[str]) -> Tuple[int, int]:
    """Insert missing tenant-module rows, never touching existing ones (also not their is_active).

    Returns (inserted, skipped). Does not commit. This is the insert-only behaviour scripts/seed_modules.py
    always had.
    """
    inserted = skipped = 0
    for key in sorted(set(module_keys)):
        exists = (
            db.query(TenantModule)
            .filter(TenantModule.organization_id == organization_id, TenantModule.module_key == key)
            .first()
        )
        if exists:
            skipped += 1
        else:
            db.add(TenantModule(organization_id=organization_id, module_key=key, is_active=True))
            inserted += 1
    return inserted, skipped


def replace_modules(db: Session, organization_id: int, module_keys: Iterable[str]) -> Tuple[List[str], List[str]]:
    """Make exactly `module_keys` the active set of the tenant. Idempotent. Does not commit.

    Missing rows are inserted, rows of keys that leave the set are deactivated (not deleted, so nothing is lost),
    and previously deactivated rows that return are reactivated. Only rows of this organization are touched.
    Returns (added, removed) as sorted key lists.
    """
    wanted = set(module_keys)
    rows = db.query(TenantModule).filter(TenantModule.organization_id == organization_id).all()
    by_key = {r.module_key: r for r in rows}

    added: List[str] = []
    removed: List[str] = []
    for key in sorted(wanted):
        row = by_key.get(key)
        if row is None:
            db.add(TenantModule(organization_id=organization_id, module_key=key, is_active=True))
            added.append(key)
        elif not row.is_active:
            row.is_active = True
            added.append(key)
    for key, row in sorted(by_key.items()):
        if key not in wanted and row.is_active:
            row.is_active = False
            removed.append(key)
    return added, removed
