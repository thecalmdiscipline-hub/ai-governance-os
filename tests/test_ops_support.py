"""Batch G, deel 1c: /ops/support-requests (HQ side)."""
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
from app.models.support_request import SupportRequest
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)
PASSWORD = "Correct-Horse-Battery-9"


def _org(prefix):
    db = SessionLocal()
    org = Organization(name=f"{prefix}-{uuid.uuid4().hex[:8]}")
    db.add(org)
    db.commit()
    oid, name = org.id, org.name
    db.close()
    return oid, name


@pytest.fixture(scope="module")
def hq():
    return _org("os-hq")


@pytest.fixture(autouse=True)
def _env(monkeypatch, hq):
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("HQ_ORGANIZATION_ID", str(hq[0]))
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))
    for name in ("RESEND_API_KEY", "SUPPORT_FROM_EMAIL", "SUPPORT_NOTIFY_EMAIL"):
        monkeypatch.delenv(name, raising=False)


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _user(org_id):
    db = SessionLocal()
    name = f"os_{uuid.uuid4().hex[:10]}"
    db.add(User(username=name, password_hash=hash_password(PASSWORD), role="admin", organization_id=org_id,
                is_active=True, is_super_admin=False))
    db.commit()
    db.close()
    return name


def _token(name):
    return client.post("/login", data={"username": name, "password": PASSWORD}).json()["access_token"]


def _ops_tokens(hq_id):
    name = _user(hq_id)
    pre = _token(name)
    secret = client.post("/auth/mfa/setup", headers=_h(pre)).json()["secret"]
    codes = client.post("/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=_h(pre)).json()["backup_codes"]
    db = SessionLocal()
    db.query(User).filter(User.username == name).update({"is_super_admin": True})
    db.commit()
    db.close()
    step1 = client.post("/login", data={"username": name, "password": PASSWORD}).json()
    mfa = client.post("/login/mfa", json={"mfa_token": step1["mfa_token"], "code": codes[0]}).json()["access_token"]
    return pre, mfa


def _customer(org_name_prefix="os-cust"):
    org_id, org_name = _org(org_name_prefix)
    name = _user(org_id)
    return org_id, org_name, name, _token(name)


def _submit(token, subject="Help", message="Please help"):
    res = client.post("/support-requests", json={"category": "question", "subject": subject, "message": message}, headers=_h(token))
    assert res.status_code == 201, res.text
    return res.json()["reference"]


def _id(reference):
    db = SessionLocal()
    try:
        return db.query(SupportRequest).filter(SupportRequest.reference == reference).first().id
    finally:
        db.close()


def _audit(org_id, entity_type, action):
    db = SessionLocal()
    try:
        return db.query(AuditLog).filter(AuditLog.organization_id == org_id, AuditLog.entity_type == entity_type, AuditLog.action == action).count()
    finally:
        db.close()


def test_ops_endpoints_need_ops_access(hq):
    ordinary = _token(_user(hq[0]))
    pre, _mfa = _ops_tokens(hq[0])
    _o, _n, _u, ctoken = _customer()
    rid = _id(_submit(ctoken))
    for method, path, body in (("get", "/ops/support-requests", None), ("patch", f"/ops/support-requests/{rid}", {"status": "done"})):
        kwargs = {"json": body} if body else {}
        assert getattr(client, method)(path, **kwargs).status_code == 401
        assert getattr(client, method)(path, headers=_h(ctoken), **kwargs).status_code == 403  # a customer admin
        assert getattr(client, method)(path, headers=_h(ordinary), **kwargs).status_code == 403  # HQ admin, not super-admin
        assert getattr(client, method)(path, headers=_h(pre), **kwargs).status_code == 403  # super-admin without mfa claim
    db = SessionLocal()
    assert db.query(SupportRequest).filter(SupportRequest.id == rid).first().status == "new"  # the PATCHes changed nothing
    db.close()


def test_list_shows_all_organizations_with_internal_fields_and_filters_by_status(hq):
    _pre, mfa = _ops_tokens(hq[0])
    a_id, a_name, a_user, a_tok = _customer()
    b_id, b_name, b_user, b_tok = _customer()
    ref_a, ref_b = _submit(a_tok, "from A"), _submit(b_tok, "from B")
    items = client.get("/ops/support-requests", headers=_h(mfa)).json()["items"]
    by_ref = {i["reference"]: i for i in items}
    assert by_ref[ref_a]["organization_id"] == a_id and by_ref[ref_a]["organization_name"] == a_name and by_ref[ref_a]["username"] == a_user
    assert by_ref[ref_b]["organization_id"] == b_id
    assert {"notify_status", "notify_error", "notified_at", "message", "subject"} <= set(by_ref[ref_a])

    client.patch(f"/ops/support-requests/{_id(ref_a)}", json={"status": "done"}, headers=_h(mfa))
    done = client.get("/ops/support-requests?status=done", headers=_h(mfa)).json()["items"]
    assert ref_a in [i["reference"] for i in done] and ref_b not in [i["reference"] for i in done]
    assert client.get("/ops/support-requests?status=bogus", headers=_h(mfa)).status_code == 422


def test_status_change_is_audited_in_both_chains_and_both_verify(hq):
    _pre, mfa = _ops_tokens(hq[0])
    org_id, _n, _u, token = _customer()
    ref = _submit(token)
    rid = _id(ref)
    hq_before = _audit(hq[0], "ops", "support_request_status_changed")

    res = client.patch(f"/ops/support-requests/{rid}", json={"status": "in_progress"}, headers=_h(mfa))
    assert res.status_code == 200 and res.json() == {"reference": ref, "status": "in_progress", "changed": True}
    assert _audit(hq[0], "ops", "support_request_status_changed") == hq_before + 1
    assert _audit(org_id, "ops_access", "support_request_status_changed") == 1

    same = client.patch(f"/ops/support-requests/{rid}", json={"status": "in_progress"}, headers=_h(mfa))
    assert same.json()["changed"] is False
    assert _audit(hq[0], "ops", "support_request_status_changed") == hq_before + 1  # a no-op writes no line

    # the customer sees the new status, and both chains verify
    assert client.get("/support-requests", headers=_h(token)).json()["items"][0]["status"] == "in_progress"
    assert client.get("/audit/verify", headers=_h(mfa)).json()["status"] == "valid"
    assert client.get("/audit/verify", headers=_h(token)).json()["status"] == "valid"


def test_only_the_status_can_be_changed_and_it_must_be_valid(hq):
    _pre, mfa = _ops_tokens(hq[0])
    _o, _n, _u, token = _customer()
    ref = _submit(token, subject="original subject", message="original message")
    rid = _id(ref)
    for body in ({"status": "done", "message": "rewritten"}, {"status": "done", "organization_id": 1}, {"subject": "x"}, {"status": "closed"}, {}):
        assert client.patch(f"/ops/support-requests/{rid}", json=body, headers=_h(mfa)).status_code == 422
    db = SessionLocal()
    row = db.query(SupportRequest).filter(SupportRequest.id == rid).first()
    assert (row.status, row.subject, row.message) == ("new", "original subject", "original message")
    db.close()
    assert client.patch("/ops/support-requests/99999999", json={"status": "done"}, headers=_h(mfa)).status_code == 404


def test_a_change_to_one_request_touches_no_other_request(hq):
    _pre, mfa = _ops_tokens(hq[0])
    _o, _n, _u, ta = _customer()
    _o2, _n2, _u2, tb = _customer()
    ra, rb = _submit(ta), _submit(tb)
    client.patch(f"/ops/support-requests/{_id(ra)}", json={"status": "done"}, headers=_h(mfa))
    assert client.get("/support-requests", headers=_h(tb)).json()["items"][0]["status"] == "new"
    assert client.get("/support-requests", headers=_h(ta)).json()["items"][0]["status"] == "done"
    assert rb != ra
