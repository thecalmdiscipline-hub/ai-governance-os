from __future__ import annotations
from typing import Any, Dict, Optional, List
from uuid import uuid4

from app.services.document_reader import read_text_document


def _to_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


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

    doc_refs = _to_list(input_data.get("documents") or context.get("documents"))
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
        summary = f"Question received: {question}. Matched text found in: {joined_docs}."
        confidence = "medium"
    elif doc_refs:
        summary = f"Question received: {question}. Document selected, but no readable text content was available."
        confidence = "low"
    else:
        summary = f"Question received: {question}. No documents were provided."
        confidence = "low"

    answer = {
        "summary": summary,
        "top_sources": top_sources,
        "confidence": confidence,
        "document_snippets": snippets,
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
