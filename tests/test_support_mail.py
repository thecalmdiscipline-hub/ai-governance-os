"""Batch G, deel 1b: the Resend notification (mocked: no network), the recovery script and secrecy."""
import importlib
import json
import uuid

import httpx
import pytest
import sentry_sdk
from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sentry_sdk.transport import Transport

from app.core import security
from app.core.observability import init_sentry
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.support_request import SupportRequest
from app.models.user import User
from app.services import support_mail

resend_script = importlib.import_module("scripts.resend_support_notifications")

client = TestClient(app, raise_server_exceptions=False)
PASSWORD = "Correct-Horse-Battery-9"
API_KEY = "re_TEST_KEY_do_not_leak_0123456789"
FROM, TO = "support@valqeron.example", "ops@valqeron.example"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))
    for name in ("RESEND_API_KEY", "SUPPORT_FROM_EMAIL", "SUPPORT_NOTIFY_EMAIL"):
        monkeypatch.delenv(name, raising=False)


def _configure(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", API_KEY)
    monkeypatch.setenv("SUPPORT_FROM_EMAIL", FROM)
    monkeypatch.setenv("SUPPORT_NOTIFY_EMAIL", TO)


class FakePost:
    def __init__(self, status=200, exc=None):
        self.status, self.exc, self.calls = status, exc, []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if self.exc is not None:
            raise self.exc
        return httpx.Response(self.status, json={"id": "abc"})


def _user(org_name=None):
    db = SessionLocal()
    org = Organization(name=org_name or f"mail-org-{uuid.uuid4().hex[:8]}")
    db.add(org)
    db.commit()
    name = f"sm_{uuid.uuid4().hex[:10]}"
    db.add(User(username=name, password_hash=hash_password(PASSWORD), role="admin", organization_id=org.id, is_active=True, is_super_admin=False))
    db.commit()
    org_id, org_name = org.id, org.name
    db.close()
    token = client.post("/login", data={"username": name, "password": PASSWORD}).json()["access_token"]
    return org_id, org_name, name, token


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _post(token, **overrides):
    body = {"category": "problem", "subject": "Cannot log in", "message": "I get an error when I log in.\nSecond line."}
    body.update(overrides)
    return client.post("/support-requests", json=body, headers=_h(token))


def _row(reference):
    db = SessionLocal()
    try:
        return db.query(SupportRequest).filter(SupportRequest.reference == reference).first()
    finally:
        db.close()


def test_without_configuration_the_request_is_stored_and_nothing_is_sent(monkeypatch):
    fake = FakePost()
    monkeypatch.setattr(support_mail.httpx, "post", fake)
    _o, _n, _u, token = _user()
    res = _post(token)
    assert res.status_code == 201
    row = _row(res.json()["reference"])
    assert row.notify_status == "skipped_no_config" and row.notified_at is None and row.notify_error is None
    assert fake.calls == []


def test_with_configuration_the_mail_is_sent_with_the_right_content(monkeypatch):
    _configure(monkeypatch)
    fake = FakePost()
    monkeypatch.setattr(support_mail.httpx, "post", fake)
    org_id, org_name, username, token = _user("Acme <b>Corp</b>")
    res = _post(token, subject="Cannot <i>log in</i>", message="<script>alert(1)</script> & \"quotes\"\nnext line")
    assert res.status_code == 201
    reference = res.json()["reference"]
    row = _row(reference)
    assert row.notify_status == "sent" and row.notified_at is not None and row.notify_error is None

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["url"] == "https://api.resend.com/emails" and call["timeout"] == 10.0
    assert call["headers"]["Authorization"] == f"Bearer {API_KEY}"
    payload = call["json"]
    assert payload["from"] == FROM and payload["to"] == [TO] and "reply_to" not in payload and "replyTo" not in payload
    assert payload["subject"] == f"[Valqeron support] {reference} {org_name}"
    for needle in (org_name, username, "problem", "Cannot <i>log in</i>", "<script>alert(1)</script>", reference):
        assert needle in payload["text"]  # plain text carries the raw values
    # HTML part: every piece of customer input is escaped, so there is no injectable markup
    assert "<script>" not in payload["html"] and "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;quotes&quot;<br>next line" in payload["html"]
    assert "<b>Corp</b>" not in payload["html"] and "&lt;b&gt;Corp&lt;/b&gt;" in payload["html"]
    assert "<i>log in</i>" not in payload["html"]
    assert "password" not in payload["text"].lower() and "token" not in payload["text"].lower()


def test_a_subject_line_cannot_contain_line_breaks(monkeypatch):
    _configure(monkeypatch)
    fake = FakePost()
    monkeypatch.setattr(support_mail.httpx, "post", fake)
    _o, _n, _u, token = _user("Evil\r\nBcc: attacker@example.com")
    _post(token)
    assert "\n" not in fake.calls[0]["json"]["subject"] and "\r" not in fake.calls[0]["json"]["subject"]


@pytest.mark.parametrize(
    "fake,expected_error",
    [
        (FakePost(status=401), "http_401"),
        (FakePost(status=500), "http_500"),
        (FakePost(exc=httpx.ReadTimeout("timed out")), "timeout"),
        (FakePost(exc=RuntimeError(f"boom {API_KEY}")), "error_RuntimeError"),
    ],
)
def test_a_mail_failure_or_timeout_never_fails_the_request(monkeypatch, fake, expected_error):
    _configure(monkeypatch)
    monkeypatch.setattr(support_mail.httpx, "post", fake)
    _o, _n, _u, token = _user()
    res = _post(token)
    assert res.status_code == 201
    row = _row(res.json()["reference"])
    assert row.notify_status == "failed" and row.notify_error == expected_error and row.notified_at is None
    assert API_KEY not in (row.notify_error or "")


# ---------------------------------------------------------------------------
# Recovery script
# ---------------------------------------------------------------------------

def _resend(dry_run):
    db = SessionLocal()
    try:
        return resend_script.resend_pending(db, dry_run)
    finally:
        db.close()


def test_resend_script_retries_failed_and_skipped_rows_only(monkeypatch):
    _o, _n, _u, token = _user()
    skipped = _post(token).json()["reference"]  # no configuration yet -> skipped_no_config
    _configure(monkeypatch)
    monkeypatch.setattr(support_mail.httpx, "post", FakePost(status=500))
    failed = _post(token).json()["reference"]
    monkeypatch.setattr(support_mail.httpx, "post", FakePost(status=200))
    sent = _post(token).json()["reference"]
    assert (_row(skipped).notify_status, _row(failed).notify_status, _row(sent).notify_status) == ("skipped_no_config", "failed", "sent")

    fake = FakePost(status=200)
    monkeypatch.setattr(support_mail.httpx, "post", fake)
    dry = _resend(dry_run=True)
    assert {skipped, failed} <= set(dry["candidates"]) and sent not in dry["candidates"] and fake.calls == []

    real = _resend(dry_run=False)
    assert real["failed"] == 0 and real["sent"] >= 2
    assert _row(skipped).notify_status == "sent" and _row(failed).notify_status == "sent"
    sent_row_time = _row(sent).notified_at
    assert _resend(dry_run=False)["candidates"] == []  # nothing left
    assert _row(sent).notified_at == sent_row_time  # already-sent rows are never touched


def test_resend_script_refuses_without_configuration():
    _o, _n, _u, token = _user()
    reference = _post(token).json()["reference"]
    assert reference in _resend(dry_run=True)["candidates"]  # a dry run works without a key
    with pytest.raises(SystemExit, match="Not configured"):
        _resend(dry_run=False)
    assert _row(reference).notify_status == "skipped_no_config"


# ---------------------------------------------------------------------------
# Secrecy: no key, message text, subject or address in logs, audit lines or Sentry events
# ---------------------------------------------------------------------------

class _Capture(Transport):
    def __init__(self):
        super().__init__()
        self.events = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)


def test_message_subject_key_and_address_stay_out_of_logs_audit_and_sentry(monkeypatch, caplog):
    _configure(monkeypatch)
    marker = uuid.uuid4().hex
    subject, message = f"SUBJECT-{marker}", f"MESSAGE-{marker}"
    transport = _Capture()
    assert init_sentry(dsn="https://publickey@o0.ingest.example.invalid/1", transport=transport)
    try:
        caplog.set_level("DEBUG")
        _o, _n, _u, token = _user()

        monkeypatch.setattr(support_mail.httpx, "post", FakePost(exc=RuntimeError(f"boom {API_KEY} {TO}")))
        assert _post(token, subject=subject, message=message).status_code == 201  # failure path of the mail

        def exploding_audit(*a, **k):
            raise RuntimeError("audit exploded")

        monkeypatch.setattr("app.api.support_requests.create_audit_log", exploding_audit)
        assert _post(token, subject=subject, message=message).status_code == 500  # unexpected error in the request itself
        sentry_sdk.flush()
        assert transport.events, "the error was not captured"

        db = SessionLocal()
        audit = json.dumps([[r.details, r.performed_by] for r in db.query(AuditLog).all()])
        db.close()
        haystack = json.dumps(transport.events) + caplog.text + audit
        for secret in (marker, API_KEY, TO, FROM):
            assert secret not in haystack
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init()
