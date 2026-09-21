"""Batch E, deel 4: super-admin, /ops access control, dual audit logging, grant_super_admin script."""
import importlib
import time
import uuid

import pyotp
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from app.core import security
from app.core.ops_audit import log_ops_action
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.user import User

grant_script = importlib.import_module("scripts.grant_super_admin")

client = TestClient(app, raise_server_exceptions=False)
PASSWORD = "Correct-Horse-Battery-9"


def _new_org(prefix):
    db = SessionLocal()
    org = Organization(name=f"{prefix}-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    oid = org.id
    db.close()
    return oid


@pytest.fixture(scope="module")
def orgs():
    return {"hq": _new_org("ops-hq"), "other": _new_org("ops-other")}


@pytest.fixture(autouse=True)
def _env(monkeypatch, orgs):
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("HQ_ORGANIZATION_ID", str(orgs["hq"]))
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))


def _user(org_id, role="admin", **flags):
    db = SessionLocal()
    name = f"ops_{uuid.uuid4().hex[:10]}"
    db.add(User(username=name, password_hash=hash_password(PASSWORD), role=role, organization_id=org_id,
                is_active=True, is_super_admin=False, **flags))
    db.commit()
    db.close()
    return name


def _set(name, **values):
    db = SessionLocal()
    db.query(User).filter(User.username == name).update(values)
    db.commit()
    db.close()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _plain_token(name):
    return client.post("/login", data={"username": name, "password": PASSWORD}).json()["access_token"]


def _enroll(name):
    """Enroll MFA via the API. Returns (pre_mfa_token, backup_codes)."""
    token = _plain_token(name)
    secret = client.post("/auth/mfa/setup", headers=_h(token)).json()["secret"]
    res = client.post("/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=_h(token))
    assert res.status_code == 200, res.text
    return token, res.json()["backup_codes"]


def _mfa_token(name, backup_code):
    step1 = client.post("/login", data={"username": name, "password": PASSWORD}).json()
    step2 = client.post("/login/mfa", json={"mfa_token": step1["mfa_token"], "code": backup_code})
    assert step2.status_code == 200, step2.text
    return step2.json()["access_token"]


def _super_admin_in(org_id):
    """A user with MFA enabled and the super-admin flag. Returns (name, pre_mfa_token, mfa_token)."""
    name = _user(org_id)
    pre, codes = _enroll(name)
    _set(name, is_super_admin=True)
    return name, pre, _mfa_token(name, codes[0])


def _audit(org_id, entity_type, action):
    db = SessionLocal()
    try:
        return (db.query(AuditLog)
                .filter(AuditLog.organization_id == org_id, AuditLog.entity_type == entity_type, AuditLog.action == action)
                .all())
    finally:
        db.close()


# ---------------------------------------------------------------------------
# /ops access
# ---------------------------------------------------------------------------

def test_whoami_403_for_an_ordinary_admin_even_with_mfa(orgs):
    name = _user(orgs["hq"])
    _pre, codes = _enroll(name)
    assert client.get("/ops/whoami", headers=_h(_mfa_token(name, codes[0]))).status_code == 403


def test_whoami_403_for_super_admin_without_mfa_claim(orgs):
    _name, pre_mfa_token, _ = _super_admin_in(orgs["hq"])
    assert client.get("/ops/whoami", headers=_h(pre_mfa_token)).status_code == 403


def test_whoami_403_for_a_super_admin_outside_hq(orgs):
    _name, _pre, mfa_token = _super_admin_in(orgs["other"])
    assert client.get("/ops/whoami", headers=_h(mfa_token)).status_code == 403


def test_whoami_403_when_hq_is_not_configured(orgs, monkeypatch):
    _name, _pre, mfa_token = _super_admin_in(orgs["hq"])
    monkeypatch.delenv("HQ_ORGANIZATION_ID")
    assert client.get("/ops/whoami", headers=_h(mfa_token)).status_code == 403


def test_whoami_200_for_hq_super_admin_with_mfa_and_writes_a_hq_audit_line(orgs):
    name, _pre, mfa_token = _super_admin_in(orgs["hq"])
    before = len(_audit(orgs["hq"], "ops", "ops_whoami"))
    res = client.get("/ops/whoami", headers=_h(mfa_token))
    assert res.status_code == 200, res.text
    assert res.json() == {"username": name, "organization_id": orgs["hq"], "is_super_admin": True, "mfa": True}
    lines = _audit(orgs["hq"], "ops", "ops_whoami")
    assert len(lines) == before + 1 and lines[-1].performed_by == name


def _user_row(name):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == name).first()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Dual audit logging
# ---------------------------------------------------------------------------

def test_log_ops_action_writes_two_lines_in_two_chains_and_both_stay_valid(orgs):
    name, _pre, mfa_token = _super_admin_in(orgs["hq"])
    db = SessionLocal()
    actor = db.query(User).filter(User.username == name).first()
    log_ops_action(db, actor, "ops_test_action", target_org_id=orgs["other"], details="dual audit test")
    db.close()

    hq_lines = _audit(orgs["hq"], "ops", "ops_test_action")
    target_lines = _audit(orgs["other"], "ops_access", "ops_test_action")
    assert len(hq_lines) == 1 and len(target_lines) == 1
    assert hq_lines[0].entity_id == orgs["other"] and target_lines[0].entity_id == orgs["hq"]
    assert hq_lines[0].performed_by == name == target_lines[0].performed_by

    hq_verify = client.get("/audit/verify", headers=_h(mfa_token)).json()
    assert hq_verify["status"] == "valid"
    other_admin = _user(orgs["other"])
    other_verify = client.get("/audit/verify", headers=_h(_plain_token(other_admin))).json()
    assert other_verify["status"] == "valid" and other_verify["chain_rows_checked"] >= 2


def test_log_ops_action_without_target_writes_only_the_hq_line(orgs):
    name = _user(orgs["hq"])
    db = SessionLocal()
    actor = db.query(User).filter(User.username == name).first()
    log_ops_action(db, actor, "ops_no_target")
    db.close()
    assert len(_audit(orgs["hq"], "ops", "ops_no_target")) == 1
    assert _audit(orgs["other"], "ops_access", "ops_no_target") == []


# ---------------------------------------------------------------------------
# Existing cross-tenant exceptions now need the MFA claim
# ---------------------------------------------------------------------------

def test_cross_tenant_exceptions_require_the_mfa_claim(orgs):
    _name, pre_mfa_token, mfa_token = _super_admin_in(orgs["hq"])

    org_body = {"name": f"created-{uuid.uuid4().hex[:8]}"}
    assert client.post("/organizations", json=org_body, headers=_h(pre_mfa_token)).status_code == 403
    assert client.post("/organizations", json=org_body, headers=_h(mfa_token)).status_code == 201

    user_body = {"username": f"x_{uuid.uuid4().hex[:8]}", "password": "long-enough-pw-1", "role": "operator",
                 "organization_id": orgs["other"]}
    assert client.post("/users", json=user_body, headers=_h(pre_mfa_token)).status_code == 403
    created = client.post("/users", json=user_body, headers=_h(mfa_token))
    assert created.status_code == 201 and created.json()["organization_id"] == orgs["other"]

    assert client.get(f"/users?organization_id={orgs['other']}", headers=_h(pre_mfa_token)).status_code == 403
    assert client.get(f"/users?organization_id={orgs['other']}", headers=_h(mfa_token)).status_code == 200
    audit_export = f"/organizations/{orgs['other']}/audit-export"
    assert client.get(audit_export, headers=_h(pre_mfa_token)).status_code == 404  # scoped to own org again
    assert client.get(audit_export, headers=_h(mfa_token)).status_code == 200


def test_no_endpoint_can_set_is_super_admin(orgs):
    admin = _user(orgs["hq"])
    token = _plain_token(admin)
    body = {"username": f"y_{uuid.uuid4().hex[:8]}", "password": "long-enough-pw-1", "role": "admin", "is_super_admin": True}
    created = client.post("/users", json=body, headers=_h(token))
    assert created.status_code == 201
    assert created.json()["is_super_admin"] is False
    assert _user_row(body["username"]).is_super_admin is False


# ---------------------------------------------------------------------------
# scripts/grant_super_admin.py
# ---------------------------------------------------------------------------

def _apply(name, revoke=False, dry_run=False):
    db = SessionLocal()
    try:
        return grant_script.apply(db, name, revoke, dry_run)
    finally:
        db.close()


def test_grant_refuses_without_mfa_outside_hq_inactive_or_unknown(orgs):
    no_mfa = _user(orgs["hq"])
    with pytest.raises(SystemExit, match="no MFA"):
        _apply(no_mfa)

    outside = _user(orgs["other"])
    _enroll(outside)
    with pytest.raises(SystemExit, match="not in the HQ"):
        _apply(outside)

    inactive = _user(orgs["hq"])
    _enroll(inactive)
    _set(inactive, is_active=False)
    with pytest.raises(SystemExit, match="not active"):
        _apply(inactive)

    with pytest.raises(SystemExit, match="not found"):
        _apply("no_such_user_zz")
    assert _user_row(no_mfa).is_super_admin is False and _user_row(outside).is_super_admin is False


def test_grant_dry_run_grant_idempotency_and_revoke(orgs):
    name = _user(orgs["hq"])
    _enroll(name)

    assert _apply(name, dry_run=True) == [f"WOULD grant super-admin to {name}"]
    assert _user_row(name).is_super_admin is False

    assert _apply(name) == [f"grant super-admin to {name}"]
    assert _user_row(name).is_super_admin is True
    assert _apply(name) == []  # idempotent

    granted = [r for r in _audit(orgs["hq"], "user", "super_admin_granted") if r.entity_id == _user_row(name).id]
    assert len(granted) == 1 and granted[0].performed_by == "system"

    assert _apply(name, revoke=True, dry_run=True) == [f"WOULD revoke super-admin from {name}"]
    assert _user_row(name).is_super_admin is True
    assert _apply(name, revoke=True) == [f"revoke super-admin from {name}"]
    assert _user_row(name).is_super_admin is False
    assert _apply(name, revoke=True) == []
