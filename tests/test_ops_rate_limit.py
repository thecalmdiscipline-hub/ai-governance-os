"""Batch R2 (2026-10-07): rate limiting on /ops/* (require_ops_access -> rate_limit_ops), keyed by
the authenticated super-admin's user id, not IP, so a shared office IP never throttles one admin
because of another's traffic. 60 requests/60s — generous enough that normal manual use and the
portal's 10s /ops/whoami poll (~6/min) stay nowhere near it.

rate_limiter.py's own TESTING-mode skip is disabled only inside this file (via a fixture), so the
real Redis-backed counting logic actually runs; every other test file in the suite is unaffected
and keeps the existing, safe default of no rate limiting during tests."""
import uuid

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

import app.core.rate_limiter as rate_limiter
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.organization import Organization
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)
PASSWORD = "Correct-Horse-Battery-9"


def _new_org():
    db = SessionLocal()
    org = Organization(name=f"ops-rl-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    org_id = org.id
    db.close()
    return org_id


def _super_admin_in(org_id):
    db = SessionLocal()
    name = f"ops-rl-user-{uuid.uuid4().hex[:10]}"
    db.add(User(
        username=name, password_hash=hash_password(PASSWORD), role="admin", organization_id=org_id,
        is_active=True, is_super_admin=True, mfa_enabled=True,
    ))
    db.commit()
    db.close()
    return name


def _token(username, org_id):
    return create_access_token({"sub": username, "org_id": org_id, "role": "admin", "mfa": True})


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def hq(monkeypatch):
    org_id = _new_org()
    monkeypatch.setenv("HQ_ORGANIZATION_ID", str(org_id))
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    return org_id


@pytest.fixture
def real_ops_rate_limit(monkeypatch):
    """Turns on the real check for /ops/* only, with a small threshold so the test is fast and
    deterministic. Other test files are unaffected: this patches the module's own attributes for
    the duration of this one test, via monkeypatch's automatic teardown."""
    monkeypatch.setattr(rate_limiter, "_in_test_mode", lambda: False)
    monkeypatch.setattr(rate_limiter, "_OPS_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(rate_limiter, "_OPS_WINDOW_SECONDS", 60)


def test_requests_under_the_limit_succeed(hq, real_ops_rate_limit):
    name = _super_admin_in(hq)
    token = _token(name, hq)

    for _ in range(3):
        assert client.get("/ops/whoami", headers=_h(token)).status_code == 200


def test_requests_over_the_limit_get_429_with_a_generic_message(hq, real_ops_rate_limit):
    name = _super_admin_in(hq)
    token = _token(name, hq)

    for _ in range(3):
        assert client.get("/ops/whoami", headers=_h(token)).status_code == 200

    res = client.get("/ops/whoami", headers=_h(token))
    assert res.status_code == 429
    body = res.json()
    assert body["detail"] == "Too many requests. Try again later."
    # No part of the username/token/key ever appears in the error body.
    assert name not in str(body)
    assert token not in str(body)


def test_isolation_between_two_super_admins(hq, real_ops_rate_limit):
    name_a = _super_admin_in(hq)
    name_b = _super_admin_in(hq)
    token_a = _token(name_a, hq)
    token_b = _token(name_b, hq)

    for _ in range(3):
        assert client.get("/ops/whoami", headers=_h(token_a)).status_code == 200
    assert client.get("/ops/whoami", headers=_h(token_a)).status_code == 429

    # Admin B, same HQ organization, is completely unaffected by admin A's traffic.
    assert client.get("/ops/whoami", headers=_h(token_b)).status_code == 200


def test_unauthorized_requests_never_spend_a_rate_limit_slot(hq, real_ops_rate_limit):
    """require_ops_access checks authorization before rate_limit_ops runs, so a non-super-admin
    hammering /ops/* can never exhaust a real super-admin's quota."""
    ordinary_org = _new_org()
    db = SessionLocal()
    ordinary_name = f"ops-rl-ordinary-{uuid.uuid4().hex[:10]}"
    db.add(User(username=ordinary_name, password_hash=hash_password(PASSWORD), role="admin",
                organization_id=ordinary_org, is_active=True, is_super_admin=False))
    db.commit()
    db.close()
    ordinary_token = create_access_token({"sub": ordinary_name, "org_id": ordinary_org, "role": "admin", "mfa": False})

    for _ in range(10):
        assert client.get("/ops/whoami", headers=_h(ordinary_token)).status_code == 403

    # A real super-admin's own fresh quota is untouched.
    name = _super_admin_in(hq)
    token = _token(name, hq)
    for _ in range(3):
        assert client.get("/ops/whoami", headers=_h(token)).status_code == 200


def test_default_test_mode_leaves_ops_unlimited(hq):
    """Without the real_ops_rate_limit fixture, TESTING mode is active (as it is for the rest of
    the suite) and /ops/* is not limited at all, even past what would otherwise be the threshold
    — this is what keeps the ~450 other tests that call /ops/* endpoints safe."""
    name = _super_admin_in(hq)
    token = _token(name, hq)

    for _ in range(10):
        assert client.get("/ops/whoami", headers=_h(token)).status_code == 200


def test_shared_counting_primitive_still_behaves_like_the_original_login_limiter():
    """rate_limit_login and rate_limit_ops both now call the same generalized _check_memory/
    _check_redis helpers. This exercises that shared primitive directly, with a unique key (so it
    can never collide with another test or a previous run), proving the refactor kept the
    original login behavior (N successes, then a 429) intact."""
    key = f"login-equivalence-{uuid.uuid4().hex}"
    for _ in range(5):
        rate_limiter._check_memory(key, window=60, max_attempts=5, message=rate_limiter._LOGIN_MESSAGE)

    with pytest.raises(Exception) as exc_info:
        rate_limiter._check_memory(key, window=60, max_attempts=5, message=rate_limiter._LOGIN_MESSAGE)
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "Too many login attempts. Try again later."
