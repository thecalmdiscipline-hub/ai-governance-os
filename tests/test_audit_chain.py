"""Batch A, deel 2: per-organization audit chain (v2 marker design).

Uses fresh organizations (never org 1) because the in-memory test DB is
shared across the whole test session, and audit_logs accumulate per
organization across every test that touches it. Tests that deliberately
corrupt a row (3, 4, 5) use a UUID-suffixed, always-unique organization
name rather than a fixed one, since that corruption is permanent
(audit_logs are immutable by design) and would otherwise poison a
fixed-name organization forever across repeated local runs against a
persistent (non-in-memory) test.db.
"""
import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import text

from app.main import app
from app.core.audit import (
    CHAIN_V2_ACTION,
    CHAIN_V2_ENTITY_TYPE,
    create_audit_log,
    generate_hmac_signature,
)
from app.core.security import ALGORITHM, SECRET_KEY, hash_password
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.user import User

client = TestClient(app)


def _fresh_org_and_user(db, name):
    org = db.query(Organization).filter(Organization.name == name).first()
    if org is None:
        org = Organization(name=name)
        db.add(org)
        db.commit()
        db.refresh(org)

    username = name.lower().replace(" ", "_") + "_admin"
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        user = User(
            username=username,
            password_hash=hash_password("Test123!"),
            role="admin",
            organization_id=org.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return org, user


def _token_for(user, org_id):
    payload = {"sub": user.username, "role": user.role, "org_id": org_id}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _verify(user, org_id):
    res = client.get(
        "/audit/verify",
        headers={"Authorization": f"Bearer {_token_for(user, org_id)}"},
    )
    assert res.status_code == 200
    return res.json()


def _get_or_insert_raw_row(db, organization_id, entity_type, entity_id, action, details, performed_by, previous_hash):
    """Simulates a row written by the pre-fix create_audit_log() (global
    previous_hash chaining) -- still correctly HMAC'd, since the write
    side's bug was only in what previous_hash it picked, not in how the
    hash itself was computed. Idempotent so repeated local runs against a
    persistent test.db don't pile up duplicate rows."""
    existing = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == organization_id,
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
            AuditLog.action == action,
            AuditLog.details == details,
        )
        .first()
    )
    if existing is not None:
        return existing

    timestamp = datetime.utcnow()
    raw_string = f"{organization_id}{entity_type}{entity_id}{action}{details}{performed_by}{timestamp}{previous_hash}"
    row = AuditLog(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        performed_by=performed_by,
        timestamp=timestamp,
        details=details,
        previous_hash=previous_hash,
        record_hash=generate_hmac_signature(raw_string),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 1. Single tenant, multiple logs via create_audit_log -> valid.
# ---------------------------------------------------------------------------

def test_single_tenant_multiple_logs_valid_with_marker():
    db = SessionLocal()
    org, user = _fresh_org_and_user(db, "Audit Test Org 1")

    create_audit_log(db, organization_id=org.id, entity_type="document", entity_id=1, action="uploaded", details="d1", performed_by="tester")
    create_audit_log(db, organization_id=org.id, entity_type="document", entity_id=2, action="uploaded", details="d2", performed_by="tester")

    result = _verify(user, org.id)
    assert result["status"] == "valid"
    assert result["chain_v2_started"] is True
    assert result["chain_rows_checked"] >= 2

    marker = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org.id, AuditLog.entity_type == CHAIN_V2_ENTITY_TYPE, AuditLog.action == CHAIN_V2_ACTION)
        .first()
    )
    assert marker is not None
    assert marker.previous_hash is None
    db.close()


# ---------------------------------------------------------------------------
# 2. Two tenants writing interleaved -> both valid.
# ---------------------------------------------------------------------------

def test_two_tenants_interleaved_writes_both_valid():
    db = SessionLocal()
    org_a, user_a = _fresh_org_and_user(db, "Audit Test Org 2A")
    org_b, user_b = _fresh_org_and_user(db, "Audit Test Org 2B")

    create_audit_log(db, organization_id=org_a.id, entity_type="document", entity_id=1, action="uploaded", details="a1", performed_by="tester")
    create_audit_log(db, organization_id=org_b.id, entity_type="document", entity_id=1, action="uploaded", details="b1", performed_by="tester")
    create_audit_log(db, organization_id=org_a.id, entity_type="document", entity_id=2, action="uploaded", details="a2", performed_by="tester")
    create_audit_log(db, organization_id=org_b.id, entity_type="document", entity_id=2, action="uploaded", details="b2", performed_by="tester")

    assert _verify(user_a, org_a.id)["status"] == "valid"
    assert _verify(user_b, org_b.id)["status"] == "valid"
    db.close()


# ---------------------------------------------------------------------------
# 3. Manipulation via raw SQL (bypasses ORM immutability events) -> compromised.
# ---------------------------------------------------------------------------

def test_manipulated_v2_row_detected_as_compromised():
    db = SessionLocal()
    org, user = _fresh_org_and_user(db, f"Audit Test Org 3 {uuid.uuid4().hex[:8]}")

    create_audit_log(db, organization_id=org.id, entity_type="document", entity_id=1, action="uploaded", details="original", performed_by="tester")

    tampered = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org.id, AuditLog.entity_type == "document")
        .order_by(AuditLog.id.desc())
        .first()
    )
    db.execute(text("UPDATE audit_logs SET details = :d WHERE id = :id"), {"d": "tampered", "id": tampered.id})
    db.commit()

    result = _verify(user, org.id)
    assert result["status"] == "compromised"
    assert result["log_id"] == tampered.id
    db.close()


# ---------------------------------------------------------------------------
# 4. Deleting a middle v2 row (raw SQL) -> compromised (chain linkage breaks,
#    no id-contiguity check needed).
# ---------------------------------------------------------------------------

def test_deleted_middle_v2_row_detected_as_compromised():
    db = SessionLocal()
    org, user = _fresh_org_and_user(db, f"Audit Test Org 4 {uuid.uuid4().hex[:8]}")

    create_audit_log(db, organization_id=org.id, entity_type="document", entity_id=1, action="uploaded", details="d1", performed_by="tester")
    create_audit_log(db, organization_id=org.id, entity_type="document", entity_id=2, action="uploaded", details="d2", performed_by="tester")
    create_audit_log(db, organization_id=org.id, entity_type="document", entity_id=3, action="uploaded", details="d3", performed_by="tester")

    rows = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org.id, AuditLog.entity_type == "document")
        .order_by(AuditLog.id.asc())
        .all()
    )
    middle = rows[1]
    db.execute(text("DELETE FROM audit_logs WHERE id = :id"), {"id": middle.id})
    db.commit()

    result = _verify(user, org.id)
    assert result["status"] == "compromised"
    db.close()


# ---------------------------------------------------------------------------
# 5. Legacy rows (old global-chain algorithm) followed by v2 rows -> valid,
#    with legacy_rows_checked > 0; manipulating a legacy row -> compromised.
# ---------------------------------------------------------------------------

def test_legacy_rows_then_v2_rows_valid_and_legacy_manipulation_detected():
    db = SessionLocal()
    org, user = _fresh_org_and_user(db, f"Audit Test Org 5 {uuid.uuid4().hex[:8]}")

    legacy_1 = _get_or_insert_raw_row(db, org.id, "document", 1, "uploaded", "legacy1", "tester", previous_hash=None)
    _get_or_insert_raw_row(db, org.id, "document", 2, "uploaded", "legacy2", "tester", previous_hash="not-from-this-orgs-chain")

    create_audit_log(db, organization_id=org.id, entity_type="document", entity_id=3, action="uploaded", details="v2 row", performed_by="tester")

    result = _verify(user, org.id)
    assert result["status"] == "valid"
    assert result["legacy_rows_checked"] == 2
    assert result["chain_v2_started"] is True

    db.execute(text("UPDATE audit_logs SET details = :d WHERE id = :id"), {"d": "tampered legacy", "id": legacy_1.id})
    db.commit()

    result2 = _verify(user, org.id)
    assert result2["status"] == "compromised"
    assert result2["log_id"] == legacy_1.id
    db.close()


# ---------------------------------------------------------------------------
# 6. Roundtrip: write -> commit -> expire_all/new session -> still valid
#    (confirms timestamp formatting round-trips identically).
# ---------------------------------------------------------------------------

def test_roundtrip_through_fresh_session_still_valid():
    db = SessionLocal()
    org, user = _fresh_org_and_user(db, "Audit Test Org 6")
    org_id = org.id
    username, role = user.username, user.role
    create_audit_log(db, organization_id=org_id, entity_type="document", entity_id=1, action="uploaded", details="d1", performed_by="tester")
    db.expire_all()
    db.close()

    # user/org are now detached; use the plain values captured above so
    # the HTTP call below reads everything back through the endpoint's
    # own fresh session, not these expired ORM instances.
    token = jwt.encode({"sub": username, "role": role, "org_id": org_id}, SECRET_KEY, algorithm=ALGORITHM)
    res = client.get("/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "valid"


# ---------------------------------------------------------------------------
# 7. Endpoint test: organizations with and without the v2 marker.
# ---------------------------------------------------------------------------

def test_endpoint_valid_for_org_without_any_marker_yet():
    db = SessionLocal()
    org, user = _fresh_org_and_user(db, "Audit Test Org 7 No Marker")
    result = _verify(user, org.id)
    assert result["status"] == "valid"
    assert result["chain_v2_started"] is False
    assert result["chain_rows_checked"] == 0
    db.close()


def test_endpoint_valid_for_org_with_marker():
    db = SessionLocal()
    org, user = _fresh_org_and_user(db, "Audit Test Org 7 With Marker")
    create_audit_log(db, organization_id=org.id, entity_type="document", entity_id=1, action="uploaded", details="d1", performed_by="tester")
    result = _verify(user, org.id)
    assert result["status"] == "valid"
    assert result["chain_v2_started"] is True
    db.close()
