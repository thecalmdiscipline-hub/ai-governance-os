from __future__ import annotations
from typing import Any, Dict, Optional, List
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.document import Document
from app.services.document_reader import read_text_document


def _to_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _load_recent_document_names(org_id: int, limit: int = 3) -> List[str]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Document)
            .filter(Document.organization_id == org_id)
            .order_by(Document.id.desc())
            .limit(limit)
            .all()
        )
        return [row.stored_name for row in rows]
    finally:
        db.close()


def run(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    input_data = payload.get("input", {}) or {}
    context = payload.get("context", {}) or {}
    user = payload.get("user")
    org_id = payload.get("org_id")

    question = (
        input_data.get("question")
        or input_data.get("query")
        or input_data.get("ping")
        or ""
    ).strip()

    explicit_doc_refs = _to_list(input_data.get("documents") or context.get("documents"))

    doc_refs: List[str] = explicit_doc_refs[:]
    auto_selected = False

    if not doc_refs and org_id is not None:
        doc_refs = _load_recent_document_names(int(org_id), limit=3)
        if doc_refs:
            auto_selected = True

    top_sources = doc_refs[:3]
    documents_used = []
    snippets = []

    if org_id is not None:
        for stored_name in doc_refs[:3]:
            text = read_text_document(int(org_id), stored_name)
            if text:
                snippet = text[:500].strip()
                documents_used.append(stored_name)
                snippets.append({
                    "document": stored_name,
                    "snippet": snippet,
                })

    if not question:
        summary = "no_question_provided"
        confidence = "low"
    elif snippets:
        joined_docs = ", ".join(documents_used)
        if auto_selected:
            summary = f"Question received: {question}. The system automatically used recent documents and found relevant text in: {joined_docs}."
        else:
            summary = f"Question received: {question}. Matched text found in: {joined_docs}."
        confidence = "medium"
    elif doc_refs:
        if auto_selected:
            summary = f"Question received: {question}. Recent documents were found automatically, but no readable text content was available."
        else:
            summary = f"Question received: {question}. Document selected, but no readable text content was available."
        confidence = "low"
    else:
        summary = f"Question received: {question}. No documents were available."
        confidence = "low"

    answer = {
        "summary": summary,
        "top_sources": top_sources,
        "confidence": confidence,
        "document_snippets": snippets,
        "auto_selected_documents": auto_selected,
    }

    return {
        "query_id": f"DK-{uuid4().hex[:10].upper()}",
        "answer": answer,
        "received": {
            "input": input_data,
            "context": context,
            "user": user,
            "org_id": org_id,
        },
        "user_id": user_id,
    }
