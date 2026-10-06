"""Batch I, Fase 2.2: /ops/onboarding (templates, projects, tasks, metrics, audit, no contact/note
content in audit details). Mirrors the hq/_ops_tokens fixture pattern used across the ops tests."""
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
from app.models.onboarding_project import OnboardingProject
from app.models.onboarding_task import OnboardingTask
from app.models.onboarding_template import OnboardingTemplate
from app.models.onboarding_template_task import OnboardingTemplateTask
from app.models.organization import Organization
from app.models.ops_account import OpsAccount
from app.models.user import User
from app.services.onboarding import STANDARD_V1_TASKS, seed_standard_v1

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
    return _new_org("ob-hq")


@pytest.fixture(autouse=True)
def _env(monkeypatch, hq):
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("HQ_ORGANIZATION_ID", str(hq))
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))


@pytest.fixture(scope="module", autouse=True)
def _ensure_template():
    db = SessionLocal()
    try:
        seed_standard_v1(db)
    finally:
        db.close()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _user(org_id, super_admin=False):
    db = SessionLocal()
    name = f"ob_{uuid.uuid4().hex[:10]}"
    db.add(User(username=name, password_hash=hash_password(PASSWORD), role="admin", organization_id=org_id,
                is_active=True, is_super_admin=super_admin))
    db.commit()
    db.close()
    return name


def _plain_token(name):
    return client.post("/login", data={"username": name, "password": PASSWORD}).json()["access_token"]


def _ops_tokens(hq_id):
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


def _start_project(mfa, account_id):
    return client.post(f"/ops/accounts/{account_id}/onboarding", headers=_h(mfa))


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def test_all_onboarding_endpoints_need_ops_access(hq):
    ordinary = _plain_token(_user(hq))
    pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    project = _start_project(mfa, account_id).json()
    task_id = project["tasks"][0]["id"]

    calls = [
        ("get", "/ops/onboarding/templates", None),
        ("post", f"/ops/accounts/{account_id}/onboarding", None),
        ("get", "/ops/onboarding/projects", None),
        ("get", f"/ops/onboarding/projects/{project['id']}", None),
        ("patch", f"/ops/onboarding/projects/{project['id']}", {"status": "paused"}),
        ("get", f"/ops/onboarding/projects/{project['id']}/metrics", None),
        ("patch", f"/ops/onboarding/tasks/{task_id}", {"status": "doing"}),
    ]
    for method, path, body in calls:
        kwargs = {"json": body} if body is not None else {}
        assert getattr(client, method)(path, **kwargs).status_code == 401
        assert getattr(client, method)(path, headers=_h(ordinary), **kwargs).status_code == 403
        assert getattr(client, method)(path, headers=_h(pre), **kwargs).status_code == 403


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def test_list_templates_includes_standard_v1(hq):
    _pre, mfa = _ops_tokens(hq)
    res = client.get("/ops/onboarding/templates", headers=_h(mfa))
    assert res.status_code == 200
    keys = [t["key"] for t in res.json()["templates"]]
    assert "standard-v1" in keys


# ---------------------------------------------------------------------------
# Project creation: copies tasks, template-independence, one-active-project rule
# ---------------------------------------------------------------------------

def test_starting_a_project_copies_all_template_tasks(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()

    res = _start_project(mfa, account_id)
    assert res.status_code == 201
    body = res.json()
    assert body["template_key"] == "standard-v1"
    assert body["status"] == "active"
    assert len(body["tasks"]) == len(STANDARD_V1_TASKS)
    assert all(t["status"] == "todo" for t in body["tasks"])
    phases = sorted({t["phase"] for t in body["tasks"]})
    assert phases == list(range(1, 9))


def test_second_project_for_same_account_is_rejected(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    first = _start_project(mfa, account_id)
    assert first.status_code == 201
    second = _start_project(mfa, account_id)
    assert second.status_code == 409 and second.json()["error"] == "project_already_active"


def test_project_tasks_are_independent_of_later_template_edits(hq):
    # Deliberately does NOT touch the shared, global "standard-v1" template (mutating it would
    # permanently corrupt it for every other test/run against a persistent local test.db — the
    # HTTP endpoint only ever starts a project from "standard-v1", so this builds its own,
    # throwaway template and calls the service function directly instead).
    from app.services.onboarding import create_project_from_template

    db = SessionLocal()
    try:
        throwaway_key = f"throwaway-{uuid.uuid4().hex[:10]}"
        template = OnboardingTemplate(key=throwaway_key, name="Throwaway", version="1", is_active=True)
        db.add(template)
        db.flush()
        task = OnboardingTemplateTask(template_id=template.id, phase=1, position=1, title="Original title", owner="valqeron", customer_visible=False)
        db.add(task)
        db.commit()

        account = _account(db)
        user = db.query(User).filter(User.organization_id == hq).first()
        project = create_project_from_template(db, account_id=account.id, created_by_user_id=user.id, template_key=throwaway_key)
        project_id = project.id

        # Mutate the template's own task directly (simulates a later template edit) — safe here,
        # it's the throwaway template created above, not the shared standard-v1 one.
        task.title = "EDITED AFTER PROJECT STARTED"
        db.commit()
    finally:
        db.close()

    _pre, mfa = _ops_tokens(hq)
    refetched = client.get(f"/ops/onboarding/projects/{project_id}", headers=_h(mfa)).json()
    assert refetched["tasks"][0]["title"] == "Original title"
    assert refetched["tasks"][0]["title"] != "EDITED AFTER PROJECT STARTED"


def test_starting_onboarding_for_unknown_account_404(hq):
    _pre, mfa = _ops_tokens(hq)
    res = client.post("/ops/accounts/99999999/onboarding", headers=_h(mfa))
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Task status / timestamps
# ---------------------------------------------------------------------------

def test_task_status_sets_and_clears_timestamps(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    project = _start_project(mfa, account_id).json()
    task_id = project["tasks"][0]["id"]

    doing = client.patch(f"/ops/onboarding/tasks/{task_id}", json={"status": "doing"}, headers=_h(mfa)).json()
    assert doing["started_at"] is not None
    assert doing["completed_at"] is None

    done = client.patch(f"/ops/onboarding/tasks/{task_id}", json={"status": "done"}, headers=_h(mfa)).json()
    assert done["completed_at"] is not None
    assert done["completed_by_user_id"] is not None

    back_to_todo = client.patch(f"/ops/onboarding/tasks/{task_id}", json={"status": "todo"}, headers=_h(mfa)).json()
    assert back_to_todo["completed_at"] is None
    assert back_to_todo["completed_by_user_id"] is None
    # started_at is a historical fact about this task and is NOT cleared by a done->todo reversal.
    assert back_to_todo["started_at"] is not None


def test_task_status_doing_only_sets_started_at_once(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    project = _start_project(mfa, account_id).json()
    task_id = project["tasks"][0]["id"]

    first = client.patch(f"/ops/onboarding/tasks/{task_id}", json={"status": "doing"}, headers=_h(mfa)).json()
    first_started = first["started_at"]
    client.patch(f"/ops/onboarding/tasks/{task_id}", json={"status": "blocked"}, headers=_h(mfa))
    second = client.patch(f"/ops/onboarding/tasks/{task_id}", json={"status": "doing"}, headers=_h(mfa)).json()
    assert second["started_at"] == first_started  # unchanged on the second time through "doing"


def test_task_status_rejects_unknown_value(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    project = _start_project(mfa, account_id).json()
    task_id = project["tasks"][0]["id"]
    res = client.patch(f"/ops/onboarding/tasks/{task_id}", json={"status": "on_hold"}, headers=_h(mfa))
    assert res.status_code == 422


def test_task_note_can_be_set_without_status_change(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    project = _start_project(mfa, account_id).json()
    task_id = project["tasks"][0]["id"]
    res = client.patch(f"/ops/onboarding/tasks/{task_id}", json={"note": "waiting on customer"}, headers=_h(mfa))
    assert res.status_code == 200
    assert res.json()["note"] == "waiting on customer"
    assert res.json()["status"] == "todo"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _set_task_status_at(task_id, status, actor_token):
    return client.patch(f"/ops/onboarding/tasks/{task_id}", json={"status": status}, headers=_h(actor_token))


def test_metrics_empty_project_has_no_phase_data(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    project = _start_project(mfa, account_id).json()

    res = client.get(f"/ops/onboarding/projects/{project['id']}/metrics", headers=_h(mfa))
    assert res.status_code == 200
    body = res.json()
    for phase in map(str, range(1, 9)):
        assert body["phases"][phase]["started_at"] is None
        assert body["phases"][phase]["completed_at"] is None
        assert body["phases"][phase]["duration_days"] is None
    assert body["kickoff_to_golive_days"] is None
    assert body["total_days"] is None


def test_metrics_partially_complete_phase_has_started_but_not_completed(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    project = _start_project(mfa, account_id).json()
    phase1_tasks = [t for t in project["tasks"] if t["phase"] == 1]
    assert len(phase1_tasks) == 3

    client.patch(f"/ops/onboarding/tasks/{phase1_tasks[0]['id']}", json={"status": "done"}, headers=_h(mfa))

    res = client.get(f"/ops/onboarding/projects/{project['id']}/metrics", headers=_h(mfa)).json()
    assert res["phases"]["1"]["started_at"] is not None
    assert res["phases"]["1"]["completed_at"] is None  # phase 1 has 3 tasks, only 1 done


def test_metrics_fully_complete_phase_has_duration(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    project = _start_project(mfa, account_id).json()
    phase1_tasks = [t for t in project["tasks"] if t["phase"] == 1]

    for t in phase1_tasks:
        client.patch(f"/ops/onboarding/tasks/{t['id']}", json={"status": "done"}, headers=_h(mfa))

    res = client.get(f"/ops/onboarding/projects/{project['id']}/metrics", headers=_h(mfa)).json()
    assert res["phases"]["1"]["started_at"] is not None
    assert res["phases"]["1"]["completed_at"] is not None
    assert res["phases"]["1"]["duration_days"] is not None
    assert res["phases"]["1"]["duration_days"] >= 0


def test_metrics_kickoff_to_golive_with_known_timestamps(hq):
    """Directly manipulates timestamps (bypassing the API's "now") to get a deterministic,
    non-zero kickoff-to-golive duration: complete phase 3's first task at T, then every phase-7
    task at T+5 days, and check the metric reports exactly 5 days."""
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    project = _start_project(mfa, account_id).json()

    kickoff_task_id = next(t["id"] for t in project["tasks"] if t["phase"] == 3 and t["position"] == 1)
    phase7_ids = [t["id"] for t in project["tasks"] if t["phase"] == 7]

    client.patch(f"/ops/onboarding/tasks/{kickoff_task_id}", json={"status": "done"}, headers=_h(mfa))
    for tid in phase7_ids:
        client.patch(f"/ops/onboarding/tasks/{tid}", json={"status": "done"}, headers=_h(mfa))

    # Force exact, known timestamps directly in the database so the duration is deterministic.
    db = SessionLocal()
    t0 = datetime(2026, 1, 1, 9, 0, 0)
    db.query(OnboardingTask).filter(OnboardingTask.id == kickoff_task_id).update({"completed_at": t0})
    db.query(OnboardingTask).filter(OnboardingTask.id.in_(phase7_ids)).update(
        {"completed_at": t0 + timedelta(days=5)}, synchronize_session=False
    )
    db.commit()
    db.close()

    res = client.get(f"/ops/onboarding/projects/{project['id']}/metrics", headers=_h(mfa)).json()
    assert res["kickoff_to_golive_days"] == 5


def test_metrics_total_days_needs_phase_8_fully_done(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    project = _start_project(mfa, account_id).json()
    phase8_ids = [t["id"] for t in project["tasks"] if t["phase"] == 8]

    res_before = client.get(f"/ops/onboarding/projects/{project['id']}/metrics", headers=_h(mfa)).json()
    assert res_before["total_days"] is None

    for tid in phase8_ids:
        client.patch(f"/ops/onboarding/tasks/{tid}", json={"status": "done"}, headers=_h(mfa))

    res_after = client.get(f"/ops/onboarding/projects/{project['id']}/metrics", headers=_h(mfa)).json()
    assert res_after["total_days"] is not None
    assert res_after["total_days"] >= 0


def test_metrics_unknown_project_404(hq):
    _pre, mfa = _ops_tokens(hq)
    res = client.get("/ops/onboarding/projects/99999999/metrics", headers=_h(mfa))
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Audit (dual chain) + no contact/note content leaked
# ---------------------------------------------------------------------------

def test_onboarding_start_and_task_update_write_dual_audit(hq):
    _pre, mfa = _ops_tokens(hq)
    target_org = _new_org("ob-audit-target")
    db = SessionLocal()
    account = _account(db, organization_id=target_org)
    account_id = account.id
    db.close()

    before_hq = len(_audit_rows(hq))
    before_target = len(_audit_rows(target_org))

    project = _start_project(mfa, account_id).json()
    # Brand-new target_org: first audit row also triggers the one-time chain-v2 marker row (+2).
    assert len(_audit_rows(hq)) == before_hq + 1
    assert len(_audit_rows(target_org)) == before_target + 2

    client.patch(f"/ops/onboarding/tasks/{project['tasks'][0]['id']}", json={"status": "doing", "note": "secret note"}, headers=_h(mfa))
    assert len(_audit_rows(hq)) == before_hq + 2
    assert len(_audit_rows(target_org)) == before_target + 3

    hq_verify = client.get("/audit/verify", headers=_h(mfa))
    assert hq_verify.json()["status"] == "valid"
    target_verify = client.get("/audit/verify", headers=_h(_plain_token(_user(target_org))))
    assert target_verify.json()["status"] == "valid"


def test_no_note_text_in_audit_details(hq):
    _pre, mfa = _ops_tokens(hq)
    db = SessionLocal()
    account_id = _account(db).id
    db.close()
    project = _start_project(mfa, account_id).json()
    task_id = project["tasks"][0]["id"]

    secret_note = "Client mentioned they are also evaluating a competitor, keep confidential"
    client.patch(f"/ops/onboarding/tasks/{task_id}", json={"status": "doing", "note": secret_note}, headers=_h(mfa))

    rows = _audit_rows(hq)
    joined = "\n".join(r.details or "" for r in rows)
    assert secret_note not in joined


# ---------------------------------------------------------------------------
# Seed script idempotency
# ---------------------------------------------------------------------------

def test_seed_standard_v1_is_idempotent():
    db = SessionLocal()
    try:
        template = db.query(OnboardingTemplate).filter(OnboardingTemplate.key == "standard-v1").first()
        assert template is not None
        task_count_before = db.query(OnboardingTemplateTask).filter(OnboardingTemplateTask.template_id == template.id).count()
        assert task_count_before == len(STANDARD_V1_TASKS)

        result = seed_standard_v1(db)  # second run: must insert nothing
        assert result["created"] is False

        task_count_after = db.query(OnboardingTemplateTask).filter(OnboardingTemplateTask.template_id == template.id).count()
        assert task_count_after == task_count_before
    finally:
        db.close()


def test_seed_standard_v1_dry_run_writes_nothing_on_a_fresh_db(monkeypatch):
    # Use a throwaway key so this test doesn't depend on whether 'standard-v1' already exists.
    import app.services.onboarding as onboarding_module

    monkeypatch.setattr(onboarding_module, "STANDARD_V1_KEY", f"dry-run-test-{uuid.uuid4().hex[:8]}")
    db = SessionLocal()
    try:
        result = onboarding_module.seed_standard_v1(db, dry_run=True)
        assert result["created"] is True
        assert result["tasks_inserted"] == len(STANDARD_V1_TASKS)
        found = db.query(OnboardingTemplate).filter(OnboardingTemplate.key == onboarding_module.STANDARD_V1_KEY).first()
        assert found is None  # dry run: nothing was actually written
    finally:
        db.close()
