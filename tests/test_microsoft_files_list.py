"""POST /microsoft/files/list used `db` without having it as a parameter (NameError -> 500) whenever the
request body carried no access_token. It now answers 409 microsoft_not_connected when the organization has
no stored MicrosoftToken (which is always the case today: nothing stores one)."""
from datetime import datetime

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.microsoft_token import MicrosoftToken
from app.models.user import User

client = TestClient(app, raise_server_exceptions=False)


def _token() -> str:
    # demo account seeded by tests/conftest.py (organization 1), same credentials as test_microsoft_routes.py
    res = client.post("/login", data={"username": "dennis_admin", "password": "Admin123!"})
    assert res.status_code == 200
    return res.json()["access_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_files_list_without_connection_is_409_not_500():
    res = client.post("/microsoft/files/list", json={}, headers=_h(_token()))
    assert res.status_code == 409
    assert res.json() == {"error": "microsoft_not_connected"}


def test_files_list_with_no_body_at_all_is_also_409():
    res = client.post("/microsoft/files/list", headers=_h(_token()))
    assert res.status_code == 409
    assert res.json() == {"error": "microsoft_not_connected"}


def test_files_list_requires_authentication():
    assert client.post("/microsoft/files/list", json={}).status_code == 401


def test_files_list_uses_only_the_own_organizations_stored_token(monkeypatch):
    """A stored token of another organization must not be used: still 409 for this organization."""
    from app.api import microsoft as ms

    db = SessionLocal()
    other_org = 2  # the caller (dennis_admin) belongs to organization 1
    other_user = db.query(User).filter(User.organization_id == other_org).first()
    row = MicrosoftToken(
        organization_id=other_org,
        user_id=other_user.id,
        access_token="other-org-token",
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    row_id = row.id
    db.close()

    called = []
    monkeypatch.setattr(ms, "MicrosoftGraphClient", lambda tok: called.append(tok) or (_ for _ in ()).throw(AssertionError("Graph must not be called")))
    try:
        res = client.post("/microsoft/files/list", json={}, headers=_h(_token()))
        assert res.status_code == 409
        assert called == []
    finally:
        db = SessionLocal()
        db.query(MicrosoftToken).filter(MicrosoftToken.id == row_id).delete()
        db.commit()
        db.close()
