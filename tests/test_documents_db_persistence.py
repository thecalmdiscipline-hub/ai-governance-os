from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.document import Document

client = TestClient(app)


def test_document_upload_persists_db_record():
    login = client.post(
        "/login",
        data={"username": "dennis_admin", "password": "Admin123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    upload = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("db_document.txt", BytesIO(b"db persistence"), "text/plain")},
    )

    assert upload.status_code == 200
    upload_data = upload.json()
    stored_name = upload_data["document"]["stored_name"]

    db = SessionLocal()
    row = db.query(Document).filter(Document.stored_name == stored_name).first()
    db.close()

    assert row is not None
    assert row.filename == "db_document.txt"
    assert row.organization_id == 1
    assert row.uploaded_by_user_id == 1
