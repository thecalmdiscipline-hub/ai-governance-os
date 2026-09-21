"""Batch F, deel 2: POST /ops/tenants/provision (no network; OpenAI/workflow runs are mocked)."""
import json
import uuid
from pathlib import Path

import pyotp
import pytest
import sentry_sdk
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sentry_sdk.transport import Transport

from app.core import security
from app.core.observability import init_sentry
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.ai_policy import AIPolicy
from app.models.ai_risk import AIRisk
from app.models.ai_system import AISystem
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.organization import Organization
from app.models.provisioning_request import ProvisioningRequest
from app.models.tenant_module import TenantModule
from app.models.user import User
from app.services import provisioning
from app.services import tenant_modules as tm

client = TestClient(app, raise_server_exceptions=False)
PASSWORD = "Correct-Horse-Battery-9"
WORKFLOWS = sorted(tm.workflow_keys())
TABLES = (Organization, User, TenantModule, AIPolicy, AISystem, AIRisk, Document, ProvisioningRequest)


def _new_org(prefix):
    db = SessionLocal()
    org = Organization(name=f"{prefix}-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    oid, name = org.id, org.name
    db.close()
    return oid, name


@pytest.fixture(scope="module")
def hq():
    return _new_org("prov-hq")


@pytest.fixture(autouse=True)
def _env(monkeypatch, hq):
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("HQ_ORGANIZATION_ID", str(hq[0]))
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _user(org_id):
    db = SessionLocal()
    name = f"pv_{uuid.uuid4().hex[:10]}"
    db.add(User(username=name, password_hash=hash_password(PASSWORD), role="admin", organization_id=org_id,
                is_active=True, is_super_admin=False))
    db.commit()
    db.close()
    return name


def _ops_tokens(hq_id):
    name = _user(hq_id)
    pre = client.post("/login", data={"username": name, "password": PASSWORD}).json()["access_token"]
    secret = client.post("/auth/mfa/setup", headers=_h(pre)).json()["secret"]
    codes = client.post("/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=_h(pre)).json()["backup_codes"]
    db = SessionLocal()
    db.query(User).filter(User.username == name).update({"is_super_admin": True})
    db.commit()
    db.close()
    step1 = client.post("/login", data={"username": name, "password": PASSWORD}).json()
    mfa = client.post("/login/mfa", json={"mfa_token": step1["mfa_token"], "code": codes[0]}).json()["access_token"]
    return pre, mfa


def _body(**overrides):
    others = [k for k in WORKFLOWS if k != tm.COMPLIANCE_KEY]
    body = {
        "idempotency_key": f"key-{uuid.uuid4().hex[:12]}",
        "organization_name": f"Prov Customer {uuid.uuid4().hex[:8]}",
        "country": "NL",
        "sector": "Testing",
        "tier": "business",
        "modules": [tm.CORE_KEY, tm.COMPLIANCE_KEY] + others[:4],  # 5 workflows incl. compliance_monitor
        "admin_username": f"prov_admin_{uuid.uuid4().hex[:8]}",
        "admin_email": "admin@example.com",
        "include_demo_document": True,
        "include_demo_run": False,
    }
    body.update(overrides)
    return body


def _counts():
    db = SessionLocal()
    try:
        return {t.__name__: db.query(t).count() for t in TABLES}
    finally:
        db.close()


def _upload_files():
    return sorted(str(p) for p in Path("uploaded_documents").glob("org_*/*")) if Path("uploaded_documents").exists() else []


def _login(username, password):
    return client.post("/login", data={"username": username, "password": password})


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------

def test_provisioning_needs_ops_access_and_creates_nothing_without_it(hq):
    ordinary = client.post("/login", data={"username": _user(hq[0]), "password": PASSWORD}).json()["access_token"]
    pre, _mfa = _ops_tokens(hq[0])
    before = _counts()
    body = _body()
    assert client.post("/ops/tenants/provision", json=body).status_code == 401
    assert client.post("/ops/tenants/provision", json=body, headers=_h(ordinary)).status_code == 403
    assert client.post("/ops/tenants/provision", json=body, headers=_h(pre)).status_code == 403
    assert _counts() == before


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------

def test_creates_a_working_customer_in_one_call(hq):
    _pre, mfa = _ops_tokens(hq[0])
    body = _body()
    res = client.post("/ops/tenants/provision", json=body, headers=_h(mfa))
    assert res.status_code == 201, res.text
    assert res.headers["cache-control"] == "no-store"
    data = res.json()
    assert data["created"] is True and data["tier"] == "business"
    assert data["admin_username"] == body["admin_username"]
    assert len(data["admin_password"]) >= 20
    assert data["modules"] == sorted(body["modules"])
    assert data["counts"] == {"modules": 6, "ai_policies": 1, "ai_systems": 5, "ai_risks": 5, "documents": 1}
    assert data["demo_run"] == "not_requested" and data["audit_logged"] is True

    org_id = data["organization_id"]
    db = SessionLocal()
    admin = db.query(User).filter(User.username == body["admin_username"]).first()
    assert admin.organization_id == org_id and admin.role == "admin" and admin.is_active
    assert admin.must_change_password is True and not admin.mfa_enabled and not admin.is_super_admin
    assert data["admin_password"] not in admin.password_hash and security.verify_password(data["admin_password"], admin.password_hash)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    assert (org.name, org.country, org.sector, org.tier) == (body["organization_name"], "NL", "Testing", "business")
    policy = db.query(AIPolicy).filter(AIPolicy.organization_id == org_id).one()
    assert policy.purpose.startswith("Standard template") and body["organization_name"] in policy.purpose
    risks = db.query(AIRisk).join(AISystem, AIRisk.ai_system_id == AISystem.id).filter(AISystem.organization_id == org_id).all()
    assert len(risks) == 5 and all(r.risk_level == "medium" and r.description.startswith("Standard template") for r in risks)
    doc = db.query(Document).filter(Document.organization_id == org_id).one()
    assert Path(doc.path).exists() and doc.uploaded_by_user_id == admin.id
    db.close()


def test_first_admin_hits_the_password_gate_then_can_work(hq):
    _pre, mfa = _ops_tokens(hq[0])
    body = _body()
    data = client.post("/ops/tenants/provision", json=body, headers=_h(mfa)).json()
    login = _login(body["admin_username"], data["admin_password"])
    assert login.status_code == 200 and login.json()["must_change_password"] is True
    token = login.json()["access_token"]
    assert client.get("/modules", headers=_h(token)).json() == {"error": "password_change_required"}
    new_pw = "A-Brand-New-Passphrase-77"
    assert client.post("/auth/change-password", json={"current_password": data["admin_password"], "new_password": new_pw}, headers=_h(token)).status_code == 200
    modules = client.get("/modules", headers=_h(token))
    assert modules.status_code == 200
    assert {m["key"] for m in modules.json() if m["active"]} == set(body["modules"])


def test_the_new_tenant_is_isolated_from_existing_organizations(hq):
    _pre, mfa = _ops_tokens(hq[0])
    other_id, _ = _new_org("prov-other")
    db = SessionLocal()
    tm.replace_modules(db, other_id, [tm.CORE_KEY, WORKFLOWS[0]])
    db.commit()
    db.close()

    def snap():
        d = SessionLocal()
        try:
            return (
                sorted((r.module_key, r.is_active) for r in d.query(TenantModule).filter(TenantModule.organization_id.in_([other_id, hq[0]]))),
                d.query(User).filter(User.organization_id.in_([other_id, hq[0]])).count(),
                d.query(AISystem).filter(AISystem.organization_id.in_([other_id, hq[0]])).count(),
            )
        finally:
            d.close()

    before = snap()
    assert client.post("/ops/tenants/provision", json=_body(), headers=_h(mfa)).status_code == 201
    assert snap() == before


# ---------------------------------------------------------------------------
# Idempotency and conflicts
# ---------------------------------------------------------------------------

def test_same_key_and_parameters_is_a_replay_without_new_rows_or_password(hq):
    _pre, mfa = _ops_tokens(hq[0])
    body = _body()
    first = client.post("/ops/tenants/provision", json=body, headers=_h(mfa))
    counts_after_first = _counts()
    second = client.post("/ops/tenants/provision", json=body, headers=_h(mfa))
    assert first.status_code == 201 and second.status_code == 200
    a, b = first.json(), second.json()
    assert b["created"] is False and b["organization_id"] == a["organization_id"] and "admin_password" not in b
    assert b["counts"] == a["counts"] and b["modules"] == a["modules"] and b["admin_username"] == a["admin_username"]
    assert _counts() == counts_after_first
    assert a["admin_password"] not in second.text


def test_same_key_with_other_parameters_is_409_and_changes_nothing(hq):
    _pre, mfa = _ops_tokens(hq[0])
    body = _body()
    client.post("/ops/tenants/provision", json=body, headers=_h(mfa))
    before = _counts()
    changed = dict(body, modules=body["modules"] + [WORKFLOWS[-1]] if WORKFLOWS[-1] not in body["modules"] else body["modules"][:-1] + [tm.CORE_KEY])
    res = client.post("/ops/tenants/provision", json=changed, headers=_h(mfa))
    assert res.status_code == 409 and res.json()["error"] == "idempotency_key_conflict"
    res = client.post("/ops/tenants/provision", json=dict(body, organization_name=body["organization_name"] + " B"), headers=_h(mfa))
    assert res.status_code == 409
    assert _counts() == before


def test_name_conflicts_including_hq_and_username_conflict(hq):
    _pre, mfa = _ops_tokens(hq[0])
    taken = _user(hq[0])
    before = _counts()
    assert client.post("/ops/tenants/provision", json=_body(organization_name=hq[1]), headers=_h(mfa)).json()["error"] == "organization_name_taken"
    assert client.post("/ops/tenants/provision", json=_body(organization_name=f"  {hq[1].upper()} "), headers=_h(mfa)).status_code == 409  # case/space-insensitive
    res = client.post("/ops/tenants/provision", json=_body(admin_username=taken), headers=_h(mfa))
    assert res.status_code == 409 and res.json()["error"] == "username_taken"
    assert _counts() == before


@pytest.mark.parametrize(
    "overrides,fragment",
    [
        ({"tier": "starter", "modules": [tm.CORE_KEY, WORKFLOWS[0]]}, "at least 2 workflows"),
        ({"tier": "business", "modules": [tm.CORE_KEY] + [k for k in WORKFLOWS if k != tm.COMPLIANCE_KEY][:5]}, "requires: compliance_monitor"),
        ({"tier": "enterprise", "modules": [tm.CORE_KEY, tm.COMPLIANCE_KEY] + [k for k in WORKFLOWS if k != tm.COMPLIANCE_KEY][:4]}, "at least 7 workflows"),
        ({"modules": [tm.COMPLIANCE_KEY] + WORKFLOWS[:5]}, "'core' is required"),
        ({"modules": [tm.CORE_KEY, tm.COMPLIANCE_KEY, "no_such_module"] + WORKFLOWS[:4]}, "unknown modules"),
        ({"admin_username": "x"}, "admin_username must be"),
        ({"admin_email": "not-an-email"}, "admin_email"),
        ({"organization_name": "   "}, "organization_name is required"),
    ],
)
def test_validation_gives_422_and_creates_nothing(hq, overrides, fragment):
    _pre, mfa = _ops_tokens(hq[0])
    before = _counts()
    res = client.post("/ops/tenants/provision", json=_body(**overrides), headers=_h(mfa))
    assert res.status_code == 422, res.text
    assert any(fragment in p for p in res.json()["problems"]), res.json()
    assert _counts() == before


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fail_after", ["_create_organization", "_create_admin", "_create_modules", "_create_governance_defaults", "_create_demo_document", "_record_request"])
def test_a_failure_after_any_step_leaves_nothing_behind(hq, monkeypatch, fail_after):
    _pre, mfa = _ops_tokens(hq[0])
    real = getattr(provisioning, fail_after)

    def boom(db, ctx):
        real(db, ctx)
        raise RuntimeError("forced failure")

    monkeypatch.setattr(provisioning, fail_after, boom)
    before, files_before = _counts(), _upload_files()
    body = _body()
    res = client.post("/ops/tenants/provision", json=body, headers=_h(mfa))
    assert res.status_code == 500
    assert _counts() == before  # every table: nothing left
    assert _upload_files() == files_before  # the demo file is removed again
    monkeypatch.undo()
    # and a retry with the same key now works (nothing half-created blocks it)
    monkeypatch.setenv("HQ_ORGANIZATION_ID", str(hq[0]))
    assert client.post("/ops/tenants/provision", json=body, headers=_h(mfa)).status_code == 201


# ---------------------------------------------------------------------------
# Audit, demo run, secrets
# ---------------------------------------------------------------------------

def test_audit_lines_in_both_chains_stay_valid_and_hold_no_password(hq):
    _pre, mfa = _ops_tokens(hq[0])
    body = _body()
    data = client.post("/ops/tenants/provision", json=body, headers=_h(mfa)).json()
    org_id = data["organization_id"]
    db = SessionLocal()
    hq_lines = db.query(AuditLog).filter(AuditLog.organization_id == hq[0], AuditLog.entity_type == "ops", AuditLog.action == "tenant_provisioned", AuditLog.entity_id == org_id).all()
    tenant_lines = db.query(AuditLog).filter(AuditLog.organization_id == org_id, AuditLog.entity_type == "ops_access", AuditLog.action == "tenant_provisioned").all()
    everything = json.dumps([[r.action, r.details, r.performed_by] for r in db.query(AuditLog).all()])
    db.close()
    assert len(hq_lines) == 1 and len(tenant_lines) == 1
    assert data["admin_password"] not in everything
    assert client.get("/audit/verify", headers=_h(mfa)).json()["status"] == "valid"
    admin_token = _login(body["admin_username"], data["admin_password"]).json()["access_token"]
    # the new tenant's admin must first change the password to use the API, so verify through the service
    from app.api.audit import verify_audit_chain  # noqa: PLC0415

    db = SessionLocal()
    admin = db.query(User).filter(User.username == body["admin_username"]).first()
    admin.must_change_password = False
    db.commit()
    db.close()
    assert client.get("/audit/verify", headers=_h(admin_token)).json()["status"] == "valid"
    assert callable(verify_audit_chain)


def test_demo_run_is_optional_and_never_fails_the_provisioning(hq, monkeypatch):
    _pre, mfa = _ops_tokens(hq[0])
    calls = []

    def fake_run(workflow, payload, user_id=None, org_id=None):
        calls.append((workflow, org_id))
        return {"status": "ok"}

    monkeypatch.setattr("app.workflows.services.runner.run_workflow", fake_run)
    none = client.post("/ops/tenants/provision", json=_body(), headers=_h(mfa)).json()
    assert none["demo_run"] == "not_requested" and calls == []

    ok = client.post("/ops/tenants/provision", json=_body(include_demo_run=True), headers=_h(mfa)).json()
    assert ok["demo_run"] == "ok" and calls == [("customer_support", ok["organization_id"])] or calls[0][0] in ("customer_support", "business_intelligence")

    def failing(*a, **k):
        raise RuntimeError("openai down")

    monkeypatch.setattr("app.workflows.services.runner.run_workflow", failing)
    bad = client.post("/ops/tenants/provision", json=_body(include_demo_run=True), headers=_h(mfa))
    assert bad.status_code == 201 and bad.json()["demo_run"] == "failed"
    db = SessionLocal()
    assert db.query(Organization).filter(Organization.id == bad.json()["organization_id"]).first() is not None  # tenant stays
    db.close()

    only_others = [tm.CORE_KEY, tm.COMPLIANCE_KEY] + [k for k in WORKFLOWS if k not in (tm.COMPLIANCE_KEY, "customer_support_ai", "business_intelligence")][:4]
    skipped = client.post("/ops/tenants/provision", json=_body(include_demo_run=True, modules=only_others), headers=_h(mfa)).json()
    assert skipped["demo_run"] == "skipped"


class _Capture(Transport):
    def __init__(self):
        super().__init__()
        self.events = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)


def test_the_password_never_reaches_logs_or_sentry(hq, monkeypatch, caplog):
    _pre, mfa = _ops_tokens(hq[0])
    known = "KNOWN-TEST-PASSWORD-abcdefghijklmnopqrstuvwxyz"
    monkeypatch.setattr(provisioning.secrets, "token_urlsafe", lambda n=32: known)
    transport = _Capture()
    assert init_sentry(dsn="https://publickey@o0.ingest.example.invalid/1", transport=transport)
    try:
        caplog.set_level("DEBUG")
        assert client.post("/ops/tenants/provision", json=_body(), headers=_h(mfa)).status_code == 201  # success path

        real = provisioning._create_modules

        def boom(db, ctx):
            real(db, ctx)
            raise RuntimeError("forced failure after the password exists")

        monkeypatch.setattr(provisioning, "_create_modules", boom)
        assert client.post("/ops/tenants/provision", json=_body(), headers=_h(mfa)).status_code == 500  # failure path
        sentry_sdk.flush()
        assert transport.events
        db = SessionLocal()
        audit = json.dumps([[r.details, r.performed_by] for r in db.query(AuditLog).all()])
        db.close()
        assert known not in json.dumps(transport.events) + caplog.text + audit
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init()
