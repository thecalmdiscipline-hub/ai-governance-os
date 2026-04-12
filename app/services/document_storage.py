from pathlib import Path
from typing import List, Dict, Optional
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.document import Document

BASE_DIR = Path("uploaded_documents")


def ensure_org_dir(organization_id: int) -> Path:
    org_dir = BASE_DIR / f"org_{organization_id}"
    org_dir.mkdir(parents=True, exist_ok=True)
    return org_dir


def save_uploaded_document(
    db: Session,
    organization_id: int,
    uploaded_by_user_id: Optional[int],
    filename: str,
    content: bytes,
    content_type: Optional[str] = None,
) -> Dict:
    org_dir = ensure_org_dir(organization_id)
    safe_name = filename.replace("/", "_").replace("\\", "_")
    stored_name = f"{uuid4().hex}_{safe_name}"
    file_path = org_dir / stored_name
    file_path.write_bytes(content)

    stat = file_path.stat()

    doc = Document(
        organization_id=organization_id,
        uploaded_by_user_id=uploaded_by_user_id,
        filename=safe_name,
        stored_name=stored_name,
        path=str(file_path),
        content_type=content_type,
        size=stat.st_size,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {
        "id": doc.id,
        "filename": doc.filename,
        "stored_name": doc.stored_name,
        "path": doc.path,
        "content_type": doc.content_type,
        "size": doc.size,
        "uploaded_at": doc.created_at.isoformat(),
    }


def list_uploaded_documents(db: Session, organization_id: int) -> List[Dict]:
    rows = (
        db.query(Document)
        .filter(Document.organization_id == organization_id)
        .order_by(Document.id.desc())
        .all()
    )

    items = []
    for row in rows:
        items.append({
            "id": row.id,
            "filename": row.filename,
            "stored_name": row.stored_name,
            "path": row.path,
            "content_type": row.content_type,
            "size": row.size,
            "uploaded_at": row.created_at.isoformat() if row.created_at else "",
        })

    return items
