from __future__ import annotations
from typing import Any, Dict, Optional
from uuid import uuid4

def run(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    input_data = payload.get("input", {})
    context = payload.get("context", {})
    user = payload.get("user")

    question = input_data.get("question") or input_data.get("query") or input_data.get("ping") or ""
    doc_refs = input_data.get("documents") or context.get("documents") or []

    if isinstance(doc_refs, str):
        doc_refs = [doc_refs]

    answer = {
        "summary": "stub_search_ok" if question else "no_question_provided",
        "top_sources": doc_refs[:3],
        "confidence": "low" if not doc_refs else "medium",
    }

    return {
        "query_id": f"DK-{uuid4().hex[:10].upper()}",
        "answer": answer,
        "received": {
            "input": input_data,
            "context": context,
            "user": user,
        },
        "user_id": user_id,
    }
