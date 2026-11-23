"""Which documents a workflow may read (Fase B3, V3/V4/V18/V20).

This is the ONLY place that decides document access for a workflow. No workflow builds its own
document query: they call load_scoped_documents()/read_scoped_documents() from here.
"""
from typing import Dict, Iterable, List, Optional, Set

from app.db.session import SessionLocal
from app.models.document import Document
from app.models.document_scope_code import DocumentScopeCode
from app.services.document_reader import read_text_document
from app.services.document_scope_codes import EXCLUSIVE_CODES, SHARED_CODE, WORKFLOW_SCOPE_CODES

MAX_DOCS = 5               # V20
MAX_CHARS_PER_DOC = 6000   # V20


def workflow_scope_code(workflow_key: str) -> str:
    try:
        return WORKFLOW_SCOPE_CODES[workflow_key]
    except KeyError:
        raise ValueError(f"Workflow has no scope code: {workflow_key}")


def allowed_document_codes(workflow_key: str) -> Set[str]:
    """V3: a workflow reads documents with its own code or the shared code."""
    return {workflow_scope_code(workflow_key), SHARED_CODE}


def may_read(workflow_key: str, document_codes: Iterable[str]) -> bool:
    """True if a document with `document_codes` may be read by `workflow_key`.

    - at least one code overlaps with allowed_document_codes (V3/V4);
    - an exclusive code (hr, V18/B3a) is read only by its own workflow, and only when the
      document carries no other code (an upload like that is refused anyway; this is the
      defence in depth for rows that would ever get there another way).
    """
    codes = set(document_codes)
    if not codes:
        return False
    own = workflow_scope_code(workflow_key)
    exclusive = codes & EXCLUSIVE_CODES
    if exclusive:
        return exclusive == {own} and codes == {own}
    return bool(codes & allowed_document_codes(workflow_key))


def load_scoped_documents(
    org_id: int,
    workflow_key: str,
    stored_names: Optional[List[str]] = None,
    limit: int = MAX_DOCS,
) -> List[Dict]:
    """Metadata of the documents `workflow_key` may read in organization `org_id`, newest first.

    Only scope_status == 'coded'. An explicit selection (`stored_names`) is narrowed by the same
    filter: selecting a document outside the workflow's scope never makes it readable.
    """
    allowed = allowed_document_codes(workflow_key)
    db = SessionLocal()
    try:
        query = (
            db.query(Document)
            .join(DocumentScopeCode, DocumentScopeCode.document_id == Document.id)
            .filter(
                Document.organization_id == org_id,
                Document.scope_status == "coded",
                DocumentScopeCode.code.in_(allowed),
            )
            .distinct()
        )
        if stored_names:
            query = query.filter(Document.stored_name.in_(stored_names))
        rows = query.order_by(Document.id.desc()).all()

        result: List[Dict] = []
        for row in rows:
            codes = sorted(c.code for c in row.scope_codes)
            if not may_read(workflow_key, codes):
                continue
            result.append({
                "id": row.id,
                "stored_name": row.stored_name,
                "filename": row.filename,
                "codes": codes,
            })
            if len(result) >= limit:
                break
        return result
    finally:
        db.close()


def read_scoped_documents(
    org_id: Optional[int],
    workflow_key: str,
    stored_names: Optional[List[str]] = None,
    limit: int = MAX_DOCS,
) -> List[Dict]:
    """Like load_scoped_documents, plus the text (max MAX_CHARS_PER_DOC); unreadable files skipped."""
    if org_id is None:
        return []
    docs: List[Dict] = []
    for meta in load_scoped_documents(int(org_id), workflow_key, stored_names=stored_names, limit=limit):
        text = read_text_document(int(org_id), meta["stored_name"])
        if text:
            docs.append({**meta, "text": text[:MAX_CHARS_PER_DOC]})
    return docs


def format_documents_for_prompt(docs: List[Dict]) -> str:
    parts = []
    for doc in docs:
        parts.append(f"\n--- [{doc['filename']}] ---")
        parts.append(doc["text"][:MAX_CHARS_PER_DOC])
    return "\n".join(parts)
