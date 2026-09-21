"""Batch F, deel 1: tier rules, module replacement and the seed wrapper (no network)."""
import importlib
import uuid

import pytest

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.tenant_module import TenantModule
from app.services import tenant_modules as tm
from app.services.module_access import BASE_MODULES

seed_modules = importlib.import_module("scripts.seed_modules")

WORKFLOWS = sorted(tm.workflow_keys())


def _mods(n_workflows, with_compliance=None, core=True):
    """core (optional) + the first n workflows; force compliance_monitor in/out when asked."""
    chosen = [k for k in WORKFLOWS if k != tm.COMPLIANCE_KEY]
    picked = chosen[:n_workflows]
    if with_compliance is True:
        picked = picked[: max(n_workflows - 1, 0)] + [tm.COMPLIANCE_KEY]
    return ([tm.CORE_KEY] if core else []) + picked


def _org(tier=None):
    db = SessionLocal()
    org = Organization(name=f"tm-test-{uuid.uuid4().hex[:10]}", tier=tier)
    db.add(org)
    db.commit()
    oid = org.id
    db.close()
    return oid


def _rows(org_id):
    db = SessionLocal()
    try:
        return {r.module_key: r.is_active for r in db.query(TenantModule).filter(TenantModule.organization_id == org_id).all()}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tier rules
# ---------------------------------------------------------------------------

def test_catalog_is_core_plus_ten_workflows():
    assert len(BASE_MODULES) == 11 and tm.CORE_KEY in tm.catalog_keys()
    assert len(tm.workflow_keys()) == 10 and tm.CORE_KEY not in tm.workflow_keys()


@pytest.mark.parametrize(
    "tier,modules",
    [
        ("starter", _mods(2, with_compliance=False)),
        ("starter", _mods(10)),
        ("business", _mods(5, with_compliance=True)),
        ("business", _mods(9, with_compliance=True)),
        ("enterprise", _mods(7, with_compliance=True)),
        ("enterprise", sorted(tm.catalog_keys())),
    ],
)
def test_valid_combinations(tier, modules):
    assert tm.validate_tier_modules(tier, modules) == []


@pytest.mark.parametrize(
    "tier,modules,fragment",
    [
        ("starter", _mods(1), "at least 2 workflows"),
        ("starter", _mods(0), "at least 2 workflows"),
        ("business", _mods(5, with_compliance=False), "requires: compliance_monitor"),
        ("business", _mods(4, with_compliance=True), "at least 5 workflows"),
        ("enterprise", _mods(6, with_compliance=True), "at least 7 workflows"),
        ("enterprise", _mods(7, with_compliance=False), "requires: compliance_monitor"),
    ],
)
def test_tier_violations_are_reported_with_what_is_missing(tier, modules, fragment):
    problems = tm.validate_tier_modules(tier, modules)
    assert any(fragment in p for p in problems), problems


def test_core_is_required_and_does_not_count_as_a_workflow():
    problems = tm.validate_tier_modules("starter", _mods(3, core=False))
    assert any("'core' is required" in p for p in problems)
    # core + 1 workflow is still only 1 workflow
    assert any("at least 2 workflows, got 1" in p for p in tm.validate_tier_modules("starter", [tm.CORE_KEY, WORKFLOWS[0]]))


def test_unknown_keys_duplicates_and_unknown_tier():
    problems = tm.validate_tier_modules("starter", _mods(3) + ["no_such_module"])
    assert any("unknown modules: no_such_module" in p for p in problems)
    assert any("duplicate modules" in p for p in tm.validate_tier_modules("starter", _mods(3) + [WORKFLOWS[0]]))
    assert tm.validate_tier_modules("platinum", _mods(3)) == ["unknown tier 'platinum'; allowed: starter, business, enterprise"]


# ---------------------------------------------------------------------------
# replace_modules / ensure_modules
# ---------------------------------------------------------------------------

def test_replace_modules_is_idempotent_and_deactivates_instead_of_deleting():
    org = _org()
    first = _mods(3)
    db = SessionLocal()
    added, removed = tm.replace_modules(db, org, first)
    db.commit()
    assert sorted(added) == sorted(first) and removed == []

    added, removed = tm.replace_modules(db, org, first)  # same set again: nothing changes
    db.commit()
    assert added == [] and removed == []

    smaller = _mods(2)
    added, removed = tm.replace_modules(db, org, smaller)
    db.commit()
    assert added == [] and removed == sorted(set(first) - set(smaller))
    rows = _rows(org)
    assert len(rows) == 4  # nothing deleted
    assert sum(rows.values()) == 3 and tm.active_module_keys(db, org) == set(smaller)

    added, removed = tm.replace_modules(db, org, first)  # comes back: reactivated, no duplicate row
    db.commit()
    assert len(_rows(org)) == 4 and tm.active_module_keys(db, org) == set(first)
    db.close()


def test_replace_modules_only_touches_the_given_organization():
    a, b = _org(), _org()
    db = SessionLocal()
    tm.replace_modules(db, a, _mods(3))
    tm.replace_modules(db, b, _mods(4))
    db.commit()
    before_b = _rows(b)
    tm.replace_modules(db, a, _mods(2))
    db.commit()
    db.close()
    assert _rows(b) == before_b


def test_ensure_modules_is_insert_only():
    org = _org()
    db = SessionLocal()
    assert tm.ensure_modules(db, org, ["core", "customer_support_ai"]) == (2, 0)
    db.commit()
    db.query(TenantModule).filter(TenantModule.organization_id == org, TenantModule.module_key == "customer_support_ai").update({"is_active": False})
    db.commit()
    assert tm.ensure_modules(db, org, ["core", "customer_support_ai", "business_intelligence"]) == (1, 2)
    db.commit()
    db.close()
    assert _rows(org) == {"core": True, "customer_support_ai": False, "business_intelligence": True}  # existing rows untouched


# ---------------------------------------------------------------------------
# seed_modules.py stays functionally identical for existing organizations
# ---------------------------------------------------------------------------

def _snapshot(org_ids):
    return {oid: _rows(oid) for oid in org_ids}


def test_seed_does_not_change_existing_organizations():
    before = _snapshot([1, 2])
    seed_modules.seed()
    seed_modules.seed()  # twice: idempotent
    assert _snapshot([1, 2]) == before


def test_seed_inserts_missing_rows_for_a_tierless_org_and_skips_orgs_with_a_tier(monkeypatch):
    tierless, managed = _org(tier=None), _org(tier="starter")
    monkeypatch.setattr(seed_modules, "SEED_DATA", {tierless: {"core", "customer_support_ai"}, managed: {"core", "customer_support_ai"}})
    seed_modules.seed()
    assert _rows(tierless) == {"core": True, "customer_support_ai": True}
    assert _rows(managed) == {}  # managed through the module API: the seed leaves it alone

    # a module removed via the API is not re-added by the next deploy's seed
    db = SessionLocal()
    tm.replace_modules(db, managed, _mods(2))
    db.commit()
    db.close()
    before = _rows(managed)
    monkeypatch.setattr(seed_modules, "SEED_DATA", {managed: set(tm.catalog_keys())})
    seed_modules.seed()
    assert _rows(managed) == before
