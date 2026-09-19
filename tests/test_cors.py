"""CORS regression test for PUT (Batch A, deel 1).

app/api/governance.py has PUT /corrective-actions/{action_id}/status, but
app/core/middleware.py's CORSMiddleware did not list "PUT" in
allow_methods — a browser preflight (OPTIONS) for that endpoint would
fail, blocking the portal's corrective-action status update entirely.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_options_preflight_for_put_corrective_action_status_allows_put():
    res = client.options(
        "/corrective-actions/1/status",
        headers={
            "Origin": "https://app.valqeron.com",
            "Access-Control-Request-Method": "PUT",
        },
    )
    assert res.status_code == 200
    allowed = res.headers.get("access-control-allow-methods", "")
    assert "PUT" in allowed


def test_options_preflight_from_disallowed_origin_gets_no_cors_headers():
    res = client.options(
        "/corrective-actions/1/status",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "PUT",
        },
    )
    assert "access-control-allow-origin" not in res.headers
