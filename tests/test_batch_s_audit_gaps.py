"""Batch S (2026-10-12): audit entries for four governance write endpoints that never wrote one —
POST /ai-systems, POST /ai-risks, DELETE /ai-risks/{id}, POST /production-approvals/{system_id}.

Fase 0 (see CLAUDE.md) confirmed these were the only four write endpoints in app/api/governance.py
missing a create_audit_log() call; create_audit_log() itself, the hash-chain logic, and all other
endpoints in this file are unchanged. No migration, no schema change, no portal change. Details
never carry title/description/mitigation text or personal data — only which entity was created/
deleted, matching the newer "<Entity> created" pattern already used for incidents/corrective
actions/evidence in this same file. Isolated test orgs/users (not the ambient demo state)."""
import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.ai_risk import AIRisk
from app.models.ai_system import AISystem
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.production_approval import ProductionApproval
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)


def _new_org_with_user_and_system():
    db = SessionLocal()
    org = Organization(name=f"audit-gap-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    user = User(
        username=f"audit-gap-user-{uuid.uuid4().hex[:8]}",
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


def _token(username, org_id, role="admin"):
    return create_access_token({"sub": username, "org_id": org_id, "role": role, "mfa": False})


def _audit_rows(org_id, entity_type, entity_id):
    db = SessionLocal()
    rows = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == org_id,
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
        )
        .all()
    )
    db.close()
    return rows


# ---------------------------------------------------------------------------
# POST /ai-systems
# ---------------------------------------------------------------------------

def test_create_ai_system_writes_exactly_one_audit_row():
    org_id, username, _ = _new_org_with_user_and_system()
    token = _token(username, org_id)

    res = client.post(
        "/ai-systems",
        json={"name": "Confidential Project Phoenix", "organization_id": org_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    system_id = res.json()["id"]

    rows = _audit_rows(org_id, "ai_system", system_id)
    assert len(rows) == 1
    assert rows[0].action == "created"
    assert rows[0].details == "AISystem created"
    assert "Confidential Project Phoenix" not in rows[0].details


def test_create_ai_system_failed_validation_writes_no_audit_row():
    org_id, username, _ = _new_org_with_user_and_system()
    token = _token(username, org_id)

    res = client.post(
        "/ai-systems",
        json={"organization_id": org_id},  # missing required "name"
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422

    db = SessionLocal()
    count_before = db.query(AuditLog).filter(AuditLog.organization_id == org_id, AuditLog.entity_type == "ai_system").count()
    db.close()
    assert count_before == 0


def test_create_ai_system_isolation_and_chain_valid():
    org_id, username, _ = _new_org_with_user_and_system()
    token = _token(username, org_id)
    other_org_id, other_username, _ = _new_org_with_user_and_system()
    other_token = _token(other_username, other_org_id)

    client.post("/ai-systems", json={"name": "x", "organization_id": org_id}, headers={"Authorization": f"Bearer {token}"})

    res = client.get("/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "valid"

    db = SessionLocal()
    other_count = db.query(AuditLog).filter(AuditLog.organization_id == other_org_id, AuditLog.entity_type == "ai_system").count()
    db.close()
    assert other_count == 0


# ---------------------------------------------------------------------------
# POST /ai-risks
# ---------------------------------------------------------------------------

def test_create_ai_risk_writes_exactly_one_audit_row_without_title_text():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)

    res = client.post(
        "/ai-risks",
        json={"title": "A secret failure mode", "risk_level": "medium", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    risk_id = res.json()["id"]

    rows = _audit_rows(org_id, "ai_risk", risk_id)
    assert len(rows) == 1
    assert rows[0].action == "created"
    assert rows[0].details == "AIRisk created"
    assert "secret failure mode" not in rows[0].details


def test_create_ai_risk_on_another_orgs_system_gives_404_and_writes_no_audit_row():
    org_a, _, system_a = _new_org_with_user_and_system()
    org_b, user_b, _ = _new_org_with_user_and_system()
    token_b = _token(user_b, org_b)

    res = client.post(
        "/ai-risks",
        json={"title": "x", "risk_level": "medium", "ai_system_id": system_a},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 404

    db = SessionLocal()
    count = db.query(AuditLog).filter(AuditLog.organization_id == org_a, AuditLog.entity_type == "ai_risk").count()
    db.close()
    assert count == 0


def test_create_ai_risk_chain_valid():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)

    client.post(
        "/ai-risks",
        json={"title": "x", "risk_level": "low", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    res = client.get("/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "valid"


# ---------------------------------------------------------------------------
# DELETE /ai-risks/{risk_id}
# ---------------------------------------------------------------------------

def test_delete_ai_risk_writes_exactly_one_audit_row():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    create_res = client.post(
        "/ai-risks",
        json={"title": "A low risk to be removed", "risk_level": "low", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    risk_id = create_res.json()["id"]

    res = client.delete(f"/ai-risks/{risk_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

    rows = _audit_rows(org_id, "ai_risk", risk_id)
    assert len(rows) == 2  # "created" then "deleted"
    assert rows[-1].action == "deleted"
    assert rows[-1].details == "AIRisk soft-deleted"
    assert "to be removed" not in rows[-1].details

    db = SessionLocal()
    row = db.query(AIRisk).filter(AIRisk.id == risk_id).first()
    assert row.is_deleted is True
    db.close()


def test_delete_ai_risk_blocked_for_high_risk_without_super_admin_writes_no_audit_row():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    create_res = client.post(
        "/ai-risks",
        json={"title": "x", "risk_level": "high", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    risk_id = create_res.json()["id"]

    res = client.delete(f"/ai-risks/{risk_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

    rows = _audit_rows(org_id, "ai_risk", risk_id)
    assert len(rows) == 1  # only the earlier "created" row, no "deleted" row
    assert rows[0].action == "created"


def test_delete_ai_risk_on_another_organizations_risk_gives_404():
    org_a, user_a, system_a = _new_org_with_user_and_system()
    org_b, user_b, _ = _new_org_with_user_and_system()
    token_a = _token(user_a, org_a)
    token_b = _token(user_b, org_b)

    create_res = client.post(
        "/ai-risks",
        json={"title": "x", "risk_level": "low", "ai_system_id": system_a},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    risk_id = create_res.json()["id"]

    res = client.delete(f"/ai-risks/{risk_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 404

    db = SessionLocal()
    row = db.query(AIRisk).filter(AIRisk.id == risk_id).first()
    assert row.is_deleted is False  # untouched
    db.close()


def test_delete_ai_risk_chain_valid():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    create_res = client.post(
        "/ai-risks",
        json={"title": "x", "risk_level": "low", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    risk_id = create_res.json()["id"]
    client.delete(f"/ai-risks/{risk_id}", headers={"Authorization": f"Bearer {token}"})

    res = client.get("/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "valid"


# ---------------------------------------------------------------------------
# POST /production-approvals/{system_id}
# ---------------------------------------------------------------------------

def test_approve_production_writes_exactly_one_audit_row():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)

    res = client.post(f"/production-approvals/{system_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    approval_id = res.json()  # endpoint returns a dict, fetch the row directly below

    db = SessionLocal()
    approval = db.query(ProductionApproval).filter(ProductionApproval.ai_system_id == system_id).first()
    assert approval is not None
    db.close()

    rows = _audit_rows(org_id, "production_approval", approval.id)
    assert len(rows) == 1
    assert rows[0].action == "created"
    assert rows[0].details == "ProductionApproval created"


def test_approve_production_requires_admin_role_and_writes_no_audit_row_when_denied():
    # current_user.role comes from the DB row (loaded by username), not from a token claim —
    # so denying this requires an actual viewer-role user, not just a different "role" in the JWT.
    org_id, _, system_id = _new_org_with_user_and_system()
    db = SessionLocal()
    viewer = User(
        username=f"audit-gap-viewer-{uuid.uuid4().hex[:8]}",
        password_hash="x",
        role="viewer",
        organization_id=org_id,
        is_active=True,
    )
    db.add(viewer)
    db.commit()
    viewer_username = viewer.username
    db.close()
    viewer_token = _token(viewer_username, org_id, role="viewer")

    res = client.post(f"/production-approvals/{system_id}", headers={"Authorization": f"Bearer {viewer_token}"})
    assert res.status_code == 403

    db = SessionLocal()
    count = db.query(AuditLog).filter(AuditLog.organization_id == org_id, AuditLog.entity_type == "production_approval").count()
    approval_count = db.query(ProductionApproval).filter(ProductionApproval.ai_system_id == system_id).count()
    db.close()
    assert count == 0
    assert approval_count == 0


def test_approve_production_on_another_organizations_system_gives_404():
    org_a, _, system_a = _new_org_with_user_and_system()
    org_b, user_b, _ = _new_org_with_user_and_system()
    token_b = _token(user_b, org_b)

    res = client.post(f"/production-approvals/{system_a}", headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 404

    db = SessionLocal()
    count = db.query(ProductionApproval).filter(ProductionApproval.ai_system_id == system_a).count()
    db.close()
    assert count == 0


def test_approve_production_chain_valid():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)

    client.post(f"/production-approvals/{system_id}", headers={"Authorization": f"Bearer {token}"})

    res = client.get("/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "valid"
