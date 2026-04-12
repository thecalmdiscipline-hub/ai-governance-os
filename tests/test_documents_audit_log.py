from io import BytesIO

from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.security import SECRET_KEY, ALGORITHM
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog

client = TestClient(app)


def make_token() -> str:
    payload = {
        "sub": "dennis_admin",
        "role": "admin",
        "org_id": 1,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def test_document_upload_and_delete_create_audit_logs():
    token = make_token()

    upload = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("audit_doc.txt", BytesIO(b"audit content"), "text/plain")},
    )
    assert upload.status_code == 200
    doc_id = upload.json()["document"]["id"]

    delete = client.delete(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete.status_code == 200

    db = SessionLocal()
    logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == 1,
            AuditLog.entity_type == "document",
        )
        .order_by(AuditLog.id.desc())
        .limit(10)
        .all()
    )
    db.close()

    actions = [log.action for log in logs]
    assert "uploaded" in actions
    assert "deleted" in actions
