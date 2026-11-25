from pathlib import Path
from typing import Dict, Iterable, List, Optional
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_scope_code import DocumentScopeCode

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
    scope_codes: Optional[Iterable[str]] = None,
) -> Dict:
    # scope_codes must already be validated by the caller (app/services/document_scope.py).
    # With codes the document is stored as 'coded'; without (e.g. the Microsoft sync) it stays
    # 'uncoded' and no workflow reads it.
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
    codes = sorted(set(scope_codes or []))
    if codes:
        doc.scope_status = "coded"
        doc.scope_codes = [DocumentScopeCode(code=c) for c in codes]
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
        "scope_status": doc.scope_status,
        "scope_codes": [row.code for row in doc.scope_codes],
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
            "scope_status": row.scope_status,
            "scope_codes": [c.code for c in row.scope_codes],
        })

    return items
