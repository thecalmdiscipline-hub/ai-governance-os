"""Batch O1 (2026-10-07): POST /ai-incidents and PATCH /ai-incidents/{id}.

ai_system_id stays required on create (not "optional" as the hand-off's prose suggested) —
AIIncident has no organization_id column of its own, so the linked AISystem is the only way an
incident is ever scoped to a tenant. Isolated test orgs/users (not the ambient demo state)."""
import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.ai_incident import AIIncident
from app.models.ai_system import AISystem
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)


def _new_org_with_user_and_system():
    db = SessionLocal()
    org = Organization(name=f"incident-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    user = User(
        username=f"incident-user-{uuid.uuid4().hex[:8]}",
        password_hash="x",
        role="admin",
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    system = AISystem(name=f"System {uuid.uuid4().hex[:6]}", organization_id=org.id)
    db.add(system)
    db.commit()
    org_id, username, system_id = org.id, user.username, system.id
    db.close()
    return org_id, username, system_id


def _token(username, org_id):
    return create_access_token({"sub": username, "org_id": org_id, "role": "admin", "mfa": False})


def test_create_incident_success():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)

    res = client.post(
        "/ai-incidents",
        json={"title": "A wrong reply reached a customer", "description": "desc", "severity": "medium", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "A wrong reply reached a customer"
    assert body["severity"] == "medium"
    assert body["status"] == "open"
    assert body["ai_system_id"] == system_id


def test_create_incident_rejects_invalid_severity_and_extra_fields():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)

    for body in (
        {"title": "x", "severity": "catastrophic", "ai_system_id": system_id},
        {"title": "x", "severity": "medium", "ai_system_id": system_id, "extra": "nope"},
        {"severity": "medium", "ai_system_id": system_id},  # missing title
    ):
        res = client.post("/ai-incidents", json=body, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 422, body


def test_create_incident_with_another_orgs_system_gives_404_and_creates_nothing():
    org_a, _, system_a = _new_org_with_user_and_system()
    org_b, user_b, _ = _new_org_with_user_and_system()
    token_b = _token(user_b, org_b)

    res = client.post(
        "/ai-incidents",
        json={"title": "x", "severity": "low", "ai_system_id": system_a},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 404

    db = SessionLocal()
    count = db.query(AIIncident).filter(AIIncident.ai_system_id == system_a).count()
    db.close()
    assert count == 0


def test_update_incident_status_success_with_old_new_in_audit():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)

    create_res = client.post(
        "/ai-incidents",
        json={"title": "x", "severity": "low", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    incident_id = create_res.json()["id"]

    res = client.patch(f"/ai-incidents/{incident_id}", json={"status": "closed"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "closed"

    db = SessionLocal()
    row = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id, AuditLog.entity_type == "ai_incident", AuditLog.entity_id == incident_id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert row is not None
    assert row.action == "incident_updated"
    assert row.details == "status:open->closed"
    db.close()


def test_update_incident_rejects_invalid_status_and_extra_fields():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    create_res = client.post(
        "/ai-incidents",
        json={"title": "x", "severity": "low", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    incident_id = create_res.json()["id"]

    for body in ({"status": "resolved"}, {"status": "closed", "note": "hello"}):
        res = client.patch(f"/ai-incidents/{incident_id}", json=body, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 422, body


def test_update_on_another_organizations_incident_gives_404():
    org_a, user_a, system_a = _new_org_with_user_and_system()
    org_b, user_b, _ = _new_org_with_user_and_system()
    token_a = _token(user_a, org_a)
    token_b = _token(user_b, org_b)

    create_res = client.post(
        "/ai-incidents",
        json={"title": "x", "severity": "low", "ai_system_id": system_a},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    incident_id = create_res.json()["id"]

    res = client.patch(f"/ai-incidents/{incident_id}", json={"status": "closed"}, headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 404

    db = SessionLocal()
    row = db.query(AIIncident).filter(AIIncident.id == incident_id).first()
    assert row.status == "open"  # untouched
    db.close()


def test_update_incident_title_change_audit_has_no_title_text():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    create_res = client.post(
        "/ai-incidents",
        json={"title": "original title", "severity": "low", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    incident_id = create_res.json()["id"]

    res = client.patch(
        f"/ai-incidents/{incident_id}",
        json={"title": "a confidential renamed title nobody else should see"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    db = SessionLocal()
    row = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id, AuditLog.entity_type == "ai_incident", AuditLog.entity_id == incident_id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert row.details == "title"
    assert "confidential" not in row.details
    db.close()


def test_audit_chain_stays_valid_after_create_and_update():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    create_res = client.post(
        "/ai-incidents",
        json={"title": "x", "severity": "low", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    incident_id = create_res.json()["id"]
    client.patch(f"/ai-incidents/{incident_id}", json={"status": "in_progress"}, headers={"Authorization": f"Bearer {token}"})

    res = client.get("/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "valid"


def test_isolation_organization_b_never_sees_organization_as_incident():
    org_a, user_a, system_a = _new_org_with_user_and_system()
    org_b, user_b, _ = _new_org_with_user_and_system()
    token_a = _token(user_a, org_a)
    token_b = _token(user_b, org_b)

    client.post(
        "/ai-incidents",
        json={"title": "x", "severity": "low", "ai_system_id": system_a},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    res = client.get("/ai-incidents", headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 200
    assert res.json() == []
