from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user, has_valqeron_admin_powers, require_any_role, require_valqeron_admin
from app.core.ops_audit import log_ops_action
from app.models.document_scope_code import DocumentScopeCode
from app.models.document_usage import DocumentUsage
from app.models.user import User
from app.models.document import Document
from app.models.organization import Organization
from app.services.document_storage import save_uploaded_document, list_uploaded_documents
from app.services.document_reader import read_text_document, read_text_from_bytes
from app.services.document_scope import ScopeValidationError, scopes_for_upload, validate_scopes
from app.services.document_scope_rules import suggest_codes
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


# Statuses whose content only Valqeron may see (B5b; extended to 'uncoded' on 25 Nov 2026, so an old
# document that was never coded cannot leak either, with or without the archive migration).
RESTRICTED_STATUSES = ("archived", "uncoded")


def get_readable_document(db: Session, user: User, document_id: int) -> Document:
    """B5b: the document whose content (download or preview) this user may see.

    - 'coded': only documents of the user's own organization (unchanged).
    - 'archived': a Valqeron administrator (any organization); a user of the document's own
      organization only when that organization has archive_download_enabled, otherwise 403.
    - 'uncoded': a Valqeron administrator (any organization); a customer user never (403, also with
      archive_download_enabled on: an uncoded document is not an archive).
    A document of another organization is always a 404 for a customer user (no existence leak).
    """
    row = db.query(Document).filter(Document.id == document_id).first()
    valqeron = has_valqeron_admin_powers(user)
    own = row is not None and user.organization_id is not None and row.organization_id == int(user.organization_id)
    if row is None or (not own and not (row.scope_status in RESTRICTED_STATUSES and valqeron)):
        raise HTTPException(status_code=404, detail="Document not found")
    if valqeron or row.scope_status not in RESTRICTED_STATUSES:
        return row
    if row.scope_status == "archived":
        org = db.get(Organization, row.organization_id)
        if org and org.archive_download_enabled:
            return row
        raise HTTPException(
            status_code=403,
            detail={"error": "archive_download_disabled",
                    "message": "Archived documents can only be downloaded by Valqeron for this organization."},
        )
    raise HTTPException(
        status_code=403,
        detail={"error": "uncoded_download_disabled",
                "message": "Documents without scope codes can only be downloaded by Valqeron."},
    )


def _audit_valqeron_archive_access(db: Session, user: User, row: Document, what: str) -> None:
    # A Valqeron administrator reading an archived or uncoded document: HQ chain + customer chain.
    # Actions: archived_document_downloaded/previewed, uncoded_document_downloaded/previewed.
    if row.scope_status in RESTRICTED_STATUSES and has_valqeron_admin_powers(user):
        log_ops_action(db, user, f"{row.scope_status}_document_{what}", target_org_id=row.organization_id,
                       details=f"document {row.id}: {row.filename}")


# V6: admin and operator may upload; auditor (and any other role) may not.
UPLOAD_ROLES = ("admin", "operator")


def document_was_used(db: Session, document_id: int) -> bool:
    return db.query(DocumentUsage.id).filter(DocumentUsage.document_id == document_id).first() is not None


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(require_any_role(*UPLOAD_ROLES)),
    db: Session = Depends(get_db),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    content = await file.read()
    filename = file.filename or "uploaded_file"

    # V1/V5: validate the scope codes before anything is written to disk or the database.
    try:
        codes = scopes_for_upload(filename, read_text_from_bytes(filename, content))
    except ScopeValidationError as exc:
        raise HTTPException(status_code=422, detail={"error": exc.error, "message": exc.message})

    saved = save_uploaded_document(
        db=db,
        organization_id=int(current_user.organization_id),
        uploaded_by_user_id=current_user.id,
        filename=filename,
        content=content,
        content_type=file.content_type,
        scope_codes=codes,
    )

    # V30: a new upload with the same filename replaces the previous coded version(s) of this
    # organization; those are archived, never deleted.
    replaced = (
        db.query(Document)
        .filter(
            Document.organization_id == int(current_user.organization_id),
            Document.filename == saved["filename"],
            Document.scope_status == "coded",
            Document.id != int(saved["id"]),
        )
        .all()
    )
    replaced_ids = [row.id for row in replaced]
    for row in replaced:
        row.scope_status = "archived"
    if replaced:
        db.commit()

    create_audit_log(
        db=db,
        organization_id=int(current_user.organization_id),
        entity_type="document",
        entity_id=int(saved["id"]),
        action="uploaded",
        details=f'Document uploaded: filename={saved["filename"]}, stored_name={saved["stored_name"]}, size={saved["size"]}, scope_codes={",".join(saved["scope_codes"])}',
        performed_by=current_user.username,
    )

    for old_id in replaced_ids:
        create_audit_log(
            db=db,
            organization_id=int(current_user.organization_id),
            entity_type="document",
            entity_id=old_id,
            action="archived",
            details=f"Document archived: replaced by document {saved['id']}",
            performed_by=current_user.username,
        )

    return {
        "status": "ok",
        "organization_id": current_user.organization_id,
        "document": saved,
        "replaced_document_ids": replaced_ids,
    }


@router.post("/scope-suggestion")
async def scope_suggestion(
    file: UploadFile = File(...),
    current_user: User = Depends(require_any_role(*UPLOAD_ROLES)),
):
    """B7 (V2): suggested codes for a file the user is about to upload, from
    config/document_scope_rules.yaml. Stores nothing. The upload itself still needs the confirmed
    codes in the filename and on the first line (V5)."""
    content = await file.read()
    filename = file.filename or "uploaded_file"
    result = suggest_codes(filename, read_text_from_bytes(filename, content))
    return {"status": "ok", "filename": filename, **result}


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
            "scope_status": row.scope_status,
            "scope_codes": [c.code for c in row.scope_codes],
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

    row = get_readable_document(db, current_user, document_id)

    text = read_text_document(
        organization_id=int(row.organization_id),
        stored_name=row.stored_name,
    )

    if text is None:
        raise HTTPException(status_code=400, detail="Preview not available for this file type")
    _audit_valqeron_archive_access(db, current_user, row, "previewed")

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

    row = get_readable_document(db, current_user, document_id)

    file_path = Path(row.path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File missing on disk")
    _audit_valqeron_archive_access(db, current_user, row, "downloaded")

    return FileResponse(
        path=str(file_path),
        filename=row.filename,
        media_type=row.content_type or "application/octet-stream",
    )


# B7: only admin and operator may delete (or archive) a document; auditor and member get 403.
DELETE_ROLES = ("admin", "operator")


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(require_any_role(*DELETE_ROLES)),
    db: Session = Depends(get_db),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    row = get_org_document(db, int(current_user.organization_id), document_id)

    # V29: a document that was read by a workflow run is archived, never deleted.
    if document_was_used(db, row.id):
        already = row.scope_status == "archived"
        row.scope_status = "archived"
        db.commit()
        if not already:
            create_audit_log(
                db=db,
                organization_id=int(current_user.organization_id),
                entity_type="document",
                entity_id=row.id,
                action="archived",
                details=f"Document archived instead of deleted (used in a workflow run): filename={row.filename}",
                performed_by=current_user.username,
            )
        return {
            "status": "ok",
            "archived": {"id": row.id, "filename": row.filename, "stored_name": row.stored_name},
        }

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


class ScopeAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codes: List[str]


# Statuses from which a Valqeron administrator may assign codes. B7: 'archived' -> 'coded' restores an
# archived document. V7: codes are fixed once set, so an archived document that already has codes
# can only be restored with exactly those codes.
ASSIGNABLE_STATUSES = ("uncoded", "archived")


@router.patch("/{document_id}/scope")
def assign_document_scope(
    document_id: int,
    body: ScopeAssignment,
    current_user: User = Depends(require_valqeron_admin),
    db: Session = Depends(get_db),
):
    """B5/B3c/B7: only a Valqeron administrator (HQ, is_valqeron_admin, MFA) assigns codes to a
    document of any organization: an uncoded document, or an archived one (restore to 'coded')."""
    row = db.query(Document).filter(Document.id == document_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if row.scope_status not in ASSIGNABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail={"error": "scope_fixed", "message": f"Codes cannot be assigned to a document with status {row.scope_status}."},
        )
    codes = sorted({c.strip() for c in body.codes if c and c.strip()})
    try:
        validate_scopes(codes)
    except ScopeValidationError as exc:
        raise HTTPException(status_code=422, detail={"error": exc.error, "message": exc.message})

    existing = sorted(c.code for c in row.scope_codes)
    if existing and existing != codes:
        raise HTTPException(
            status_code=409,
            detail={"error": "scope_fixed", "message": f"This document already has codes {','.join(existing)}; they cannot be changed."},
        )

    # V30: only one active version per filename. Restoring an archived version while another version
    # with the same name is coded (normally the newer one that replaced it) would make two active.
    if row.scope_status == "archived":
        active = (
            db.query(Document.id)
            .filter(
                Document.organization_id == row.organization_id,
                Document.filename == row.filename,
                Document.scope_status == "coded",
                Document.id != row.id,
            )
            .first()
        )
        if active is not None:
            raise HTTPException(
                status_code=409,
                detail={"error": "active_version_exists",
                        "message": f"Document {active.id} with the same filename is active; archive it first."},
            )

    previous_status = row.scope_status
    if not existing:
        row.scope_codes = [DocumentScopeCode(code=c) for c in codes]
    row.scope_status = "coded"
    db.commit()

    log_ops_action(
        db,
        current_user,
        "document_scope_assigned",
        target_org_id=row.organization_id,
        details=f"document {row.id}: {previous_status} -> coded, codes={','.join(codes)}",
    )
    return {"status": "ok", "document": {"id": row.id, "scope_status": row.scope_status, "scope_codes": codes}}
