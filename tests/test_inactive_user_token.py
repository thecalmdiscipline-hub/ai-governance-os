"""A deactivated user can no longer use a token issued before the deactivation."""
import uuid

import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from app.core import security
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.organization import Organization
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)
PASSWORD = "Correct-Horse-Battery-9"


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch):
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))


@pytest.fixture(scope="module")
def org_id():
    db = SessionLocal()
    org = Organization(name=f"inactive-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    oid = org.id
    db.close()
    return oid


def _user(org_id):
    db = SessionLocal()
    name = f"ina_{uuid.uuid4().hex[:10]}"
    db.add(User(username=name, password_hash=hash_password(PASSWORD), role="admin", organization_id=org_id,
                is_active=True, is_super_admin=False))
    db.commit()
    db.close()
    return name


def _set_active(name, value):
    db = SessionLocal()
    db.query(User).filter(User.username == name).update({"is_active": value})
    db.commit()
    db.close()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_existing_token_stops_working_after_deactivation_and_works_again_on_reactivation(org_id):
    name = _user(org_id)
    token = client.post("/login", data={"username": name, "password": PASSWORD}).json()["access_token"]
    for path in ("/modules", "/auth/me"):
        assert client.get(path, headers=_h(token)).status_code == 200

    _set_active(name, False)
    for path in ("/modules", "/auth/me", "/users"):
        res = client.get(path, headers=_h(token))
        assert res.status_code == 401
        assert res.json() == {"detail": "Could not validate credentials"}
    assert client.post("/auth/mfa/setup", headers=_h(token)).status_code == 401
    assert client.post("/login", data={"username": name, "password": PASSWORD}).status_code == 401

    _set_active(name, True)
    assert client.get("/modules", headers=_h(token)).status_code == 200


def test_the_demo_accounts_are_unaffected():
    for username in ("dennis_admin", "customer2_admin"):
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        db.close()
        assert user is not None and user.is_active is True
