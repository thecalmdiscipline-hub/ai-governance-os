"""Batch L, Deel B (2026-10-07): the new customer-facing, read-only governance list endpoints
(GET /ai-policy, /ai-systems, /ai-risks, /ai-incidents, /corrective-actions, /evidence) and the
new audit log on PUT /corrective-actions/{id}/status.

Fase 0 found these GET lists did not exist at all before this batch (not just incidents/evidence,
as the hand-off assumed) — and that app/api/governance.py's POST/PUT endpoints had zero API-level
test coverage anywhere in the repo. This file is scoped to the new GET endpoints and the new audit
log on the status endpoint; it does not retroactively add coverage for the pre-existing POST paths.

Isolated test orgs/users (not the ambient dennis_admin/customer2_admin demo state), same pattern as
tests/test_onboarding_progress.py.
"""
import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.ai_incident import AIIncident
from app.models.ai_policy import AIPolicy
from app.models.ai_risk import AIRisk
from app.models.ai_system import AISystem
from app.models.audit_log import AuditLog
from app.models.corrective_action import CorrectiveAction
from app.models.evidence import Evidence
from app.models.organization import Organization
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)


def _new_org_with_user():
    db = SessionLocal()
    org = Organization(name=f"gov-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    user = User(
        username=f"gov-user-{uuid.uuid4().hex[:8]}",
        password_hash="x",
        role="admin",
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    org_id, username = org.id, user.username
    db.close()
    return org_id, username


def _token(username, org_id):
    return create_access_token({"sub": username, "org_id": org_id, "role": "admin", "mfa": False})


def _make_full_governance_set(org_id):
    """One of everything for org_id, plus one soft-deleted system/risk/incident to prove exclusion."""
    db = SessionLocal()

    policy = AIPolicy(
        purpose="p", principles="pr", risk_commitment="rc", monitoring_commitment="mc", organization_id=org_id
    )
    db.add(policy)

    system = AISystem(name="Customer Support AI", organization_id=org_id)
    db.add(system)
    db.commit()

    deleted_system = AISystem(name="Retired system", organization_id=org_id, is_deleted=True)
    db.add(deleted_system)
    db.commit()

    risk = AIRisk(title="Support replies may be wrong", risk_level="medium", ai_system_id=system.id)
    db.add(risk)
    db.commit()

    deleted_risk = AIRisk(title="Old risk", risk_level="low", ai_system_id=system.id, is_deleted=True)
    db.add(deleted_risk)
    db.commit()

    incident = AIIncident(title="A wrong reply reached a customer", severity="medium", ai_system_id=system.id)
    db.add(incident)

    deleted_incident = AIIncident(title="Old incident", severity="low", ai_system_id=system.id, is_deleted=True)
    db.add(deleted_incident)

    action = CorrectiveAction(title="Review before sending", description="desc", status="open", ai_risk_id=risk.id)
    db.add(action)

    evidence_via_system = Evidence(title="Screenshot of the review step", ai_system_id=system.id)
    evidence_via_risk = Evidence(title="Risk sign-off note", ai_risk_id=risk.id)
    db.add(evidence_via_system)
    db.add(evidence_via_risk)
    db.commit()

    ids = {
        "policy_id": policy.id,
        "system_id": system.id,
        "deleted_system_id": deleted_system.id,
        "risk_id": risk.id,
        "deleted_risk_id": deleted_risk.id,
        "incident_id": incident.id,
        "action_id": action.id,
    }
    db.close()
    return ids


def test_ai_policy_list_scoped_to_own_org():
    org_a, user_a = _new_org_with_user()
    org_b, user_b = _new_org_with_user()
    ids = _make_full_governance_set(org_a)

    res_a = client.get("/ai-policy", headers={"Authorization": f"Bearer {_token(user_a, org_a)}"})
    assert res_a.status_code == 200
    assert [p["id"] for p in res_a.json()] == [ids["policy_id"]]

    res_b = client.get("/ai-policy", headers={"Authorization": f"Bearer {_token(user_b, org_b)}"})
    assert res_b.status_code == 200
    assert res_b.json() == []


def test_ai_systems_list_excludes_deleted_and_other_orgs():
    org_a, user_a = _new_org_with_user()
    org_b, user_b = _new_org_with_user()
    ids = _make_full_governance_set(org_a)

    res_a = client.get("/ai-systems", headers={"Authorization": f"Bearer {_token(user_a, org_a)}"})
    assert res_a.status_code == 200
    returned_ids = [s["id"] for s in res_a.json()]
    assert returned_ids == [ids["system_id"]]  # the soft-deleted one is excluded

    res_b = client.get("/ai-systems", headers={"Authorization": f"Bearer {_token(user_b, org_b)}"})
    assert res_b.json() == []


def test_ai_risks_list_excludes_deleted_and_other_orgs():
    org_a, user_a = _new_org_with_user()
    org_b, user_b = _new_org_with_user()
    ids = _make_full_governance_set(org_a)

    res_a = client.get("/ai-risks", headers={"Authorization": f"Bearer {_token(user_a, org_a)}"})
    assert [r["id"] for r in res_a.json()] == [ids["risk_id"]]

    res_b = client.get("/ai-risks", headers={"Authorization": f"Bearer {_token(user_b, org_b)}"})
    assert res_b.json() == []


def test_ai_incidents_list_excludes_deleted_and_other_orgs():
    org_a, user_a = _new_org_with_user()
    org_b, user_b = _new_org_with_user()
    ids = _make_full_governance_set(org_a)

    res_a = client.get("/ai-incidents", headers={"Authorization": f"Bearer {_token(user_a, org_a)}"})
    assert res_a.status_code == 200
    body = res_a.json()
    assert [i["id"] for i in body] == [ids["incident_id"]]
    assert body[0]["status"] == "open"

    res_b = client.get("/ai-incidents", headers={"Authorization": f"Bearer {_token(user_b, org_b)}"})
    assert res_b.json() == []


def test_corrective_actions_list_scoped_to_own_org():
    org_a, user_a = _new_org_with_user()
    org_b, user_b = _new_org_with_user()
    ids = _make_full_governance_set(org_a)

    res_a = client.get("/corrective-actions", headers={"Authorization": f"Bearer {_token(user_a, org_a)}"})
    assert [a["id"] for a in res_a.json()] == [ids["action_id"]]

    res_b = client.get("/corrective-actions", headers={"Authorization": f"Bearer {_token(user_b, org_b)}"})
    assert res_b.json() == []


def test_evidence_list_matches_via_either_system_or_risk_and_is_org_scoped():
    org_a, user_a = _new_org_with_user()
    org_b, user_b = _new_org_with_user()
    _make_full_governance_set(org_a)

    res_a = client.get("/evidence", headers={"Authorization": f"Bearer {_token(user_a, org_a)}"})
    assert res_a.status_code == 200
    titles = {e["title"] for e in res_a.json()}
    assert titles == {"Screenshot of the review step", "Risk sign-off note"}

    res_b = client.get("/evidence", headers={"Authorization": f"Bearer {_token(user_b, org_b)}"})
    assert res_b.json() == []


def test_corrective_action_status_update_still_400_on_invalid_status():
    org_a, user_a = _new_org_with_user()
    ids = _make_full_governance_set(org_a)
    token = _token(user_a, org_a)

    res = client.put(
        f"/corrective-actions/{ids['action_id']}/status",
        json={"new_status": "not-a-real-status", "reason": "testing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400  # unchanged, as instructed — not tightened to 422


def test_corrective_action_status_update_writes_audit_log_without_reason_text():
    org_a, user_a = _new_org_with_user()
    ids = _make_full_governance_set(org_a)
    token = _token(user_a, org_a)

    res = client.put(
        f"/corrective-actions/{ids['action_id']}/status",
        json={"new_status": "in_progress", "reason": "a sensitive internal justification nobody else should see"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == {"action_id": ids["action_id"], "new_status": "in_progress"}

    db = SessionLocal()
    row = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == org_a,
            AuditLog.entity_type == "corrective_action",
            AuditLog.entity_id == ids["action_id"],
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert row is not None
    assert row.action == "corrective_action_status_changed"
    assert row.details == "open->in_progress"
    assert "sensitive internal justification" not in (row.details or "")
    db.close()


def test_corrective_action_status_update_on_another_orgs_action_gives_404():
    org_a, _ = _new_org_with_user()
    org_b, user_b = _new_org_with_user()
    ids = _make_full_governance_set(org_a)
    token_b = _token(user_b, org_b)

    res = client.put(
        f"/corrective-actions/{ids['action_id']}/status",
        json={"new_status": "in_progress", "reason": "x"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 404


def test_audit_chain_stays_valid_after_corrective_action_status_change():
    org_a, user_a = _new_org_with_user()
    ids = _make_full_governance_set(org_a)
    token = _token(user_a, org_a)

    client.put(
        f"/corrective-actions/{ids['action_id']}/status",
        json={"new_status": "closed", "reason": "resolved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    res = client.get("/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "valid"
