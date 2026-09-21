"""Batch G, deel 1a: POST/GET /support-requests (customer side). No network."""
import json
import re
import uuid
from datetime import datetime, timedelta

import pytest
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


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch):
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))


@pytest.fixture(autouse=True)
def _no_mail_config(monkeypatch):
    # never let a developer's .env make a test talk to Resend
    for name in ("RESEND_API_KEY", "SUPPORT_FROM_EMAIL", "SUPPORT_NOTIFY_EMAIL"):
        monkeypatch.delenv(name, raising=False)


def _org():
    db = SessionLocal()
    org = Organization(name=f"sr-org-{uuid.uuid4().hex[:8]}")
    db.add(org)
    db.commit()
    oid = org.id
    db.close()
    return oid


def _user(org_id):
    db = SessionLocal()
    name = f"sr_{uuid.uuid4().hex[:10]}"
    user = User(username=name, password_hash=hash_password(PASSWORD), role="admin", organization_id=org_id, is_active=True, is_super_admin=False)
    db.add(user)
    db.commit()
    uid = user.id
    db.close()
    token = client.post("/login", data={"username": name, "password": PASSWORD}).json()["access_token"]
    return name, uid, token


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _body(**overrides):
    body = {"category": "question", "subject": "How do I add a user?", "message": "Please explain how to add a colleague."}
    body.update(overrides)
    return body


def _row(reference):
    db = SessionLocal()
    try:
        return db.query(SupportRequest).filter(SupportRequest.reference == reference).first()
    finally:
        db.close()


# ---------------------------------------------------------------------------

def test_requires_authentication():
    assert client.post("/support-requests", json=_body()).status_code == 401
    assert client.get("/support-requests").status_code == 401


def test_creates_a_request_for_the_own_organization_and_user():
    org = _org()
    name, uid, token = _user(org)
    res = client.post("/support-requests", json=_body(), headers=_h(token))
    assert res.status_code == 201, res.text
    data = res.json()
    assert set(data) == {"reference", "status", "created_at"}
    assert re.fullmatch(r"SR-\d{6}", data["reference"]) and data["status"] == "new"
    row = _row(data["reference"])
    assert row.organization_id == org and row.user_id == uid
    assert row.category == "question" and row.status == "new" and row.notify_status == "skipped_no_config"
    assert row.reference == f"SR-{row.id:06d}"


def test_organization_user_and_status_in_the_body_are_ignored():
    org_a, org_b = _org(), _org()
    _name, uid, token = _user(org_a)
    res = client.post("/support-requests", json=_body(organization_id=org_b, user_id=999999, status="done", reference="SR-000001"), headers=_h(token))
    assert res.status_code == 201
    row = _row(res.json()["reference"])
    assert row.organization_id == org_a and row.user_id == uid and row.status == "new"
    assert row.reference != "SR-000001" or row.id == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"subject": "x" * 201},
        {"message": "y" * 5001},
        {"subject": "   "},
        {"message": ""},
        {"category": "nonsense"},
    ],
)
def test_validation_rejects_bad_input_and_stores_nothing(overrides):
    _n, uid, token = _user(_org())
    assert client.post("/support-requests", json=_body(**overrides), headers=_h(token)).status_code == 422
    db = SessionLocal()
    assert db.query(SupportRequest).filter(SupportRequest.user_id == uid).count() == 0
    db.close()


def test_boundaries_and_all_categories_are_accepted():
    _n, _u, token = _user(_org())
    assert client.post("/support-requests", json=_body(subject="s" * 200, message="m" * 5000), headers=_h(token)).status_code == 201
    for category in ("problem", "access", "other"):
        assert client.post("/support-requests", json=_body(category=category), headers=_h(token)).status_code in (201, 429)


def test_hourly_limit_is_5_per_user_and_does_not_affect_other_users():
    org = _org()
    _n1, _u1, t1 = _user(org)
    _n2, _u2, t2 = _user(org)
    for _ in range(5):
        assert client.post("/support-requests", json=_body(), headers=_h(t1)).status_code == 201
    sixth = client.post("/support-requests", json=_body(), headers=_h(t1))
    assert sixth.status_code == 429
    assert sixth.json()["error"] == "too_many_requests" and "per hour" in sixth.json()["message"]
    assert int(sixth.headers["retry-after"]) > 0
    assert client.post("/support-requests", json=_body(), headers=_h(t2)).status_code == 201  # another user, same org


def test_daily_limit_is_20_per_user():
    org = _org()
    _n, uid, token = _user(org)
    old = datetime.utcnow() - timedelta(hours=3)  # outside the hourly window, inside the daily one
    db = SessionLocal()
    for i in range(20):
        db.add(SupportRequest(reference=f"TMP-{uuid.uuid4().hex}", organization_id=org, user_id=uid, category="other",
                              subject="old", message="old", status="new", created_at=old, updated_at=old))
    db.commit()
    db.close()
    res = client.post("/support-requests", json=_body(), headers=_h(token))
    assert res.status_code == 429 and "per day" in res.json()["message"]


def test_list_is_tenant_scoped_newest_first_and_has_no_internal_fields():
    org_a, org_b = _org(), _org()
    _na, _ua, ta = _user(org_a)
    _nb, _ub, tb = _user(org_b)
    first = client.post("/support-requests", json=_body(subject="first"), headers=_h(ta)).json()["reference"]
    second = client.post("/support-requests", json=_body(subject="second"), headers=_h(ta)).json()["reference"]
    other = client.post("/support-requests", json=_body(subject="other tenant"), headers=_h(tb)).json()["reference"]

    a_items = client.get("/support-requests", headers=_h(ta)).json()["items"]
    assert [i["reference"] for i in a_items] == [second, first]
    assert other not in json.dumps(a_items)
    for item in a_items:
        assert set(item) == {"reference", "category", "subject", "message", "status", "created_at", "updated_at"}
    b_items = client.get("/support-requests", headers=_h(tb)).json()["items"]
    assert [i["reference"] for i in b_items] == [other]


def test_audit_line_in_the_own_chain_holds_no_text_and_the_chain_verifies(caplog):
    org = _org()
    name, _uid, token = _user(org)
    marker = f"SECRET-MARKER-{uuid.uuid4().hex}"
    caplog.set_level("DEBUG")
    res = client.post("/support-requests", json=_body(subject=f"subject {marker}", message=f"message {marker}"), headers=_h(token))
    assert res.status_code == 201
    db = SessionLocal()
    lines = db.query(AuditLog).filter(AuditLog.organization_id == org, AuditLog.action == "support_request_created").all()
    everything = json.dumps([[r.details, r.performed_by] for r in db.query(AuditLog).all()])
    db.close()
    assert len(lines) == 1 and lines[0].performed_by == name and res.json()["reference"] in lines[0].details
    assert marker not in everything and marker not in caplog.text
    assert client.get("/audit/verify", headers=_h(token)).json()["status"] == "valid"
