from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.document import Document
from app.services.document_storage import save_uploaded_document, list_uploaded_documents
from app.services.document_reader import read_text_document
from app.core.audit import create_audit_log

router = APIRouter(prefix="/documents", tags=["Documents"])


def get_org_document(db: Session, organization_id: int, document_id: int) -> Document:
    row = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return row


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    content = await file.read()
    saved = save_uploaded_document(
        db=db,
        organization_id=int(current_user.organization_id),
        uploaded_by_user_id=current_user.id,
        filename=file.filename or "uploaded_file",
        content=content,
        content_type=file.content_type,
    )

    create_audit_log(
        db=db,
        organization_id=int(current_user.organization_id),
        entity_type="document",
        entity_id=int(saved["id"]),
        action="uploaded",
        details=f'Document uploaded: filename={saved["filename"]}, stored_name={saved["stored_name"]}, size={saved["size"]}',
        performed_by=current_user.username,
    )

    return {
        "status": "ok",
        "organization_id": current_user.organization_id,
        "document": saved,
    }


@router.get("")
def get_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    items = list_uploaded_documents(db=db, organization_id=int(current_user.organization_id))

    return {
        "status": "ok",
        "organization_id": current_user.organization_id,
        "total": len(items),
        "items": items,
    }


@router.get("/{document_id}")
def get_document_detail(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    row = get_org_document(db, int(current_user.organization_id), document_id)

    return {
        "status": "ok",
        "document": {
            "id": row.id,
            "organization_id": row.organization_id,
            "uploaded_by_user_id": row.uploaded_by_user_id,
            "filename": row.filename,
            "stored_name": row.stored_name,
            "path": row.path,
            "content_type": row.content_type,
            "size": row.size,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        },
    }


@router.get("/{document_id}/preview")
def preview_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    row = get_org_document(db, int(current_user.organization_id), document_id)

    text = read_text_document(
        organization_id=int(current_user.organization_id),
        stored_name=row.stored_name,
    )

    if text is None:
        raise HTTPException(status_code=400, detail="Preview not available for this file type")

    return {
        "status": "ok",
        "document": {
            "id": row.id,
            "filename": row.filename,
            "stored_name": row.stored_name,
        },
        "preview": {
            "text": text[:4000],
            "length": len(text),
            "truncated": len(text) > 4000,
        },
    }


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    row = get_org_document(db, int(current_user.organization_id), document_id)

    file_path = Path(row.path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File missing on disk")

    return FileResponse(
        path=str(file_path),
        filename=row.filename,
        media_type=row.content_type or "application/octet-stream",
    )


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    row = get_org_document(db, int(current_user.organization_id), document_id)

    deleted = {
        "id": row.id,
        "filename": row.filename,
        "stored_name": row.stored_name,
    }

    file_path = Path(row.path)
    if file_path.exists() and file_path.is_file():
        file_path.unlink()

    db.delete(row)
    db.commit()

    create_audit_log(
        db=db,
        organization_id=int(current_user.organization_id),
        entity_type="document",
        entity_id=int(deleted["id"]),
        action="deleted",
        details=f'Document deleted: filename={deleted["filename"]}, stored_name={deleted["stored_name"]}',
        performed_by=current_user.username,
    )

    return {
        "status": "ok",
        "deleted": deleted,
    }
