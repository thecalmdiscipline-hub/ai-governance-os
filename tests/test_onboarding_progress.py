"""Batch L, Deel A: GET /onboarding/progress and PATCH /onboarding/tasks/{id} — customer-facing,
always scoped to the caller's own organization_id, never an id from the request. Isolated test
orgs/users/accounts (not the ambient dennis_admin/customer2_admin demo state)."""
import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.onboarding_project import OnboardingProject
from app.models.onboarding_task import OnboardingTask
from app.models.organization import Organization
from app.models.ops_account import OpsAccount
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)


def _new_org_with_user():
    db = SessionLocal()
    org = Organization(name=f"onb-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    user = User(
        username=f"onb-user-{uuid.uuid4().hex[:8]}",
        password_hash="x",
        role="admin",
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    org_id, user_id, username = org.id, user.id, user.username
    db.close()
    return org_id, user_id, username


def _token(username, org_id):
    return create_access_token({"sub": username, "org_id": org_id, "role": "admin", "mfa": False})


def _make_account_with_project(org_id=None, with_project=True):
    """Creates an OpsAccount (linked to org_id if given) and, if with_project, an active
    OnboardingProject with a representative mix of customer_visible/owner tasks — mirrors a slice
    of STANDARD_V1_TASKS without depending on the seeded template (keeps this test file isolated)."""
    db = SessionLocal()
    account = OpsAccount(name=f"onb-account-{uuid.uuid4().hex[:8]}", status="onboarding", organization_id=org_id)
    db.add(account)
    db.commit()
    account_id = account.id

    project_id = None
    task_ids = {}
    if with_project:
        project = OnboardingProject(account_id=account_id, template_key="standard-v1", template_version="1", status="active", created_by_user_id=1)
        db.add(project)
        db.commit()
        project_id = project.id

        rows = [
            # (phase, position, title, owner, customer_visible, status)
            (1, 1, "Lead vastleggen", "valqeron", False, "done"),
            (2, 2, "Voorstel akkoord", "customer", True, "done"),
            (2, 3, "DPA getekend", "both", True, "todo"),
            (4, 1, "Organisatie aanmaken", "valqeron", False, "done"),
            (6, 2, "Training gegeven", "valqeron", True, "todo"),  # customer_visible but NOT editable by the customer
        ]
        for phase, position, title, owner, customer_visible, status in rows:
            t = OnboardingTask(project_id=project_id, phase=phase, position=position, title=title, owner=owner, customer_visible=customer_visible, status=status)
            db.add(t)
            db.commit()
            task_ids[title] = t.id

    db.close()
    return account_id, project_id, task_ids


def test_no_account_linked_returns_null_project():
    org_id, _, username = _new_org_with_user()
    token = _token(username, org_id)

    res = client.get("/onboarding/progress", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == {"project": None}


def test_account_without_open_project_returns_null_project():
    org_id, _, username = _new_org_with_user()
    token = _token(username, org_id)
    _make_account_with_project(org_id=org_id, with_project=False)

    res = client.get("/onboarding/progress", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == {"project": None}


def test_progress_shows_only_customer_visible_tasks_no_internal_fields():
    org_id, _, username = _new_org_with_user()
    token = _token(username, org_id)
    _, project_id, task_ids = _make_account_with_project(org_id=org_id)

    res = client.get("/onboarding/progress", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()

    assert body["project"]["id"] == project_id
    assert body["project"]["status"] == "active"

    titles = {t["title"] for t in body["tasks"]}
    assert titles == {"Voorstel akkoord", "DPA getekend", "Training gegeven"}  # the 2 non-customer_visible tasks are excluded

    # editable reflects owner, independent of customer_visible
    by_title = {t["title"]: t for t in body["tasks"]}
    assert by_title["Voorstel akkoord"]["editable"] is True  # owner=customer
    assert by_title["DPA getekend"]["editable"] is True  # owner=both
    assert by_title["Training gegeven"]["editable"] is False  # owner=valqeron, visible but read-only

    # Phase 2 has 2 of its (customer-visible) tasks counted, 1 done
    phase_2 = next(p for p in body["phases"] if p["phase"] == 2)
    assert phase_2["total"] == 2
    assert phase_2["done"] == 1
    assert phase_2["title"] == "Proposal, contract & DPA"

    # No internal/account fields of any kind anywhere in the response.
    full_json = str(body)
    for forbidden in ("notes", "primary_contact", "source", "proposed_tier", "TESTACCOUNT", "status_label"):
        assert forbidden not in full_json
    # The account's own status ("onboarding") must never appear — only the project's status.
    # The account's own status ("onboarding", set in _make_account_with_project) must never leak —
    # only the project's status ("active") is returned.
    assert "\"onboarding\"" not in full_json


def test_isolation_organization_b_never_sees_organization_a():
    org_a, _, user_a = _new_org_with_user()
    org_b, _, user_b = _new_org_with_user()
    _make_account_with_project(org_id=org_a)
    token_b = _token(user_b, org_b)

    res = client.get("/onboarding/progress", headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 200
    assert res.json() == {"project": None}


def test_patch_updates_an_editable_customer_visible_task():
    org_id, _, username = _new_org_with_user()
    token = _token(username, org_id)
    _, _, task_ids = _make_account_with_project(org_id=org_id)
    task_id = task_ids["DPA getekend"]

    res = client.patch(f"/onboarding/tasks/{task_id}", json={"status": "done"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == {"id": task_id, "status": "done"}

    db = SessionLocal()
    task = db.query(OnboardingTask).filter(OnboardingTask.id == task_id).first()
    assert task.status == "done"
    assert task.completed_at is not None
    db.close()


def test_patch_rejects_a_task_owned_by_valqeron_even_if_customer_visible():
    org_id, _, username = _new_org_with_user()
    token = _token(username, org_id)
    _, _, task_ids = _make_account_with_project(org_id=org_id)
    task_id = task_ids["Training gegeven"]  # owner=valqeron, customer_visible=True

    res = client.patch(f"/onboarding/tasks/{task_id}", json={"status": "done"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404


def test_patch_rejects_a_non_customer_visible_task():
    org_id, _, username = _new_org_with_user()
    token = _token(username, org_id)
    _, _, task_ids = _make_account_with_project(org_id=org_id)
    task_id = task_ids["Organisatie aanmaken"]  # owner=valqeron, customer_visible=False

    res = client.patch(f"/onboarding/tasks/{task_id}", json={"status": "done"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404


def test_patch_rejects_skipped_and_blocked_and_extra_fields():
    org_id, _, username = _new_org_with_user()
    token = _token(username, org_id)
    _, _, task_ids = _make_account_with_project(org_id=org_id)
    task_id = task_ids["DPA getekend"]

    for body in ({"status": "skipped"}, {"status": "blocked"}, {"status": "done", "note": "hello"}):
        res = client.patch(f"/onboarding/tasks/{task_id}", json=body, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 422, body


def test_patch_on_another_organizations_task_gives_404():
    org_a, _, user_a = _new_org_with_user()
    org_b, _, user_b = _new_org_with_user()
    _, _, task_ids = _make_account_with_project(org_id=org_a)
    task_id = task_ids["DPA getekend"]
    token_b = _token(user_b, org_b)

    res = client.patch(f"/onboarding/tasks/{task_id}", json={"status": "done"}, headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 404

    # The task itself is untouched.
    db = SessionLocal()
    task = db.query(OnboardingTask).filter(OnboardingTask.id == task_id).first()
    assert task.status == "todo"
    db.close()


def test_patch_audit_log_has_no_note_or_account_text(caplog):
    org_id, _, username = _new_org_with_user()
    token = _token(username, org_id)
    _, _, task_ids = _make_account_with_project(org_id=org_id)
    task_id = task_ids["DPA getekend"]

    res = client.patch(f"/onboarding/tasks/{task_id}", json={"status": "done"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

    from app.models.audit_log import AuditLog

    db = SessionLocal()
    row = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id, AuditLog.entity_type == "onboarding_task", AuditLog.entity_id == task_id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert row is not None
    assert row.action == "customer_task_status_changed"
    assert row.details == "todo->done"
    db.close()


def test_audit_chain_stays_valid_after_customer_patch():
    org_id, _, username = _new_org_with_user()
    token = _token(username, org_id)
    _, _, task_ids = _make_account_with_project(org_id=org_id)
    task_id = task_ids["DPA getekend"]
    client.patch(f"/onboarding/tasks/{task_id}", json={"status": "done"}, headers={"Authorization": f"Bearer {token}"})

    res = client.get("/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "valid"
