"""Batch F, deel 1b: /ops tenant overview and module API (access control, tier rules, isolation, audit)."""
import uuid

import pyotp
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from app.core import security
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.tenant_module import TenantModule
from app.models.user import User
from app.services import tenant_modules as tm

client = TestClient(app, raise_server_exceptions=False)
PASSWORD = "Correct-Horse-Battery-9"
WORKFLOWS = sorted(tm.workflow_keys())


def _new_org(prefix, tier=None):
    db = SessionLocal()
    org = Organization(name=f"{prefix}-{uuid.uuid4().hex[:10]}", tier=tier)
    db.add(org)
    db.commit()
    oid = org.id
    db.close()
    return oid


@pytest.fixture(scope="module")
def hq():
    return _new_org("ot-hq")


@pytest.fixture(autouse=True)
def _env(monkeypatch, hq):
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("HQ_ORGANIZATION_ID", str(hq))
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _user(org_id):
    db = SessionLocal()
    name = f"ot_{uuid.uuid4().hex[:10]}"
    db.add(User(username=name, password_hash=hash_password(PASSWORD), role="admin", organization_id=org_id,
                is_active=True, is_super_admin=False))
    db.commit()
    db.close()
    return name


def _plain_token(name):
    return client.post("/login", data={"username": name, "password": PASSWORD}).json()["access_token"]


def _ops_tokens(hq_id):
    """(pre_mfa_token, mfa_token) of a fresh HQ super-admin."""
    name = _user(hq_id)
    pre = _plain_token(name)
    secret = client.post("/auth/mfa/setup", headers=_h(pre)).json()["secret"]
    codes = client.post("/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=_h(pre)).json()["backup_codes"]
    db = SessionLocal()
    db.query(User).filter(User.username == name).update({"is_super_admin": True})
    db.commit()
    db.close()
    step1 = client.post("/login", data={"username": name, "password": PASSWORD}).json()
    mfa = client.post("/login/mfa", json={"mfa_token": step1["mfa_token"], "code": codes[0]}).json()["access_token"]
    return pre, mfa


def _mods(n, compliance=None):
    others = [k for k in WORKFLOWS if k != tm.COMPLIANCE_KEY]
    picked = others[:n]
    if compliance is True:
        picked = picked[: n - 1] + [tm.COMPLIANCE_KEY]
    return [tm.CORE_KEY] + picked


def _rows(org_id):
    db = SessionLocal()
    try:
        return {r.module_key: r.is_active for r in db.query(TenantModule).filter(TenantModule.organization_id == org_id).all()}
    finally:
        db.close()


def _audit_count(org_id, entity_type, action):
    db = SessionLocal()
    try:
        return db.query(AuditLog).filter(AuditLog.organization_id == org_id, AuditLog.entity_type == entity_type,
                                         AuditLog.action == action).count()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------

def test_all_tenant_endpoints_need_ops_access(hq):
    ordinary = _plain_token(_user(hq))
    pre, _mfa = _ops_tokens(hq)
    target = _new_org("ot-t")
    calls = [
        ("get", "/ops/tenants", None),
        ("get", f"/ops/tenants/{target}", None),
        ("get", f"/ops/tenants/{target}/modules", None),
        ("put", f"/ops/tenants/{target}/modules", {"tier": "starter", "modules": _mods(2)}),
    ]
    for method, path, body in calls:
        kwargs = {"json": body} if body is not None else {}
        assert getattr(client, method)(path, **kwargs).status_code == 401
        assert getattr(client, method)(path, headers=_h(ordinary), **kwargs).status_code == 403  # ordinary admin
        assert getattr(client, method)(path, headers=_h(pre), **kwargs).status_code == 403  # no mfa claim
    assert _rows(target) == {}  # the PUTs above changed nothing


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def test_overview_detail_and_modules(hq):
    _pre, mfa = _ops_tokens(hq)
    other = _new_org("ot-o", tier=None)
    db = SessionLocal()
    tm.replace_modules(db, other, _mods(3))
    db.commit()
    db.close()
    _user(other)

    listing = client.get("/ops/tenants", headers=_h(mfa)).json()["tenants"]
    entry = next(t for t in listing if t["id"] == other)
    assert set(entry) == {"id", "name", "tier", "module_count", "active_users"}
    assert entry["tier"] is None and entry["module_count"] == 4 and entry["active_users"] == 1
    assert any(t["id"] == hq for t in listing)

    detail = client.get(f"/ops/tenants/{other}", headers=_h(mfa)).json()
    assert detail["id"] == other and len(detail["modules"]) == 11
    assert sum(1 for m in detail["modules"] if m["active"]) == 4

    mods = client.get(f"/ops/tenants/{other}/modules", headers=_h(mfa)).json()
    assert mods["tier"] is None and {m["key"] for m in mods["modules"]} == tm.catalog_keys()

    assert client.get("/ops/tenants/99999999", headers=_h(mfa)).status_code == 404
    assert client.get("/ops/tenants/99999999/modules", headers=_h(mfa)).status_code == 404
    assert client.put("/ops/tenants/99999999/modules", json={"tier": "starter", "modules": _mods(2)}, headers=_h(mfa)).status_code == 404


# ---------------------------------------------------------------------------
# Write: tier rules
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "tier,modules,fragment",
    [
        ("starter", _mods(1), "at least 2 workflows"),
        ("business", _mods(5, compliance=False), "requires: compliance_monitor"),
        ("enterprise", _mods(6, compliance=True), "at least 7 workflows"),
    ],
)
def test_violations_give_422_with_the_missing_pieces_and_change_nothing(hq, tier, modules, fragment):
    _pre, mfa = _ops_tokens(hq)
    org = _new_org("ot-v")
    res = client.put(f"/ops/tenants/{org}/modules", json={"tier": tier, "modules": modules}, headers=_h(mfa))
    assert res.status_code == 422
    body = res.json()
    assert body["error"] == "tier_rules_violated" and any(fragment in p for p in body["problems"])
    assert _rows(org) == {}
    db = SessionLocal()
    assert db.query(Organization).filter(Organization.id == org).first().tier is None
    db.close()


def test_core_unknown_key_and_missing_tier_are_refused(hq):
    _pre, mfa = _ops_tokens(hq)
    org = _new_org("ot-r")
    no_core = client.put(f"/ops/tenants/{org}/modules", json={"tier": "starter", "modules": _mods(3)[1:]}, headers=_h(mfa))
    assert no_core.status_code == 422 and any("'core' is required" in p for p in no_core.json()["problems"])
    unknown = client.put(f"/ops/tenants/{org}/modules", json={"tier": "starter", "modules": _mods(3) + ["nope"]}, headers=_h(mfa))
    assert unknown.status_code == 422 and any("unknown modules: nope" in p for p in unknown.json()["problems"])
    no_tier = client.put(f"/ops/tenants/{org}/modules", json={"modules": _mods(3)}, headers=_h(mfa))
    assert no_tier.status_code == 422 and no_tier.json()["error"] == "tier_required"
    bad_tier = client.put(f"/ops/tenants/{org}/modules", json={"tier": "platinum", "modules": _mods(3)}, headers=_h(mfa))
    assert bad_tier.status_code == 422
    assert _rows(org) == {}


def test_valid_put_is_idempotent_and_audited_in_both_chains(hq):
    _pre, mfa = _ops_tokens(hq)
    org = _new_org("ot-a")
    body = {"tier": "business", "modules": _mods(5, compliance=True)}
    hq_before = _audit_count(hq, "ops", "tenant_modules_updated")

    first = client.put(f"/ops/tenants/{org}/modules", json=body, headers=_h(mfa))
    assert first.status_code == 200 and first.json()["changed"] is True and first.json()["tier"] == "business"
    assert len(first.json()["modules"]) == 6
    assert _audit_count(hq, "ops", "tenant_modules_updated") == hq_before + 1
    assert _audit_count(org, "ops_access", "tenant_modules_updated") == 1

    second = client.put(f"/ops/tenants/{org}/modules", json=body, headers=_h(mfa))
    assert second.status_code == 200 and second.json()["changed"] is False and second.json()["added"] == []
    assert len(_rows(org)) == 6  # no duplicate rows
    assert _audit_count(hq, "ops", "tenant_modules_updated") == hq_before + 1  # a no-op writes no audit line
    assert _audit_count(org, "ops_access", "tenant_modules_updated") == 1

    # tier can be omitted once the organization has one; the set is replaced, removed modules are deactivated
    smaller = client.put(f"/ops/tenants/{org}/modules", json={"modules": _mods(6, compliance=True)}, headers=_h(mfa))
    assert smaller.status_code == 200 and smaller.json()["added"]

    # both chains still verify
    assert client.get("/audit/verify", headers=_h(mfa)).json()["status"] == "valid"
    target_admin = _plain_token(_user(org))
    assert client.get("/audit/verify", headers=_h(target_admin)).json()["status"] == "valid"


def test_a_change_for_tenant_x_never_touches_tenant_y(hq):
    _pre, mfa = _ops_tokens(hq)
    x, y = _new_org("ot-x"), _new_org("ot-y")
    client.put(f"/ops/tenants/{y}/modules", json={"tier": "starter", "modules": _mods(3)}, headers=_h(mfa))
    y_rows = _rows(y)
    y_audit = _audit_count(y, "ops_access", "tenant_modules_updated")

    client.put(f"/ops/tenants/{x}/modules", json={"tier": "enterprise", "modules": sorted(tm.catalog_keys())}, headers=_h(mfa))
    client.put(f"/ops/tenants/{x}/modules", json={"modules": _mods(2)}, headers=_h(mfa))

    assert _rows(y) == y_rows
    assert _audit_count(y, "ops_access", "tenant_modules_updated") == y_audit
    db = SessionLocal()
    assert db.query(Organization).filter(Organization.id == y).first().tier == "starter"
    db.close()
