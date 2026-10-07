"""Batch O4 (2026-10-07): POST /evidence (now with an audit log and a full EvidenceResponse) and
the new PATCH /evidence/{id}. Metadata only — no file upload, no file_reference pointing at real
file storage; it is free text describing where the evidence is kept.

Evidence links via ai_system_id and/or ai_risk_id (the model has no ai_incident_id, unlike
CorrectiveAction after Batch O2) — this mirrors the existing GET /evidence's or_(...) scoping, not
O2's risk-or-incident one. Isolated test orgs/users (not the ambient demo state)."""
import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.ai_risk import AIRisk
from app.models.ai_system import AISystem
from app.models.audit_log import AuditLog
from app.models.evidence import Evidence
from app.models.organization import Organization
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)


def _new_org_with_user_system_and_risk():
    db = SessionLocal()
    org = Organization(name=f"ev-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    user = User(
        username=f"ev-user-{uuid.uuid4().hex[:8]}",
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
    db.add(risk)
    db.commit()
    org_id, username, system_id, risk_id = org.id, user.username, system.id, risk.id
    db.close()
    return org_id, username, system_id, risk_id


def _token(username, org_id):
    return create_access_token({"sub": username, "org_id": org_id, "role": "admin", "mfa": False})


def test_create_with_system_only_success():
    org_id, username, system_id, _ = _new_org_with_user_system_and_risk()
    token = _token(username, org_id)

    res = client.post(
        "/evidence",
        json={"title": "Screenshot of the review step", "description": "desc", "file_reference": "Policy v1.2 in the customer's own document system", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ai_system_id"] == system_id
    assert body["ai_risk_id"] is None
    assert body["file_reference"] == "Policy v1.2 in the customer's own document system"


def test_create_with_risk_only_success():
    org_id, username, _, risk_id = _new_org_with_user_system_and_risk()
    token = _token(username, org_id)

    res = client.post(
        "/evidence",
        json={"title": "Risk sign-off note", "ai_risk_id": risk_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ai_risk_id"] == risk_id
    assert body["ai_system_id"] is None


def test_create_with_both_success():
    org_id, username, system_id, risk_id = _new_org_with_user_system_and_risk()
    token = _token(username, org_id)

    res = client.post(
        "/evidence",
        json={"title": "x", "ai_system_id": system_id, "ai_risk_id": risk_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ai_system_id"] == system_id
    assert body["ai_risk_id"] == risk_id


def test_create_rejects_neither_system_nor_risk():
    org_id, username, _, _ = _new_org_with_user_system_and_risk()
    token = _token(username, org_id)

    res = client.post("/evidence", json={"title": "x"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 422


def test_create_rejects_extra_fields():
    org_id, username, system_id, _ = _new_org_with_user_system_and_risk()
    token = _token(username, org_id)

    res = client.post(
        "/evidence",
        json={"title": "x", "ai_system_id": system_id, "created_at": "2020-01-01T00:00:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


def test_create_with_unknown_system_id_gives_404_and_creates_nothing():
    org_id, username, system_id, _ = _new_org_with_user_system_and_risk()
    token = _token(username, org_id)
    bogus_id = system_id + 999999

    res = client.post("/evidence", json={"title": "x", "ai_system_id": bogus_id}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404

    db = SessionLocal()
    count = db.query(Evidence).filter(Evidence.ai_system_id == bogus_id).count()
    db.close()
    assert count == 0


def test_create_with_another_orgs_system_gives_404_and_creates_nothing():
    org_a, _, system_a, _ = _new_org_with_user_system_and_risk()
    org_b, user_b, _, _ = _new_org_with_user_system_and_risk()
    token_b = _token(user_b, org_b)

    res = client.post("/evidence", json={"title": "x", "ai_system_id": system_a}, headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 404

    db = SessionLocal()
    count = db.query(Evidence).filter(Evidence.ai_system_id == system_a).count()
    db.close()
    assert count == 0


def test_create_with_another_orgs_risk_gives_404_and_creates_nothing():
    org_a, _, _, risk_a = _new_org_with_user_system_and_risk()
    org_b, user_b, _, _ = _new_org_with_user_system_and_risk()
    token_b = _token(user_b, org_b)

    res = client.post("/evidence", json={"title": "x", "ai_risk_id": risk_a}, headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 404

    db = SessionLocal()
    count = db.query(Evidence).filter(Evidence.ai_risk_id == risk_a).count()
    db.close()
    assert count == 0


def test_create_writes_an_audit_log_without_title_or_description_text():
    org_id, username, system_id, _ = _new_org_with_user_system_and_risk()
    token = _token(username, org_id)

    res = client.post(
        "/evidence",
        json={"title": "a confidential title nobody else should see", "description": "a confidential description", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    evidence_id = res.json()["id"]

    db = SessionLocal()
    row = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id, AuditLog.entity_type == "evidence", AuditLog.entity_id == evidence_id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert row is not None
    assert row.action == "evidence_created"
    assert "confidential" not in (row.details or "")
    db.close()


def test_update_success_with_changed_fields_in_audit_log():
    org_id, username, system_id, _ = _new_org_with_user_system_and_risk()
    token = _token(username, org_id)

    create_res = client.post("/evidence", json={"title": "original", "ai_system_id": system_id}, headers={"Authorization": f"Bearer {token}"})
    evidence_id = create_res.json()["id"]

    res = client.patch(
        f"/evidence/{evidence_id}",
        json={"title": "updated", "file_reference": "New location"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "updated"
    assert body["file_reference"] == "New location"
    assert body["ai_system_id"] == system_id  # link unchanged

    db = SessionLocal()
    row = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id, AuditLog.entity_type == "evidence", AuditLog.entity_id == evidence_id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert row.action == "evidence_updated"
    assert set(row.details.split(", ")) == {"title", "file_reference"}
    db.close()


def test_update_cannot_move_evidence_to_a_different_link():
    org_id, username, system_id, risk_id = _new_org_with_user_system_and_risk()
    token = _token(username, org_id)

    create_res = client.post("/evidence", json={"title": "x", "ai_system_id": system_id}, headers={"Authorization": f"Bearer {token}"})
    evidence_id = create_res.json()["id"]

    res = client.patch(f"/evidence/{evidence_id}", json={"ai_risk_id": risk_id}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 422  # extra="forbid" — no linking fields on update


def test_update_on_another_organizations_evidence_gives_404_and_does_not_change_it():
    org_a, user_a, system_a, _ = _new_org_with_user_system_and_risk()
    org_b, user_b, _, _ = _new_org_with_user_system_and_risk()
    token_a = _token(user_a, org_a)
    token_b = _token(user_b, org_b)

    create_res = client.post("/evidence", json={"title": "original", "ai_system_id": system_a}, headers={"Authorization": f"Bearer {token_a}"})
    evidence_id = create_res.json()["id"]

    res = client.patch(f"/evidence/{evidence_id}", json={"title": "hacked"}, headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 404

    db = SessionLocal()
    row = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    assert row.title == "original"
    db.close()


def test_audit_chain_stays_valid_after_create_and_update():
    org_id, username, system_id, _ = _new_org_with_user_system_and_risk()
    token = _token(username, org_id)

    create_res = client.post("/evidence", json={"title": "x", "ai_system_id": system_id}, headers={"Authorization": f"Bearer {token}"})
    evidence_id = create_res.json()["id"]
    client.patch(f"/evidence/{evidence_id}", json={"description": "y"}, headers={"Authorization": f"Bearer {token}"})

    res = client.get("/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "valid"


def test_list_finds_evidence_created_via_post_scoped_to_own_org():
    org_a, user_a, system_a, _ = _new_org_with_user_system_and_risk()
    org_b, user_b, _, _ = _new_org_with_user_system_and_risk()
    token_a = _token(user_a, org_a)
    token_b = _token(user_b, org_b)

    create_res = client.post("/evidence", json={"title": "x", "ai_system_id": system_a}, headers={"Authorization": f"Bearer {token_a}"})
    evidence_id = create_res.json()["id"]

    res_a = client.get("/evidence", headers={"Authorization": f"Bearer {token_a}"})
    assert evidence_id in [e["id"] for e in res_a.json()]

    res_b = client.get("/evidence", headers={"Authorization": f"Bearer {token_b}"})
    assert evidence_id not in [e["id"] for e in res_b.json()]
