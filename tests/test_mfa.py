"""Batch E, deel 2: TOTP second factor (setup, enable, two-step login, lockout, backup codes).

Users live in a fresh, UUID-named organization per test module run (never org 1/2), because the
test database and its audit chains persist across the whole session.
"""
import json
import secrets
import time
import uuid
from datetime import datetime, timedelta

import pyotp
import pytest
import sentry_sdk
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sentry_sdk.transport import Transport

from app.core import mfa, security
from app.core.observability import init_sentry
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)
PASSWORD = "Correct-Horse-Battery-9"


@pytest.fixture(autouse=True)
def _mfa_env(monkeypatch):
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    # bcrypt cost 4: same hash format, but the 10 backup-code hashes per enrollment stay fast in tests
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))


@pytest.fixture(scope="module")
def org_id():
    db = SessionLocal()
    org = Organization(name=f"mfa-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    oid = org.id
    db.close()
    return oid


def _make_user(org_id, role="admin", must_change=False):
    db = SessionLocal()
    user = User(
        username=f"mfa_{uuid.uuid4().hex[:10]}",
        password_hash=hash_password(PASSWORD),
        role=role,
        organization_id=org_id,
        is_active=True,
        is_super_admin=False,
        must_change_password=must_change,
    )
    db.add(user)
    db.commit()
    username = user.username
    db.close()
    return username


def _row(username):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == username).first()
        db.expunge(u)
        return u
    finally:
        db.close()


def _login(username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _enroll(username):
    """Full enrollment through the API; returns (secret, backup_codes, access_token_before_mfa)."""
    token = _login(username).json()["access_token"]
    setup = client.post("/auth/mfa/setup", headers=_auth(token))
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    code = pyotp.TOTP(secret).now()
    enable = client.post("/auth/mfa/enable", json={"code": code}, headers=_auth(token))
    assert enable.status_code == 200, enable.text
    return secret, enable.json()["backup_codes"], token


def _next_code(secret, ahead=1):
    """A valid code for a step after the one enrollment used (within the +/-1 tolerance)."""
    return pyotp.TOTP(secret).at(time.time() + 30 * ahead)


# ---------------------------------------------------------------------------
# Pure primitives
# ---------------------------------------------------------------------------

def test_totp_tolerance_and_replay():
    secret = mfa.new_secret()
    totp = pyotp.TOTP(secret)
    now = 1_800_000_000.0
    step = mfa.current_step(now)
    for offset in (-1, 0, 1):
        assert mfa.verify_totp(secret, totp.at(now + 30 * offset), None, now=now) == step + offset
    for offset in (-2, 2):
        assert mfa.verify_totp(secret, totp.at(now + 30 * offset), None, now=now) is None
    # replay: the step that was accepted (or any older one) can't be used again
    code = totp.at(now)
    assert mfa.verify_totp(secret, code, step, now=now) is None
    assert mfa.verify_totp(secret, totp.at(now - 30), step, now=now) is None
    assert mfa.verify_totp(secret, totp.at(now + 30), step, now=now) == step + 1
    assert mfa.verify_totp(secret, "12345", None, now=now) is None  # wrong format


def test_backup_codes_are_single_use_and_stored_hashed():
    codes = mfa.generate_backup_codes()
    assert len(codes) == 10 and len(set(codes)) == 10
    stored = mfa.hash_backup_codes(codes)
    for code in codes:
        assert code not in stored and code.replace("-", "") not in stored
    remaining = mfa.consume_backup_code(stored, codes[3].lower())  # case-insensitive, dash optional
    assert remaining is not None and len(json.loads(remaining)) == 9
    assert mfa.consume_backup_code(remaining, codes[3]) is None  # used once only
    assert mfa.consume_backup_code(remaining, "AAAAA-AAAAA") is None


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------

def test_setup_and_enable_store_encrypted_secret_and_hashed_codes(org_id):
    username = _make_user(org_id)
    secret, codes, token = _enroll(username)
    assert len(codes) == 10
    row = _row(username)
    assert row.mfa_enabled is True
    assert row.mfa_secret_enc and secret not in row.mfa_secret_enc
    assert mfa.decrypt_secret(row.mfa_secret_enc) == secret
    for code in codes:
        assert code not in row.mfa_backup_codes
    # a second setup/enable is refused while MFA is on
    assert client.post("/auth/mfa/setup", headers=_auth(token)).status_code == 409
    assert client.post("/auth/mfa/enable", json={"code": _next_code(secret)}, headers=_auth(token)).status_code == 409


def test_enable_with_wrong_code_fails_and_setup_can_restart(org_id):
    username = _make_user(org_id)
    token = _login(username).json()["access_token"]
    first = client.post("/auth/mfa/setup", headers=_auth(token)).json()["secret"]
    assert client.post("/auth/mfa/enable", json={"code": "000000"}, headers=_auth(token)).status_code == 401
    assert _row(username).mfa_enabled is False
    second = client.post("/auth/mfa/setup", headers=_auth(token)).json()["secret"]
    assert second != first  # setup may be repeated until confirmed


def test_setup_refuses_without_encryption_key_but_login_still_works(org_id, monkeypatch):
    monkeypatch.delenv("MFA_ENCRYPTION_KEY", raising=False)
    username = _make_user(org_id)
    login = _login(username)
    assert login.status_code == 200
    assert client.post("/auth/mfa/setup", headers=_auth(login.json()["access_token"])).status_code == 503


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_without_mfa_is_unchanged(org_id):
    body = _login(_make_user(org_id)).json()
    assert set(body) == {"access_token", "token_type"}
    assert body["token_type"] == "bearer"


def test_two_step_login(org_id):
    username = _make_user(org_id)
    secret, _codes, _ = _enroll(username)

    step1 = _login(username)
    assert step1.status_code == 200
    assert set(step1.json()) == {"mfa_required", "mfa_token"}  # no access token yet
    mfa_token = step1.json()["mfa_token"]
    # the MFA-step token is not an access token
    assert client.get("/modules", headers=_auth(mfa_token)).status_code == 401

    step2 = client.post("/login/mfa", json={"mfa_token": mfa_token, "code": _next_code(secret)})
    assert step2.status_code == 200, step2.text
    assert set(step2.json()) == {"access_token", "token_type"}
    assert client.get("/modules", headers=_auth(step2.json()["access_token"])).status_code == 200


def test_used_totp_step_cannot_be_replayed(org_id):
    username = _make_user(org_id)
    secret, _codes, _ = _enroll(username)
    code = _next_code(secret)
    tok = _login(username).json()["mfa_token"]
    assert client.post("/login/mfa", json={"mfa_token": tok, "code": code}).status_code == 200
    tok2 = _login(username).json()["mfa_token"]
    assert client.post("/login/mfa", json={"mfa_token": tok2, "code": code}).status_code == 401


def test_backup_code_works_once(org_id):
    username = _make_user(org_id)
    _secret, codes, _ = _enroll(username)
    tok = _login(username).json()["mfa_token"]
    assert client.post("/login/mfa", json={"mfa_token": tok, "code": codes[0]}).status_code == 200
    tok2 = _login(username).json()["mfa_token"]
    assert client.post("/login/mfa", json={"mfa_token": tok2, "code": codes[0]}).status_code == 401
    assert client.post("/login/mfa", json={"mfa_token": tok2, "code": codes[1]}).status_code == 200
    actions = _audit_actions(username)
    assert actions.count("mfa_backup_code_used") == 2


def test_lockout_after_five_wrong_codes_and_reset_on_success(org_id):
    username = _make_user(org_id)
    secret, _codes, _ = _enroll(username)
    tok = _login(username).json()["mfa_token"]
    for _ in range(5):
        assert client.post("/login/mfa", json={"mfa_token": tok, "code": "000000"}).status_code == 401
    row = _row(username)
    assert row.mfa_locked_until and row.mfa_locked_until > datetime.utcnow()
    # locked: even the right code is refused (same generic 401)
    good = _next_code(secret)
    assert client.post("/login/mfa", json={"mfa_token": tok, "code": good}).status_code == 401
    # simulate the 15 minutes passing
    db = SessionLocal()
    db.query(User).filter(User.username == username).update({"mfa_locked_until": datetime.utcnow() - timedelta(seconds=1)})
    db.commit()
    db.close()
    assert client.post("/login/mfa", json={"mfa_token": tok, "code": good}).status_code == 200
    row = _row(username)
    assert row.mfa_failed_attempts == 0 and row.mfa_locked_until is None
    assert "mfa_locked" in _audit_actions(username)


def test_failures_are_generic(org_id):
    username = _make_user(org_id)
    _enroll(username)
    tok = _login(username).json()["mfa_token"]
    wrong_code = client.post("/login/mfa", json={"mfa_token": tok, "code": "111111"})
    garbage = client.post("/login/mfa", json={"mfa_token": "not-a-jwt", "code": "111111"})
    ghost = security.create_access_token(
        {"sub": "no_such_user", "org_id": org_id, "purpose": "mfa"}, expires_delta=timedelta(minutes=5)
    )
    unknown = client.post("/login/mfa", json={"mfa_token": ghost, "code": "111111"})
    # an ordinary access token is not accepted as mfa_token either
    plain = client.post("/login/mfa", json={"mfa_token": security.create_access_token({"sub": username, "org_id": org_id}), "code": "111111"})
    for res in (wrong_code, garbage, unknown, plain):
        assert res.status_code == 401
        assert res.json() == {"detail": "Invalid credentials"}


def test_disable_needs_password_and_code(org_id):
    username = _make_user(org_id)
    secret, _codes, token = _enroll(username)
    bad = client.post("/auth/mfa/disable", json={"password": "wrong-password-1", "code": _next_code(secret)}, headers=_auth(token))
    assert bad.status_code == 401
    ok = client.post("/auth/mfa/disable", json={"password": PASSWORD, "code": _next_code(secret, ahead=1)}, headers=_auth(token))
    assert ok.status_code == 200, ok.text
    row = _row(username)
    assert row.mfa_enabled is False and row.mfa_secret_enc is None and row.mfa_backup_codes is None
    assert set(_login(username).json()) == {"access_token", "token_type"}  # plain login again


def test_super_admin_cannot_disable_mfa(org_id):
    username = _make_user(org_id)
    secret, _codes, token = _enroll(username)
    db = SessionLocal()
    db.query(User).filter(User.username == username).update({"is_super_admin": True})
    db.commit()
    db.close()
    res = client.post("/auth/mfa/disable", json={"password": PASSWORD, "code": _next_code(secret)}, headers=_auth(token))
    assert res.status_code == 403
    assert _row(username).mfa_enabled is True


# ---------------------------------------------------------------------------
# Audit lines and no secrets in logs/Sentry
# ---------------------------------------------------------------------------

def _audit_actions(username):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        rows = db.query(AuditLog).filter(AuditLog.entity_type == "user_mfa", AuditLog.entity_id == user.id).all()
        return [r.action for r in rows]
    finally:
        db.close()


def test_audit_lines_exist_and_contain_no_secret_or_code(org_id):
    username = _make_user(org_id)
    secret, codes, _ = _enroll(username)
    tok = _login(username).json()["mfa_token"]
    client.post("/login/mfa", json={"mfa_token": tok, "code": "222222"})
    client.post("/login/mfa", json={"mfa_token": tok, "code": codes[0]})
    assert {"mfa_enrollment_started", "mfa_enrollment_confirmed", "mfa_failed", "mfa_backup_code_used"} <= set(_audit_actions(username))
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    blob = json.dumps([[r.action, r.details, r.performed_by] for r in db.query(AuditLog).filter(AuditLog.entity_id == user.id).all()])
    db.close()
    assert secret not in blob and "222222" not in blob
    for code in codes:
        assert code not in blob and code.replace("-", "") not in blob


class _Capture(Transport):
    def __init__(self):
        super().__init__()
        self.events = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)


def test_no_secret_or_code_in_logs_or_sentry(org_id, monkeypatch, caplog):
    transport = _Capture()
    assert init_sentry(dsn="https://publickey@o0.ingest.example.invalid/1", transport=transport)
    try:
        caplog.set_level("DEBUG")
        username = _make_user(org_id)
        secret, codes, _ = _enroll(username)
        tok = _login(username).json()["mfa_token"]
        wrong = f"{secrets.randbelow(10**6):06d}"  # random, so no literal sits in the source lines Sentry may attach
        client.post("/login/mfa", json={"mfa_token": tok, "code": wrong})
        good = _next_code(secret)
        # force an unhandled error inside the verification path, with the real code in flight
        monkeypatch.setattr(mfa, "verify_totp", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("verification exploded")))
        res = client.post("/login/mfa", json={"mfa_token": tok, "code": good})
        assert res.status_code == 500
        sentry_sdk.flush()
        assert transport.events, "the error was not captured"
        haystack = json.dumps(transport.events) + caplog.text
        for secret_value in [secret, good, wrong, tok, *codes, *(c.replace("-", "") for c in codes)]:
            assert secret_value not in haystack
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init()
