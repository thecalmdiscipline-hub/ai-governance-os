"""Batch E, deel 3: change-password, /auth/me and the must_change_password gate."""
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
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)
PASSWORD = "Correct-Horse-Battery-9"
NEW_PASSWORD = "Another-Long-Passphrase-42"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))


@pytest.fixture(scope="module")
def org_id():
    db = SessionLocal()
    org = Organization(name=f"pw-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    oid = org.id
    db.close()
    return oid


def _user(org_id, must_change):
    db = SessionLocal()
    name = f"pw_{uuid.uuid4().hex[:10]}"
    db.add(User(username=name, password_hash=hash_password(PASSWORD), role="admin", organization_id=org_id,
                is_active=True, is_super_admin=False, must_change_password=must_change))
    db.commit()
    db.close()
    return name


def _login(name, password=PASSWORD):
    return client.post("/login", data={"username": name, "password": password})


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_flagged_user_is_blocked_everywhere_except_the_allowed_endpoints(org_id):
    name = _user(org_id, must_change=True)
    login = _login(name)
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True
    token = login.json()["access_token"]

    blocked = client.get("/modules", headers=_h(token))
    assert blocked.status_code == 403
    assert blocked.json() == {"error": "password_change_required"}
    assert client.get("/workflows/dashboard", headers=_h(token)).json() == {"error": "password_change_required"}
    assert client.get("/users", headers=_h(token)).status_code == 403

    me = client.get("/auth/me", headers=_h(token))
    assert me.status_code == 200 and me.json()["must_change_password"] is True
    assert client.post("/auth/mfa/setup", headers=_h(token)).status_code == 200  # MFA endpoints stay reachable


def test_gate_does_not_touch_users_without_the_flag(org_id):
    name = _user(org_id, must_change=False)
    login = _login(name)
    assert set(login.json()) == {"access_token", "token_type"}  # no must_change_password key at all
    assert client.get("/modules", headers=_h(login.json()["access_token"])).status_code == 200


def test_change_password_clears_the_flag_and_unblocks(org_id):
    name = _user(org_id, must_change=True)
    token = _login(name).json()["access_token"]
    res = client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}, headers=_h(token))
    assert res.status_code == 200, res.text
    assert client.get("/modules", headers=_h(token)).status_code == 200
    db = SessionLocal()
    user = db.query(User).filter(User.username == name).first()
    assert user.must_change_password is False and user.password_changed_at is not None
    audit = [r.action for r in db.query(AuditLog).filter(AuditLog.entity_type == "user", AuditLog.entity_id == user.id).all()]
    db.close()
    assert "password_changed" in audit
    assert _login(name, PASSWORD).status_code == 401
    assert _login(name, NEW_PASSWORD).status_code == 200


def test_change_password_validations(org_id):
    name = _user(org_id, must_change=False)
    token = _login(name).json()["access_token"]
    too_short = client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": "Short-1"}, headers=_h(token))
    assert too_short.status_code == 422
    same = client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": PASSWORD}, headers=_h(token))
    assert same.status_code == 400
    wrong = client.post("/auth/change-password", json={"current_password": "not-the-password-1", "new_password": NEW_PASSWORD}, headers=_h(token))
    assert wrong.status_code == 401 and wrong.json() == {"detail": "Invalid credentials"}
    assert _login(name).status_code == 200  # nothing changed


def test_wrong_current_password_locks_after_five_attempts(org_id):
    name = _user(org_id, must_change=False)
    token = _login(name).json()["access_token"]
    for _ in range(5):
        client.post("/auth/change-password", json={"current_password": "wrong-password-1", "new_password": NEW_PASSWORD}, headers=_h(token))
    ok_now = client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}, headers=_h(token))
    assert ok_now.status_code == 401  # locked, even with the right password


def test_flag_is_passed_on_by_the_mfa_login_step(org_id):
    name = _user(org_id, must_change=True)
    token = _login(name).json()["access_token"]
    secret = client.post("/auth/mfa/setup", headers=_h(token)).json()["secret"]
    assert client.post("/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=_h(token)).status_code == 200
    step1 = _login(name).json()
    assert step1["mfa_required"] is True
    step2 = client.post("/login/mfa", json={"mfa_token": step1["mfa_token"], "code": pyotp.TOTP(secret).at(__import__("time").time() + 30)})
    assert step2.status_code == 200
    assert step2.json()["must_change_password"] is True


def test_me_reports_profile_and_mfa_claim(org_id):
    name = _user(org_id, must_change=False)
    me = client.get("/auth/me", headers=_h(_login(name).json()["access_token"])).json()
    assert me["username"] == name and me["organization_id"] == org_id
    assert me["is_super_admin"] is False and me["mfa_enabled"] is False and me["mfa"] is False
