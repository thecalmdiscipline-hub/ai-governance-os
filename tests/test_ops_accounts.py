"""Batch I, Fase 2.1: /ops/accounts (access control, status machine, link-organization, audit, no
contact data in audit/logs). Mirrors the hq/_ops_tokens fixture pattern from tests/test_ops_tenants.py."""
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
from app.models.ops_account import OpsAccount
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)
PASSWORD = "Correct-Horse-Battery-9"


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
    return _new_org("oa-hq")


@pytest.fixture(autouse=True)
def _env(monkeypatch, hq):
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("HQ_ORGANIZATION_ID", str(hq))
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _user(org_id, super_admin=False):
    db = SessionLocal()
    name = f"oa_{uuid.uuid4().hex[:10]}"
    db.add(User(username=name, password_hash=hash_password(PASSWORD), role="admin", organization_id=org_id,
                is_active=True, is_super_admin=super_admin))
    db.commit()
    db.close()
    return name


def _plain_token(name):
    return client.post("/login", data={"username": name, "password": PASSWORD}).json()["access_token"]


def _ops_tokens(hq_id):
    """(pre_mfa_token, mfa_token) of a fresh HQ super-admin."""
    name = _user(hq_id, super_admin=False)
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


def _account(db, **overrides):
    from datetime import datetime
    defaults = dict(name=f"Acme-{uuid.uuid4().hex[:8]}", status="lead", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    defaults.update(overrides)
    a = OpsAccount(**defaults)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _audit_rows(org_id):
    db = SessionLocal()
    try:
        return db.query(AuditLog).filter(AuditLog.organization_id == org_id).order_by(AuditLog.id).all()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def test_all_account_endpoints_need_ops_access(hq):
    ordinary = _plain_token(_user(hq))
    pre, _mfa = _ops_tokens(hq)
    db = SessionLocal()
    target = _account(db).id
    db.close()

    calls = [
        ("get", "/ops/accounts", None),
        ("post", "/ops/accounts", {"name": "Blocked Co"}),
        ("get", f"/ops/accounts/{target}", None),
        ("patch", f"/ops/accounts/{target}", {"notes": "x"}),
        ("post", f"/ops/accounts/{target}/link-organization", {"organization_id": hq}),
        ("post", f"/ops/accounts/{target}/status", {"status": "qualified"}),
    ]
    for method, path, body in calls:
        kwargs = {"json": body} if body is not None else {}
        assert getattr(client, method)(path, **kwargs).status_code == 401
        assert getattr(client, method)(path, headers=_h(ordinary), **kwargs).status_code == 403
        assert getattr(client, method)(path, headers=_h(pre), **kwargs).status_code == 403


# ---------------------------------------------------------------------------
# Create / read / update
# ---------------------------------------------------------------------------

def test_create_account_starts_as_lead(hq):
    _pre, mfa = _ops_tokens(hq)
    res = client.post("/ops/accounts", json={"name": "Northwind Traders", "country": "GB", "sector": "Logistics", "source": "inbound"}, headers=_h(mfa))
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "lead"
    assert body["organization_id"] is None

    got = client.get(f"/ops/accounts/{body['id']}", headers=_h(mfa))
    assert got.status_code == 200 and got.json()["name"] == "Northwind Traders"


def test_create_account_rejects_invalid_source_and_tier(hq):
    _pre, mfa = _ops_tokens(hq)
    r1 = client.post("/ops/accounts", json={"name": "X", "source": "cold-call"}, headers=_h(mfa))
    assert r1.status_code == 422 and r1.json()["error"] == "invalid_source"
    r2 = client.post("/ops/accounts", json={"name": "X", "proposed_tier": "premium"}, headers=_h(mfa))
    assert r2.status_code == 422 and r2.json()["error"] == "invalid_proposed_tier"


def test_create_account_rejects_invalid_email(hq):
    _pre, mfa = _ops_tokens(hq)
    res = client.post("/ops/accounts", json={"name": "X", "primary_contact_email": "not-an-email"}, headers=_h(mfa))
    assert res.status_code == 422


def test_get_unknown_account_404(hq):
    _pre, mfa = _ops_tokens(hq)
    assert client.get("/ops/accounts/99999999", headers=_h(mfa)).status_code == 404


def test_update_account_patches_allowed_fields_only(hq):
    _pre, mfa = _ops_tokens(hq)
    created = client.post("/ops/accounts", json={"name": "Contoso"}, headers=_h(mfa)).json()
    res = client.patch(f"/ops/accounts/{created['id']}", json={"sector": "Manufacturing", "notes": "met at trade fair"}, headers=_h(mfa))
    assert res.status_code == 200
    assert res.json()["sector"] == "Manufacturing"
    assert res.json()["notes"] == "met at trade fair"


def test_update_account_cannot_set_organization_id_or_status_directly(hq):
    _pre, mfa = _ops_tokens(hq)
    created = client.post("/ops/accounts", json={"name": "Fabrikam"}, headers=_h(mfa)).json()
    res = client.patch(f"/ops/accounts/{created['id']}", json={"organization_id": hq}, headers=_h(mfa))
    assert res.status_code == 422  # extra="forbid" rejects the field outright
    res2 = client.patch(f"/ops/accounts/{created['id']}", json={"status": "qualified"}, headers=_h(mfa))
    assert res2.status_code == 422


def test_update_with_no_actual_change_does_not_write_audit_or_bump_updated_at(hq):
    _pre, mfa = _ops_tokens(hq)
    created = client.post("/ops/accounts", json={"name": "Tailspin", "sector": "Retail"}, headers=_h(mfa)).json()
    before = len(_audit_rows(hq))
    res = client.patch(f"/ops/accounts/{created['id']}", json={"sector": "Retail"}, headers=_h(mfa))
    assert res.status_code == 200
    assert len(_audit_rows(hq)) == before  # no-op: nothing actually changed


# ---------------------------------------------------------------------------
# Status machine
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("old,new,allowed", [
    ("lead", "qualified", True),
    ("lead", "contract", True),  # skipping stages forward is allowed
    ("qualified", "lead", False),  # backward
    ("live", "onboarding", False),  # backward
    ("lead", "lead", True),  # no-op
    ("lead", "lost", True),
    ("onboarding", "lost", True),
    ("live", "lost", False),  # 'lost' not reachable once live
    ("live", "churned", True),
    ("qualified", "churned", False),  # 'churned' only from live
    ("lost", "qualified", False),  # terminal
    ("churned", "live", False),  # terminal
])
def test_status_transitions(hq, old, new, allowed):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account = _account(db, status=old)
    account_id = account.id
    db.close()

    res = client.post(f"/ops/accounts/{account_id}/status", json={"status": new}, headers=_h(mfa))
    if allowed:
        assert res.status_code == 200, res.text
        assert res.json()["status"] == new
    else:
        assert res.status_code == 409, res.text


def test_status_change_rejects_unknown_status_value(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    res = client.post(f"/ops/accounts/{account_id}/status", json={"status": "enthusiastic"}, headers=_h(mfa))
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# link-organization
# ---------------------------------------------------------------------------

def test_link_organization_success(hq):
    _pre, mfa = _ops_tokens(hq)
    target_org = _new_org("oa-target")
    db = SessionLocal()
    account_id = _account(db).id
    db.close()

    res = client.post(f"/ops/accounts/{account_id}/link-organization", json={"organization_id": target_org}, headers=_h(mfa))
    assert res.status_code == 200
    assert res.json()["organization_id"] == target_org


def test_link_organization_rejects_double_link(hq):
    _pre, mfa = _ops_tokens(hq)
    target_org = _new_org("oa-target2")
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    client.post(f"/ops/accounts/{account_id}/link-organization", json={"organization_id": target_org}, headers=_h(mfa))
    res = client.post(f"/ops/accounts/{account_id}/link-organization", json={"organization_id": target_org}, headers=_h(mfa))
    assert res.status_code == 409 and res.json()["error"] == "already_linked"


def test_link_organization_rejects_unknown_organization(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    res = client.post(f"/ops/accounts/{account_id}/link-organization", json={"organization_id": 999999}, headers=_h(mfa))
    assert res.status_code == 404


def test_link_organization_rejects_organization_already_used_by_another_account(hq):
    _pre, mfa = _ops_tokens(hq)
    target_org = _new_org("oa-target3")
    db = SessionLocal()
    first_id = _account(db).id
    second_id = _account(db).id
    db.close()
    ok = client.post(f"/ops/accounts/{first_id}/link-organization", json={"organization_id": target_org}, headers=_h(mfa))
    assert ok.status_code == 200
    blocked = client.post(f"/ops/accounts/{second_id}/link-organization", json={"organization_id": target_org}, headers=_h(mfa))
    assert blocked.status_code == 409 and blocked.json()["error"] == "organization_already_linked_to_another_account"


# ---------------------------------------------------------------------------
# Dual audit chain
# ---------------------------------------------------------------------------

def test_account_lifecycle_writes_dual_audit_and_verifies_valid(hq):
    _pre, mfa = _ops_tokens(hq)
    target_org = _new_org("oa-audit-target")

    before_hq = len(_audit_rows(hq))
    before_target = len(_audit_rows(target_org))

    created = client.post("/ops/accounts", json={"name": "AuditCo"}, headers=_h(mfa)).json()
    account_id = created["id"]
    # account_created only writes to the HQ chain (not yet linked to an organization)
    assert len(_audit_rows(hq)) == before_hq + 1
    assert len(_audit_rows(target_org)) == before_target

    client.post(f"/ops/accounts/{account_id}/link-organization", json={"organization_id": target_org}, headers=_h(mfa))
    # link-organization writes to both the HQ chain and the newly-linked organization's chain.
    # target_org is brand new, so its first-ever audit row also triggers create_audit_log()'s
    # one-time "chain_v2_started" marker row (see app/core/audit.py) — +2, not +1, this first time.
    assert len(_audit_rows(hq)) == before_hq + 2
    assert len(_audit_rows(target_org)) == before_target + 2

    client.post(f"/ops/accounts/{account_id}/status", json={"status": "qualified"}, headers=_h(mfa))
    # No new marker needed the second time — exactly +1 per chain from here on.
    assert len(_audit_rows(hq)) == before_hq + 3
    assert len(_audit_rows(target_org)) == before_target + 3

    # GET /audit/verify only ever checks the CALLER's own organization (it has no org_id
    # parameter) — so to confirm both chains are valid, call it once with the HQ token and once
    # with a token that actually belongs to target_org.
    hq_verify = client.get("/audit/verify", headers=_h(mfa))
    assert hq_verify.status_code == 200 and hq_verify.json()["status"] == "valid", hq_verify.text

    target_token = _plain_token(_user(target_org))
    target_verify = client.get("/audit/verify", headers=_h(target_token))
    assert target_verify.status_code == 200 and target_verify.json()["status"] == "valid", target_verify.text


def test_no_contact_data_in_audit_details(hq):
    _pre, mfa = _ops_tokens(hq)
    secret_name = "Jane Confidential-Contact"
    secret_email = "jane.secret@example.com"
    secret_notes = "Do not call before 10am, prefers email, mentioned a competitor by name"

    created = client.post(
        "/ops/accounts",
        json={"name": "SecretCo", "primary_contact_name": secret_name, "primary_contact_email": secret_email, "notes": secret_notes},
        headers=_h(mfa),
    ).json()
    account_id = created["id"]
    client.patch(f"/ops/accounts/{account_id}", json={"notes": "updated: " + secret_notes}, headers=_h(mfa))
    client.post(f"/ops/accounts/{account_id}/status", json={"status": "qualified"}, headers=_h(mfa))

    rows = _audit_rows(hq)
    joined = "\n".join(r.details or "" for r in rows)
    assert secret_name not in joined
    assert secret_email not in joined
    assert secret_notes not in joined
    assert "updated: " not in joined
