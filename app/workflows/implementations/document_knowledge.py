"""
Document Knowledge workflow — LLM implementation.

Input fields (all optional):
  question           : The question to answer based on available documents
  query              : Alias for question
  documents          : Specific document stored_names to use (list or string)

Output (always returned, even on LLM failure):
  status             : "ok" | "degraded"
  query_id           : Unique query ID (DK-xxxx)
  answer:
    summary          : AI-generated answer to the question
    top_sources      : Filenames of documents used in the answer
    confidence       : "high" | "medium" | "low"
    document_snippets: list[{document, snippet}]
    auto_selected_documents: bool
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.document import Document
from app.services.document_reader import read_text_document

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"
_MAX_CHARS_PER_DOC = 6000
_MAX_DOCS = 5

_SYSTEM_PROMPT = """You are a document knowledge assistant. Answer the user's question based solely on the provided documents.

Return a JSON object matching this exact schema — no prose, no markdown, only JSON:
{
  "answer": "<clear, direct answer based on the documents>",
  "confidence": <"high" | "medium" | "low">,
  "sources_used": ["<document filename 1>", "<document filename 2>", ...],
  "reasoning": "<brief explanation of how the answer was derived>"
}

Confidence guidance:
- "high"  : Documents contain clear, direct information that fully answers the question
- "medium": Documents contain partial or indirect information; answer is reasonable but incomplete
- "low"   : Documents contain little or no relevant information; answer cannot be determined

Only include filenames in "sources_used" that directly contributed to the answer.
If no answer can be found, state that clearly and set confidence to "low".
"""


def _to_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _load_documents(org_id: int, stored_names: Optional[List[str]], limit: int = _MAX_DOCS) -> List[Dict[str, str]]:
    db = SessionLocal()
    try:
        query = db.query(Document).filter(Document.organization_id == org_id)
        if stored_names:
            query = query.filter(Document.stored_name.in_(stored_names))
        else:
            query = query.order_by(Document.id.desc())
        rows = query.limit(limit).all()
        return [{"stored_name": row.stored_name, "filename": row.filename} for row in rows]
    finally:
        db.close()


def _build_user_message(question: str, doc_contents: List[Dict[str, str]]) -> str:
    parts = [f"Question: {question}", "", "Documents:"]
    for doc in doc_contents:
        parts.append(f"\n--- [{doc['filename']}] ---")
        parts.append(doc["text"][:_MAX_CHARS_PER_DOC])
    return "\n".join(parts)


def _parse_llm_response(content: str) -> Dict[str, Any]:
    data = json.loads(content)

    confidence = data.get("confidence", "low")
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"

    sources_used = data.get("sources_used", [])
    if not isinstance(sources_used, list):
        sources_used = []

    return {
        "answer": str(data.get("answer", "")),
        "confidence": confidence,
        "sources_used": [str(s) for s in sources_used],
        "reasoning": str(data.get("reasoning", "")),
    }


def _fallback_answer(reason: str, doc_snippets: List[Dict], top_sources: List[str], auto_selected: bool) -> Dict[str, Any]:
    return {
        "summary": f"Automated document analysis could not be completed: {reason}",
        "top_sources": top_sources,
        "confidence": "low",
        "document_snippets": doc_snippets,
        "auto_selected_documents": auto_selected,
    }


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
    query_id = f"DK-{uuid4().hex[:10].upper()}"

    received = {
        "input": input_data,
        "context": context,
        "user": user,
        "org_id": org_id,
    }

    # Load document metadata from DB
    auto_selected = False
    doc_meta: List[Dict[str, str]] = []

    if org_id is not None:
        doc_meta = _load_documents(int(org_id), stored_names=explicit_doc_refs or None)
        if not explicit_doc_refs and doc_meta:
            auto_selected = True

    # Read text content for each document
    doc_contents: List[Dict[str, str]] = []
    doc_snippets: List[Dict[str, str]] = []

    for meta in doc_meta:
        if org_id is None:
            break
        text = read_text_document(int(org_id), meta["stored_name"])
        if text:
            doc_contents.append({
                "stored_name": meta["stored_name"],
                "filename": meta["filename"],
                "text": text,
            })
            doc_snippets.append({
                "document": meta["filename"],
                "snippet": text[:500].strip(),
            })

    top_sources = [d["filename"] for d in doc_contents]

    # Guard: no question
    if not question:
        return {
            "status": "ok",
            "query_id": query_id,
            "answer": {
                "summary": "No question provided.",
                "top_sources": top_sources,
                "confidence": "low",
                "document_snippets": doc_snippets,
                "auto_selected_documents": auto_selected,
            },
            "received": received,
            "user_id": user_id,
        }

    # Guard: no documents with readable content
    if not doc_contents:
        return {
            "status": "ok",
            "query_id": query_id,
            "answer": {
                "summary": "No documents with readable content were available to answer the question.",
                "top_sources": [],
                "confidence": "low",
                "document_snippets": [],
                "auto_selected_documents": auto_selected,
            },
            "received": received,
            "user_id": user_id,
        }

    # Guard: no API key
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("document_knowledge: OPENAI_API_KEY not set — returning degraded response")
        return {
            "status": "degraded",
            "query_id": query_id,
            "answer": _fallback_answer("OPENAI_API_KEY not configured", doc_snippets, top_sources, auto_selected),
            "degraded_reason": "OPENAI_API_KEY not configured",
            "received": received,
            "user_id": user_id,
        }

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        user_message = _build_user_message(question, doc_contents)

        response = client.chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=1000,
        )

        raw_content = response.choices[0].message.content or ""
        parsed = _parse_llm_response(raw_content)

        # Keep only sources the LLM cited that we actually loaded
        valid_filenames = {d["filename"] for d in doc_contents}
        cited_sources = [s for s in parsed["sources_used"] if s in valid_filenames]
        if not cited_sources:
            cited_sources = top_sources[:3]

        logger.info(
            "document_knowledge: LLM call succeeded — confidence=%s sources=%s tokens=%s",
            parsed["confidence"],
            cited_sources,
            response.usage.total_tokens if response.usage else None,
        )

        return {
            "status": "ok",
            "query_id": query_id,
            "answer": {
                "summary": parsed["answer"],
                "top_sources": cited_sources,
                "confidence": parsed["confidence"],
                "document_snippets": doc_snippets,
                "auto_selected_documents": auto_selected,
                "reasoning": parsed["reasoning"],
            },
            "model": _MODEL,
            "tokens_used": response.usage.total_tokens if response.usage else None,
            "received": received,
            "user_id": user_id,
        }

    except openai.RateLimitError:
        logger.warning("document_knowledge: OpenAI rate limit reached")
        reason = "OpenAI rate limit reached — retry later"

    except openai.APIConnectionError as exc:
        logger.warning("document_knowledge: OpenAI connection error: %s", exc)
        reason = f"Could not reach OpenAI API: {exc}"

    except openai.APIStatusError as exc:
        logger.warning("document_knowledge: OpenAI API error %s: %s", exc.status_code, exc.message)
        reason = f"OpenAI API error {exc.status_code}"

    except json.JSONDecodeError as exc:
        logger.error("document_knowledge: Failed to parse LLM JSON response: %s", exc)
        reason = "LLM returned unparseable response"

    except Exception as exc:
        logger.error("document_knowledge: Unexpected error: %s", exc, exc_info=True)
        reason = f"Unexpected error: {type(exc).__name__}"

    return {
        "status": "degraded",
        "query_id": query_id,
        "answer": _fallback_answer(reason, doc_snippets, top_sources, auto_selected),
        "degraded_reason": reason,
        "received": received,
        "user_id": user_id,
    }
