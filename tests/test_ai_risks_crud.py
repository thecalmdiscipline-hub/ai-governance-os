"""Batch O3 (2026-10-07): PATCH /ai-risks/{id} (POST /ai-risks already existed, Batch F).

Mirrors O1's incident endpoints: get_org_scoped_risk (already existed) for 404-on-foreign-org,
no extra role check, audit details never carry title/description/mitigation text. Isolated test
orgs/users (not the ambient demo state)."""
import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.ai_risk import AIRisk
from app.models.ai_system import AISystem
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)


def _new_org_with_user_and_system():
    db = SessionLocal()
    org = Organization(name=f"risk-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    user = User(
        username=f"risk-user-{uuid.uuid4().hex[:8]}",
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


def _token(username, org_id, mfa=False):
    return create_access_token({"sub": username, "org_id": org_id, "role": "admin", "mfa": mfa})


def _make_super_admin(username, org_id):
    db = SessionLocal()
    db.query(User).filter(User.username == username).update({"is_super_admin": True, "mfa_enabled": True})
    db.commit()
    db.close()
    return _token(username, org_id, mfa=True)


def _create_risk(token, system_id, level="medium", title="x"):
    res = client.post(
        "/ai-risks",
        json={"title": title, "risk_level": level, "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_create_still_works_and_now_rejects_extra_fields():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)

    ok = client.post(
        "/ai-risks",
        json={"title": "x", "risk_level": "medium", "ai_system_id": system_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 200

    rejected = client.post(
        "/ai-risks",
        json={"title": "x", "risk_level": "medium", "ai_system_id": system_id, "extra": "nope"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rejected.status_code == 422


def test_update_title_and_mitigation_success():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    risk_id = _create_risk(token, system_id)

    res = client.patch(
        f"/ai-risks/{risk_id}",
        json={"title": "New title", "mitigation": "New mitigation"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "New title"
    assert body["mitigation"] == "New mitigation"


def test_update_rejects_invalid_level_and_extra_fields():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    risk_id = _create_risk(token, system_id)

    for body in ({"risk_level": "critical"}, {"risk_level": "medium", "note": "hello"}):
        res = client.patch(f"/ai-risks/{risk_id}", json=body, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 422, body


def test_update_on_another_organizations_risk_gives_404():
    org_a, user_a, system_a = _new_org_with_user_and_system()
    org_b, user_b, _ = _new_org_with_user_and_system()
    token_a = _token(user_a, org_a)
    token_b = _token(user_b, org_b)
    risk_id = _create_risk(token_a, system_a)

    res = client.patch(f"/ai-risks/{risk_id}", json={"title": "hijack"}, headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 404

    db = SessionLocal()
    row = db.query(AIRisk).filter(AIRisk.id == risk_id).first()
    assert row.title == "x"  # untouched
    db.close()


def test_regular_admin_cannot_lower_a_high_risk_level():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    risk_id = _create_risk(token, system_id, level="high")

    res = client.patch(f"/ai-risks/{risk_id}", json={"risk_level": "medium"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

    db = SessionLocal()
    row = db.query(AIRisk).filter(AIRisk.id == risk_id).first()
    assert row.risk_level == "high"  # untouched
    db.close()


def test_regular_admin_can_edit_a_high_risks_other_fields_without_changing_level():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    risk_id = _create_risk(token, system_id, level="high")

    res = client.patch(f"/ai-risks/{risk_id}", json={"mitigation": "updated mitigation"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["risk_level"] == "high"


def test_regular_admin_can_raise_a_risk_level():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    risk_id = _create_risk(token, system_id, level="low")

    res = client.patch(f"/ai-risks/{risk_id}", json={"risk_level": "high"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["risk_level"] == "high"


def test_super_admin_can_lower_a_high_risk_level():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    risk_id = _create_risk(token, system_id, level="high")

    super_token = _make_super_admin(username, org_id)
    res = client.patch(f"/ai-risks/{risk_id}", json={"risk_level": "low"}, headers={"Authorization": f"Bearer {super_token}"})
    assert res.status_code == 200
    assert res.json()["risk_level"] == "low"


def test_audit_log_has_old_new_level_but_no_title_or_mitigation_text():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    risk_id = _create_risk(token, system_id, level="medium")

    res = client.patch(
        f"/ai-risks/{risk_id}",
        json={"title": "a confidential renamed title", "risk_level": "low"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    db = SessionLocal()
    row = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id, AuditLog.entity_type == "ai_risk", AuditLog.entity_id == risk_id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert row is not None
    assert row.action == "risk_updated"
    assert "title" in row.details
    assert "risk_level:medium->low" in row.details
    assert "confidential" not in row.details
    db.close()


def test_audit_chain_stays_valid_after_update():
    org_id, username, system_id = _new_org_with_user_and_system()
    token = _token(username, org_id)
    risk_id = _create_risk(token, system_id)
    client.patch(f"/ai-risks/{risk_id}", json={"risk_level": "high"}, headers={"Authorization": f"Bearer {token}"})

    res = client.get("/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "valid"


def test_isolation_organization_b_never_sees_organization_as_risk():
    org_a, user_a, system_a = _new_org_with_user_and_system()
    org_b, user_b, _ = _new_org_with_user_and_system()
    token_a = _token(user_a, org_a)
    token_b = _token(user_b, org_b)
    _create_risk(token_a, system_a)

    res = client.get("/ai-risks", headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 200
    assert res.json() == []
