"""Sentry (Batch D): errors only, and no customer content leaves the process.

No network: events go to an in-memory transport after before_send has run, so
what is asserted here is exactly what would be sent to Sentry.
"""
import json

import pytest
import sentry_sdk
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from app.core import observability
from app.core.observability import before_send, init_sentry, scrub_text
from app.main import app

PERSON_EMAIL = "test.person@example.com"
FAKE_DSN = "https://publickey@o0.ingest.example.invalid/1"


class CaptureTransport(Transport):
    def __init__(self):
        super().__init__()
        self.events = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)


@pytest.fixture
def transport(monkeypatch):
    """Sentry initialised through init_sentry() with an in-memory transport."""
    t = CaptureTransport()
    assert init_sentry(dsn=FAKE_DSN, transport=t) is True
    yield t
    sentry_sdk.get_client().close()
    sentry_sdk.init()  # back to disabled so other tests are unaffected


@pytest.fixture
def boom_routes():
    router = APIRouter()

    @router.post("/__test_boom_body__")
    async def boom_body(payload: dict):
        customer_text = payload["text"]  # a local variable holding customer text
        raise RuntimeError(f"processing failed for {customer_text}")

    @router.post("/__test_boom_plain__")
    async def boom_plain(payload: dict):
        customer_text = payload["text"]  # noqa: F841 - must not be sent as a frame variable
        raise ValueError("boom")

    before = list(app.router.routes)
    app.include_router(router)
    added = [r for r in app.router.routes if r not in before]
    yield
    for r in added:
        app.router.routes.remove(r)


def test_not_active_without_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    calls = []
    monkeypatch.setattr(sentry_sdk, "init", lambda *a, **k: calls.append((a, k)))
    assert init_sentry() is False
    assert calls == [], "the SDK must not even be initialised without a DSN"


def test_blank_dsn_is_inactive(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "   ")
    calls = []
    monkeypatch.setattr(sentry_sdk, "init", lambda *a, **k: calls.append((a, k)))
    assert init_sentry() is False
    assert calls == []


def test_error_event_contains_no_customer_text(transport, boom_routes):
    client = TestClient(app, raise_server_exceptions=False)
    res = client.post(
        "/__test_boom_body__?email=" + PERSON_EMAIL,
        json={"text": f"Contact {PERSON_EMAIL} or call 06-12345678"},
        headers={"Authorization": "Bearer abc.def.ghi", "Cookie": "session=secret123"},
    )
    assert res.status_code == 500
    assert transport.events, "the error was not captured"

    blob = json.dumps(transport.events)
    assert PERSON_EMAIL not in blob
    assert "test.person" not in blob
    assert "06-12345678" not in blob
    assert "abc.def.ghi" not in blob
    assert "secret123" not in blob
    event = transport.events[0]
    assert "data" not in event.get("request", {}) and "query_string" not in event.get("request", {})
    # what remains is technical: exception type, file/function names, and a masked, truncated message
    values = event["exception"]["values"]
    assert "[email]" in values[-1]["value"] and "[digits]" in values[-1]["value"]
    assert values[-1]["type"] == "RuntimeError"
    assert any("boom_body" in (f.get("function") or "") for f in values[-1]["stacktrace"]["frames"])


def test_frame_variables_are_not_sent(transport, boom_routes):
    client = TestClient(app, raise_server_exceptions=False)
    client.post("/__test_boom_plain__", json={"text": "customer-secret-text-xyz"})
    blob = json.dumps(transport.events)
    assert "customer-secret-text-xyz" not in blob
    for exc in transport.events[0]["exception"]["values"]:
        for frame in exc["stacktrace"]["frames"]:
            assert "vars" not in frame


def test_global_handler_still_returns_existing_500_and_is_captured_once(transport, boom_routes):
    client = TestClient(app, raise_server_exceptions=False)
    res = client.post("/__test_boom_plain__", json={"text": "x"})
    assert res.status_code == 500
    assert res.json() == {
        "error": "internal_server_error",
        "message": "An unexpected error occurred.",
    }
    sentry_sdk.flush()
    assert len(transport.events) == 1, "exactly one event per failing request"
    assert transport.events[0]["exception"]["values"][-1]["type"] == "ValueError"


def test_before_send_removes_cookies_authorization_query_string_and_user():
    event = {
        "request": {
            "method": "POST",
            "url": "https://api.valqeron.com/documents?email=test.person@example.com",
            "query_string": "email=test.person@example.com",
            "cookies": {"session": "secret123"},
            "headers": {"Authorization": "Bearer abc", "Cookie": "session=secret123"},
            "data": {"text": "customer text"},
        },
        "user": {"email": PERSON_EMAIL, "ip_address": "203.0.113.9"},
        "extra": {"prompt": "customer text"},
        "breadcrumbs": {"values": [{"message": "SELECT ... 'customer text'"}]},
        "contexts": {"runtime": {"name": "CPython"}, "os": {"name": "Linux"}, "custom": {"k": "customer text"}},
        "exception": {
            "values": [
                {
                    "type": "RuntimeError",
                    "value": f"failed for {PERSON_EMAIL} on IBAN NL91ABNA0417164300 " + "x" * 500,
                    "stacktrace": {"frames": [{"function": "f", "filename": "a.py", "vars": {"t": "customer text"}}]},
                }
            ]
        },
    }
    out = before_send(event)
    blob = json.dumps(out)
    assert out["request"] == {"method": "POST", "url": "https://api.valqeron.com/documents"}
    assert "user" not in out and "extra" not in out and "breadcrumbs" not in out
    assert set(out["contexts"]) == {"runtime", "os"}
    assert PERSON_EMAIL not in blob
    assert "customer text" not in blob
    assert "secret123" not in blob
    assert "0417164300" not in blob
    value = out["exception"]["values"][0]["value"]
    assert len(value) <= 200
    assert "[email]" in value


def test_before_send_never_raises_and_drops_broken_events():
    assert before_send({"exception": {"values": [{"stacktrace": {"frames": None, "x": 1}, "value": 5}]}}) is not None
    assert before_send({"exception": 5}) is None  # broken shape: dropped, not raised


def test_scrub_text_masks_email_and_long_digit_runs_and_truncates():
    assert scrub_text("mail a.b+c@example.co.uk now") == "mail [email] now"
    assert scrub_text("bel 06-12345678") == "bel [digits]"
    assert scrub_text("code 12345") == "code 12345"  # short numbers stay
    assert len(scrub_text("y" * 1000)) == 200
    assert scrub_text(None) is None


def test_health_reports_status_ok_and_build_sha():
    client = TestClient(app)
    res = client.get("/health")
    body = res.json()
    assert body["status"] == "ok"
    assert "build_sha" in body
    assert body["build_sha"] == observability.get_build_sha()


def test_build_sha_reads_file_and_falls_back_to_unknown(tmp_path, monkeypatch):
    observability.get_build_sha.cache_clear()
    try:
        f = tmp_path / "BUILD_SHA"
        monkeypatch.setattr(observability, "_BUILD_SHA_FILE", f)
        assert observability.get_build_sha() == "unknown"  # missing file

        observability.get_build_sha.cache_clear()
        f.write_text("abc1234\n")
        assert observability.get_build_sha() == "abc1234"

        observability.get_build_sha.cache_clear()
        f.write_text("not a sha; rm -rf /")
        assert observability.get_build_sha() == "unknown"
    finally:
        observability.get_build_sha.cache_clear()
