"""Batch E, deel 5: emergency MFA reset script."""
import importlib
import uuid
from datetime import datetime, timedelta

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
from app.models.user import User

reset_script = importlib.import_module("scripts.mfa_reset")

client = TestClient(app, raise_server_exceptions=False)
PASSWORD = "Correct-Horse-Battery-9"


@pytest.fixture(scope="module")
def org_id():
    db = SessionLocal()
    org = Organization(name=f"reset-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    oid = org.id
    db.close()
    return oid


@pytest.fixture(autouse=True)
def _env(monkeypatch, org_id):
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("HQ_ORGANIZATION_ID", str(org_id))  # this test org acts as HQ
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))


def _user(org_id):
    db = SessionLocal()
    name = f"rst_{uuid.uuid4().hex[:10]}"
    db.add(User(username=name, password_hash=hash_password(PASSWORD), role="admin", organization_id=org_id,
                is_active=True, is_super_admin=False))
    db.commit()
    db.close()
    return name


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _row(name):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == name).first()
    finally:
        db.close()


def _enroll(name):
    token = client.post("/login", data={"username": name, "password": PASSWORD}).json()["access_token"]
    secret = client.post("/auth/mfa/setup", headers=_h(token)).json()["secret"]
    res = client.post("/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=_h(token))
    assert res.status_code == 200
    return res.json()["backup_codes"]


def _mfa_login(name, backup_code):
    step1 = client.post("/login", data={"username": name, "password": PASSWORD}).json()
    return client.post("/login/mfa", json={"mfa_token": step1["mfa_token"], "code": backup_code})


def _apply(name, dry_run=False):
    db = SessionLocal()
    try:
        return reset_script.apply(db, name, dry_run)
    finally:
        db.close()


def test_reset_wipes_all_mfa_fields_and_plain_login_works_again(org_id):
    name = _user(org_id)
    _enroll(name)
    db = SessionLocal()
    db.query(User).filter(User.username == name).update(
        {"mfa_failed_attempts": 3, "mfa_locked_until": datetime.utcnow() + timedelta(minutes=10)})
    db.commit()
    db.close()

    assert _apply(name, dry_run=True) == [f"WOULD reset MFA for {name}"]
    assert _row(name).mfa_enabled is True  # dry-run wrote nothing

    assert _apply(name) == [f"reset MFA for {name}"]
    row = _row(name)
    assert row.mfa_enabled is False
    assert row.mfa_secret_enc is None and row.mfa_backup_codes is None and row.mfa_last_step is None
    assert row.mfa_failed_attempts == 0 and row.mfa_locked_until is None
    assert set(client.post("/login", data={"username": name, "password": PASSWORD}).json()) == {"access_token", "token_type"}

    db = SessionLocal()
    lines = [r for r in db.query(AuditLog).filter(AuditLog.entity_type == "user_mfa", AuditLog.entity_id == row.id,
                                                 AuditLog.action == "mfa_reset").all()]
    db.close()
    assert len(lines) == 1 and lines[0].performed_by == "system:mfa_reset"
    assert _apply(name) == []  # idempotent


def test_reset_of_a_locked_out_user_unblocks_login(org_id):
    name = _user(org_id)
    _enroll(name)
    step1 = client.post("/login", data={"username": name, "password": PASSWORD}).json()
    for _ in range(5):
        client.post("/login/mfa", json={"mfa_token": step1["mfa_token"], "code": "000000"})
    assert _row(name).mfa_locked_until is not None
    _apply(name)
    assert _row(name).mfa_locked_until is None
    assert "access_token" in client.post("/login", data={"username": name, "password": PASSWORD}).json()


def test_super_admin_keeps_the_flag_but_loses_ops_until_new_enrollment(org_id):
    name = _user(org_id)
    codes = _enroll(name)
    db = SessionLocal()
    db.query(User).filter(User.username == name).update({"is_super_admin": True})
    db.commit()
    db.close()
    token = _mfa_login(name, codes[0]).json()["access_token"]
    assert client.get("/ops/whoami", headers=_h(token)).status_code == 200

    _apply(name)
    assert _row(name).is_super_admin is True  # flag stays
    assert client.get("/ops/whoami", headers=_h(token)).status_code == 403  # the old MFA token no longer counts
    plain = client.post("/login", data={"username": name, "password": PASSWORD}).json()["access_token"]
    assert client.get("/ops/whoami", headers=_h(plain)).status_code == 403  # no claim without MFA

    new_codes = _enroll(name)  # new enrollment + MFA login: /ops works again
    assert client.get("/ops/whoami", headers=_h(_mfa_login(name, new_codes[0]).json()["access_token"])).status_code == 200


def test_reset_unknown_user_and_user_without_mfa(org_id):
    with pytest.raises(SystemExit, match="not found"):
        _apply("no_such_user_zz")
    assert _apply(_user(org_id)) == []
