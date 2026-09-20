"""scripts/setup_hq_tenant.py: idempotent, dry-run writes nothing, touches only its organization.

Uses fresh UUID-named organizations (never org 1/2): the DB is shared across the suite.
"""
import importlib
import uuid

import pytest

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.tenant_module import TenantModule
from app.models.user import User
from app.services.module_access import BASE_MODULES

setup_hq = importlib.import_module("scripts.setup_hq_tenant")
ALL_KEYS = {m["key"] for m in BASE_MODULES}


def _org_with_users(db, usernames):
    tag = uuid.uuid4().hex[:8]
    org = Organization(name=f"HQ Test Org {tag}")
    db.add(org)
    db.commit()
    db.refresh(org)
    for u in usernames:
        db.add(User(username=f"{u}_{tag}", password_hash=hash_password("x-Test123!"), role="admin", organization_id=org.id))
    db.commit()
    return org, tag


def _active_keys(db, org_id):
    return {r.module_key for r in db.query(TenantModule).filter(
        TenantModule.organization_id == org_id, TenantModule.is_active.is_(True)).all()}


def test_dry_run_reports_but_writes_nothing():
    db = SessionLocal()
    org, tag = _org_with_users(db, ["old", "keep"])
    changes = setup_hq.apply(db, org.id, [f"old_{tag}"], dry_run=True)
    assert len(changes) == len(ALL_KEYS) + 1
    assert all(c.startswith("WOULD ") for c in changes)
    assert _active_keys(db, org.id) == set()
    assert db.query(User).filter(User.username == f"old_{tag}").one().is_active is True
    assert db.query(AuditLog).filter(AuditLog.organization_id == org.id).count() == 0
    db.close()


def test_apply_activates_all_modules_deactivates_user_and_audits():
    db = SessionLocal()
    org, tag = _org_with_users(db, ["old", "keep"])
    setup_hq.apply(db, org.id, [f"old_{tag}"], dry_run=False)
    assert _active_keys(db, org.id) == ALL_KEYS
    old = db.query(User).filter(User.username == f"old_{tag}").one()
    assert old.is_active is False  # deactivated, not deleted
    assert db.query(User).filter(User.username == f"keep_{tag}").one().is_active is True
    assert old.is_super_admin in (False, None)
    actions = [r.action for r in db.query(AuditLog).filter(AuditLog.organization_id == org.id).all()]
    assert actions.count("module_activated") == len(ALL_KEYS)
    assert actions.count("user_deactivated") == 1
    assert all(r.performed_by == "system" for r in db.query(AuditLog).filter(AuditLog.organization_id == org.id).all())
    db.close()


def test_second_run_changes_nothing():
    db = SessionLocal()
    org, tag = _org_with_users(db, ["old", "keep"])
    setup_hq.apply(db, org.id, [f"old_{tag}"], dry_run=False)
    rows_before = db.query(AuditLog).filter(AuditLog.organization_id == org.id).count()
    assert setup_hq.apply(db, org.id, [f"old_{tag}"], dry_run=False) == []
    assert db.query(AuditLog).filter(AuditLog.organization_id == org.id).count() == rows_before
    db.close()


def test_reactivates_an_inactive_existing_module_row():
    db = SessionLocal()
    org, _ = _org_with_users(db, ["keep"])
    db.add(TenantModule(organization_id=org.id, module_key="core", is_active=False))
    db.commit()
    changes = setup_hq.apply(db, org.id, [], dry_run=False)
    assert any("reactivate module core" in c for c in changes)
    assert "core" in _active_keys(db, org.id)
    db.close()


def test_other_organizations_are_untouched():
    db = SessionLocal()
    org_a, tag_a = _org_with_users(db, ["a1", "a2"])
    org_b, tag_b = _org_with_users(db, ["b1"])
    setup_hq.apply(db, org_a.id, [f"a1_{tag_a}"], dry_run=False)
    assert _active_keys(db, org_b.id) == set()
    assert db.query(User).filter(User.username == f"b1_{tag_b}").one().is_active is True
    assert db.query(AuditLog).filter(AuditLog.organization_id == org_b.id).count() == 0
    db.close()


def test_refuses_to_deactivate_the_last_active_user():
    db = SessionLocal()
    org, tag = _org_with_users(db, ["only"])
    with pytest.raises(SystemExit, match="last active user"):
        setup_hq.apply(db, org.id, [f"only_{tag}"], dry_run=False)
    assert db.query(User).filter(User.username == f"only_{tag}").one().is_active is True
    db.close()


def test_unknown_organization_or_user_is_an_error():
    db = SessionLocal()
    with pytest.raises(SystemExit, match="does not exist"):
        setup_hq.apply(db, 999999, [], dry_run=True)
    org, _ = _org_with_users(db, ["keep"])
    with pytest.raises(SystemExit, match="not found"):
        setup_hq.apply(db, org.id, ["nobody"], dry_run=True)
    db.close()
