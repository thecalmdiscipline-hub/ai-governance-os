"""Batch N2 (2026-10-07): POST /ai-policy's monitoring_commitment now shares one constant
(app/core/provisioning_defaults.MONITORING_COMMITMENT_TEXT) with the provisioning template,
instead of its own separately hardcoded "AI systems are continuously monitored." overclaim.

No test existed for this endpoint before (confirmed via grep across tests/ — app/api/governance.py
had zero API-level coverage). This file adds the one test this fix needs; it does not retroactively
cover the rest of POST /ai-policy's behaviour."""
import uuid

from fastapi.testclient import TestClient

from app.core.provisioning_defaults import MONITORING_COMMITMENT_TEXT
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.organization import Organization
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)


def test_generate_ai_policy_uses_the_shared_monitoring_commitment_text():
    db = SessionLocal()
    org = Organization(name=f"ai-policy-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    user = User(
        username=f"ai-policy-user-{uuid.uuid4().hex[:8]}",
        password_hash="x",
        role="admin",
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    org_id, username = org.id, user.username
    db.close()

    token = create_access_token({"sub": username, "org_id": org_id, "role": "admin", "mfa": False})
    res = client.post("/ai-policy", json={"organization_id": org_id}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["monitoring_commitment"] == MONITORING_COMMITMENT_TEXT
    assert "continuously" not in body["monitoring_commitment"]
