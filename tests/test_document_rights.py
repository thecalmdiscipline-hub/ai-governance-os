"""Fase B5/B5a: upload roles (V6), archive instead of delete (V29), replace (V30),
scope assignment only by Valqeron administrators (B3c), PUT /ops/staff."""
import uuid
from io import BytesIO
from pathlib import Path

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
from app.models.document import Document
from app.models.document_usage import DocumentUsage
from app.models.organization import Organization
from app.models.user import User
from app.models.workflow_run import WorkflowRun

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
def hq():
    return _new_org("dr-hq")


@pytest.fixture(scope="module")
def customer():
    return _new_org("dr-cust")


@pytest.fixture(autouse=True)
def _env(monkeypatch, hq):
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("HQ_ORGANIZATION_ID", str(hq))
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _user(org_id, role="admin", **flags):
    db = SessionLocal()
    name = f"dr_{uuid.uuid4().hex[:10]}"
    u = User(username=name, password_hash=hash_password(PASSWORD), role=role, organization_id=org_id,
             is_active=True, is_super_admin=False, **flags)
    db.add(u)
    db.commit()
    uid = u.id
    db.close()
    return name, uid


def _token(name):
    return client.post("/login", data={"username": name, "password": PASSWORD}).json()["access_token"]


def _mfa_token(name, super_admin=False, valqeron_admin=False):
    pre = _token(name)
    secret = client.post("/auth/mfa/setup", headers=_h(pre)).json()["secret"]
    codes = client.post("/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=_h(pre)).json()["backup_codes"]
    db = SessionLocal()
    db.query(User).filter(User.username == name).update(
        {"is_super_admin": super_admin, "is_valqeron_admin": valqeron_admin}
    )
    db.commit()
    db.close()
    step1 = client.post("/login", data={"username": name, "password": PASSWORD}).json()
    return client.post("/login/mfa", json={"mfa_token": step1["mfa_token"], "code": codes[0]}).json()["access_token"]


def _upload(token, name="[scope=kennis] r.txt", body=b"scope: kennis\nbody"):
    return client.post("/documents/upload", headers=_h(token), files={"file": (name, BytesIO(body), "text/plain")})


def _uncoded_doc(org_id):
    stored = f"{uuid.uuid4().hex}_legacy.txt"
    d = Path(f"uploaded_documents/org_{org_id}")
    d.mkdir(parents=True, exist_ok=True)
    (d / stored).write_text("legacy", encoding="utf-8")
    db = SessionLocal()
    doc = Document(organization_id=org_id, filename="legacy.txt", stored_name=stored, path=str(d / stored), size=6)
    db.add(doc)
    db.commit()
    did = doc.id
    db.close()
    return did


def _mark_used(document_id, org_id):
    db = SessionLocal()
    run_id = str(uuid.uuid4())
    db.add(WorkflowRun(run_id=run_id, workflow="document_knowledge", organization_id=org_id, status="ok"))
    db.commit()
    db.add(DocumentUsage(run_id=run_id, document_id=document_id, codes="kennis"))
    db.commit()
    db.close()


def _doc(document_id):
    db = SessionLocal()
    try:
        row = db.get(Document, document_id)
        return None if row is None else {"status": row.scope_status, "codes": sorted(c.code for c in row.scope_codes)}
    finally:
        db.close()


# --- V6: upload roles -------------------------------------------------------

@pytest.mark.parametrize("role", ["auditor", "member"])
def test_auditor_and_member_may_not_upload(customer, role):  # test 14
    name, _ = _user(customer, role=role)
    res = _upload(_token(name))
    assert res.status_code == 403


@pytest.mark.parametrize("role", ["admin", "operator"])
def test_admin_and_operator_may_upload(customer, role):
    name, _ = _user(customer, role=role)
    assert _upload(_token(name)).status_code == 200


# --- V29 / V30 --------------------------------------------------------------

def test_used_document_is_archived_not_deleted(customer):  # test 9
    name, _ = _user(customer)
    token = _token(name)
    doc_id = _upload(token, name=f"[scope=kennis] used-{uuid.uuid4().hex[:6]}.txt").json()["document"]["id"]
    _mark_used(doc_id, customer)

    res = client.delete(f"/documents/{doc_id}", headers=_h(token))
    assert res.status_code == 200
    assert res.json()["archived"]["id"] == doc_id
    assert _doc(doc_id)["status"] == "archived"

    db = SessionLocal()
    row = db.get(Document, doc_id)
    assert Path(row.path).exists()
    actions = [a.action for a in db.query(AuditLog).filter(AuditLog.entity_type == "document", AuditLog.entity_id == doc_id)]
    db.close()
    assert "archived" in actions and "deleted" not in actions


def test_unused_document_is_still_deleted(customer):
    name, _ = _user(customer)
    token = _token(name)
    doc_id = _upload(token, name=f"[scope=kennis] unused-{uuid.uuid4().hex[:6]}.txt").json()["document"]["id"]
    res = client.delete(f"/documents/{doc_id}", headers=_h(token))
    assert res.status_code == 200
    assert res.json()["deleted"]["id"] == doc_id
    assert _doc(doc_id) is None


def test_new_upload_with_same_name_archives_previous_version(customer):  # V30
    name, _ = _user(customer)
    token = _token(name)
    fname = f"[scope=kennis] handboek-{uuid.uuid4().hex[:6]}.txt"
    first = _upload(token, name=fname, body=b"scope: kennis\nv1").json()["document"]["id"]
    second = _upload(token, name=fname, body=b"scope: kennis\nv2").json()
    assert second["replaced_document_ids"] == [first]
    assert _doc(first)["status"] == "archived"
    assert _doc(second["document"]["id"])["status"] == "coded"


# --- B3c / B5a: scope assignment --------------------------------------------

def test_customer_admin_gets_403_on_scope_assignment(customer):
    doc_id = _uncoded_doc(customer)
    name, _ = _user(customer, role="admin")
    res = client.patch(f"/documents/{doc_id}/scope", json={"codes": ["kennis"]}, headers=_h(_token(name)))
    assert res.status_code == 403
    assert _doc(doc_id)["status"] == "uncoded"


def test_customer_admin_with_flag_and_mfa_still_gets_403(customer):
    # The flag only counts for an HQ user (it can only be set through /ops/staff anyway).
    doc_id = _uncoded_doc(customer)
    name, _ = _user(customer, role="admin")
    token = _mfa_token(name, valqeron_admin=True)
    assert client.patch(f"/documents/{doc_id}/scope", json={"codes": ["kennis"]}, headers=_h(token)).status_code == 403


def test_hq_user_without_flag_or_without_mfa_gets_403(hq, customer):
    doc_id = _uncoded_doc(customer)
    no_flag, _ = _user(hq)
    assert client.patch(f"/documents/{doc_id}/scope", json={"codes": ["kennis"]},
                        headers=_h(_mfa_token(no_flag))).status_code == 403
    flag_no_mfa, _ = _user(hq, is_valqeron_admin=True)
    assert client.patch(f"/documents/{doc_id}/scope", json={"codes": ["kennis"]},
                        headers=_h(_token(flag_no_mfa))).status_code == 403


def test_valqeron_admin_assigns_codes_once(hq, customer):
    doc_id = _uncoded_doc(customer)
    name, _ = _user(hq)
    token = _mfa_token(name, valqeron_admin=True)

    bad = client.patch(f"/documents/{doc_id}/scope", json={"codes": ["onbekend"]}, headers=_h(token))
    assert bad.status_code == 422
    hr_mix = client.patch(f"/documents/{doc_id}/scope", json={"codes": ["hr", "gedeeld"]}, headers=_h(token))
    assert hr_mix.status_code == 422

    ok = client.patch(f"/documents/{doc_id}/scope", json={"codes": ["kennis", "gedeeld"]}, headers=_h(token))
    assert ok.status_code == 200
    assert _doc(doc_id) == {"status": "coded", "codes": ["gedeeld", "kennis"]}

    again = client.patch(f"/documents/{doc_id}/scope", json={"codes": ["sales"]}, headers=_h(token))
    assert again.status_code == 409  # V7: fixed once coded
    assert _doc(doc_id)["codes"] == ["gedeeld", "kennis"]

    db = SessionLocal()
    hq_lines = db.query(AuditLog).filter(AuditLog.organization_id == hq, AuditLog.action == "document_scope_assigned").count()
    cust_lines = db.query(AuditLog).filter(AuditLog.organization_id == customer, AuditLog.action == "document_scope_assigned").count()
    db.close()
    assert hq_lines >= 1 and cust_lines >= 1


# --- PUT /ops/staff ---------------------------------------------------------

def test_ops_staff_sets_flag_only_for_hq_users_and_only_via_ops(hq, customer):
    staff_name, staff_id = _user(hq)
    cust_name, cust_id = _user(customer)

    # an ordinary customer admin cannot reach /ops
    assert client.put(f"/ops/staff/{staff_id}", json={"is_valqeron_admin": True},
                      headers=_h(_token(cust_name))).status_code == 403

    ops_name, _ = _user(hq)
    ops = _mfa_token(ops_name, super_admin=True)

    res = client.put(f"/ops/staff/{staff_id}", json={"is_valqeron_admin": True}, headers=_h(ops))
    assert res.status_code == 200 and res.json()["changed"] is True
    assert client.put(f"/ops/staff/{cust_id}", json={"is_valqeron_admin": True}, headers=_h(ops)).status_code == 422
    assert client.put(f"/ops/staff/{staff_id}", json={"is_valqeron_admin": True, "role": "admin"},
                      headers=_h(ops)).status_code == 422

    db = SessionLocal()
    assert db.get(User, staff_id).is_valqeron_admin is True
    assert db.get(User, cust_id).is_valqeron_admin is False
    assert db.query(AuditLog).filter(AuditLog.organization_id == hq, AuditLog.action == "valqeron_admin_granted").count() >= 1
    db.close()
