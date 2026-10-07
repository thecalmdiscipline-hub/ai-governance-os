"""Batch O2 (2026-10-07): POST /corrective-actions (owner, due_date, ai_risk_id and/or
ai_incident_id) and the existing PUT .../status, after the additive migration (owner, due_date,
ai_incident_id on CorrectiveAction).

A corrective action now links to a risk and/or an incident. Isolation (get_org_scoped_action,
list_corrective_actions) must therefore match via either link, not an inner join through AIRisk
alone — otherwise an incident-only action would be invisible/unreachable in its own organization.
Isolated test orgs/users (not the ambient demo state), same pattern as test_ai_incidents.py."""
import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.ai_incident import AIIncident
from app.models.ai_risk import AIRisk
from app.models.ai_system import AISystem
from app.models.audit_log import AuditLog
from app.models.corrective_action import CorrectiveAction
from app.models.organization import Organization
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)


def _new_org_with_user_risk_and_incident():
    db = SessionLocal()
    org = Organization(name=f"ca-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    user = User(
        username=f"ca-user-{uuid.uuid4().hex[:8]}",
        password_hash="x",
        role="admin",
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    system = AISystem(name=f"System {uuid.uuid4().hex[:6]}", organization_id=org.id)
    db.add(system)
    db.commit()
    risk = AIRisk(title="x", risk_level="medium", ai_system_id=system.id)
    incident = AIIncident(title="x", severity="low", ai_system_id=system.id)
    db.add(risk)
    db.add(incident)
    db.commit()
    org_id, username, risk_id, incident_id = org.id, user.username, risk.id, incident.id
    db.close()
    return org_id, username, risk_id, incident_id


def _token(username, org_id):
    return create_access_token({"sub": username, "org_id": org_id, "role": "admin", "mfa": False})


def test_create_with_risk_only_success():
    org_id, username, risk_id, _ = _new_org_with_user_risk_and_incident()
    token = _token(username, org_id)

    res = client.post(
        "/corrective-actions",
        json={"title": "Review before sending", "description": "desc", "ai_risk_id": risk_id, "owner": "Compliance team", "due_date": "2026-11-01"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "open"
    assert body["ai_risk_id"] == risk_id
    assert body["ai_incident_id"] is None
    assert body["owner"] == "Compliance team"
    assert body["due_date"] == "2026-11-01"


def test_create_with_incident_only_success():
    org_id, username, _, incident_id = _new_org_with_user_risk_and_incident()
    token = _token(username, org_id)

    res = client.post(
        "/corrective-actions",
        json={"title": "Follow up", "description": "desc", "ai_incident_id": incident_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ai_incident_id"] == incident_id
    assert body["ai_risk_id"] is None
    assert body["owner"] is None
    assert body["due_date"] is None


def test_create_with_both_risk_and_incident_success():
    org_id, username, risk_id, incident_id = _new_org_with_user_risk_and_incident()
    token = _token(username, org_id)

    res = client.post(
        "/corrective-actions",
        json={"title": "x", "description": "desc", "ai_risk_id": risk_id, "ai_incident_id": incident_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ai_risk_id"] == risk_id
    assert body["ai_incident_id"] == incident_id


def test_create_rejects_neither_risk_nor_incident():
    org_id, username, _, _ = _new_org_with_user_risk_and_incident()
    token = _token(username, org_id)

    res = client.post(
        "/corrective-actions",
        json={"title": "x", "description": "desc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


def test_create_rejects_extra_fields():
    org_id, username, risk_id, _ = _new_org_with_user_risk_and_incident()
    token = _token(username, org_id)

    res = client.post(
        "/corrective-actions",
        json={"title": "x", "description": "desc", "ai_risk_id": risk_id, "status": "closed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


def test_create_with_unknown_risk_id_gives_404_and_creates_nothing():
    org_id, username, risk_id, _ = _new_org_with_user_risk_and_incident()
    token = _token(username, org_id)
    bogus_risk_id = risk_id + 999999

    res = client.post(
        "/corrective-actions",
        json={"title": "x", "description": "desc", "ai_risk_id": bogus_risk_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404

    db = SessionLocal()
    count = db.query(CorrectiveAction).filter(CorrectiveAction.ai_risk_id == bogus_risk_id).count()
    db.close()
    assert count == 0


def test_create_with_another_orgs_risk_gives_404_and_creates_nothing():
    org_a, _, risk_a, _ = _new_org_with_user_risk_and_incident()
    org_b, user_b, _, _ = _new_org_with_user_risk_and_incident()
    token_b = _token(user_b, org_b)

    res = client.post(
        "/corrective-actions",
        json={"title": "x", "description": "desc", "ai_risk_id": risk_a},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 404

    db = SessionLocal()
    count = db.query(CorrectiveAction).filter(CorrectiveAction.ai_risk_id == risk_a).count()
    db.close()
    assert count == 0


def test_create_with_another_orgs_incident_gives_404_and_creates_nothing():
    org_a, _, _, incident_a = _new_org_with_user_risk_and_incident()
    org_b, user_b, _, _ = _new_org_with_user_risk_and_incident()
    token_b = _token(user_b, org_b)

    res = client.post(
        "/corrective-actions",
        json={"title": "x", "description": "desc", "ai_incident_id": incident_a},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 404

    db = SessionLocal()
    count = db.query(CorrectiveAction).filter(CorrectiveAction.ai_incident_id == incident_a).count()
    db.close()
    assert count == 0


def test_create_writes_an_audit_log_without_title_or_description_text():
    org_id, username, risk_id, _ = _new_org_with_user_risk_and_incident()
    token = _token(username, org_id)

    res = client.post(
        "/corrective-actions",
        json={"title": "a confidential title nobody else should see", "description": "a confidential description", "ai_risk_id": risk_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    action_id = res.json()["id"]

    db = SessionLocal()
    row = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id, AuditLog.entity_type == "corrective_action", AuditLog.entity_id == action_id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert row is not None
    assert row.action == "corrective_action_created"
    assert "confidential" not in (row.details or "")
    db.close()


def test_list_finds_an_incident_only_action_scoped_to_own_org():
    org_a, user_a, _, incident_a = _new_org_with_user_risk_and_incident()
    org_b, user_b, _, _ = _new_org_with_user_risk_and_incident()
    token_a = _token(user_a, org_a)
    token_b = _token(user_b, org_b)

    create_res = client.post(
        "/corrective-actions",
        json={"title": "x", "description": "desc", "ai_incident_id": incident_a},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    action_id = create_res.json()["id"]

    res_a = client.get("/corrective-actions", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    assert [a["id"] for a in res_a.json()] == [action_id]

    res_b = client.get("/corrective-actions", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.json() == []


def test_list_filter_by_ai_incident_id():
    org_id, username, risk_id, incident_id = _new_org_with_user_risk_and_incident()
    token = _token(username, org_id)

    client.post("/corrective-actions", json={"title": "risk-linked", "description": "d", "ai_risk_id": risk_id}, headers={"Authorization": f"Bearer {token}"})
    incident_res = client.post("/corrective-actions", json={"title": "incident-linked", "description": "d", "ai_incident_id": incident_id}, headers={"Authorization": f"Bearer {token}"})

    res = client.get(f"/corrective-actions?ai_incident_id={incident_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert [a["id"] for a in res.json()] == [incident_res.json()["id"]]


def test_status_update_still_works_for_an_incident_only_action():
    org_id, username, _, incident_id = _new_org_with_user_risk_and_incident()
    token = _token(username, org_id)

    create_res = client.post(
        "/corrective-actions",
        json={"title": "x", "description": "desc", "ai_incident_id": incident_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    action_id = create_res.json()["id"]

    res = client.put(
        f"/corrective-actions/{action_id}/status",
        json={"new_status": "closed", "reason": "resolved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == {"action_id": action_id, "new_status": "closed"}


def test_status_update_on_incident_only_action_from_another_org_gives_404():
    org_a, user_a, _, incident_a = _new_org_with_user_risk_and_incident()
    org_b, user_b, _, _ = _new_org_with_user_risk_and_incident()
    token_a = _token(user_a, org_a)
    token_b = _token(user_b, org_b)

    create_res = client.post(
        "/corrective-actions",
        json={"title": "x", "description": "desc", "ai_incident_id": incident_a},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    action_id = create_res.json()["id"]

    res = client.put(
        f"/corrective-actions/{action_id}/status",
        json={"new_status": "closed", "reason": "x"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 404


def test_audit_chain_stays_valid_after_create_and_status_change():
    org_id, username, risk_id, _ = _new_org_with_user_risk_and_incident()
    token = _token(username, org_id)

    create_res = client.post(
        "/corrective-actions",
        json={"title": "x", "description": "desc", "ai_risk_id": risk_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    action_id = create_res.json()["id"]
    client.put(f"/corrective-actions/{action_id}/status", json={"new_status": "closed", "reason": "x"}, headers={"Authorization": f"Bearer {token}"})

    res = client.get("/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "valid"


def test_existing_row_without_the_new_columns_stays_readable_with_null():
    """Simulates a pre-migration row: owner/due_date/ai_incident_id never set (NULL)."""
    org_id, username, risk_id, _ = _new_org_with_user_risk_and_incident()
    token = _token(username, org_id)

    db = SessionLocal()
    action = CorrectiveAction(title="pre-existing", description="d", status="open", ai_risk_id=risk_id)
    db.add(action)
    db.commit()
    action_id = action.id
    db.close()

    res = client.get("/corrective-actions", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    row = [a for a in res.json() if a["id"] == action_id][0]
    assert row["owner"] is None
    assert row["due_date"] is None
    assert row["ai_incident_id"] is None
