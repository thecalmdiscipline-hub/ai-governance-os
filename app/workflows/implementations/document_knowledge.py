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
    auto_selected_documents: bool
  sources            : list[{filename, codes}] — documents read for this run (V22)

Documents: only those within this workflow's scope (kennis or gedeeld), via
app/services/document_access.py. Raw document text is never returned (V8: no snippets).

PII handling: the user message (the question plus the content of every
loaded document) is anonymised via app.core.pii_anonymizer before being
sent to OpenAI. The documents come from this organization's own Document
table (app/models/document.py), not from the requesting user personally
— but every member of an organization can already query any document in
that same organization (within this workflow's scope). Restoring a placeholder in the AI-generated answer
therefore exposes nothing a member of this organization could not
already see by the normal use of this same endpoint; the trust boundary
here, as everywhere else in this codebase, is organization membership,
not "the one user who happened to upload the file". answer.summary and
answer.reasoning are the LLM's own free text and are run through
pii_anonymizer.restore_placeholders() before being returned (see
app/core/pii_anonymizer.py and CLAUDE.md §6). confidence/sources_used/
top_sources/auto_selected_documents/sources are either enums or filtered
against known filenames — none of them pass through the LLM's own
free-text output, so none need restore.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.services.document_access import MAX_CHARS_PER_DOC, MAX_DOCS, read_scoped_documents, sources_for

from app.core import pii_anonymizer

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"
_MAX_CHARS_PER_DOC = MAX_CHARS_PER_DOC
_MAX_DOCS = MAX_DOCS

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


def _fallback_answer(reason: str, top_sources: List[str], auto_selected: bool) -> Dict[str, Any]:
    return {
        "summary": f"Automated document analysis could not be completed: {reason}",
        "top_sources": top_sources,
        "confidence": "low",
        "auto_selected_documents": auto_selected,
    }


def run(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    input_data = payload.get("input", {}) or {}
    context = payload.get("context", {}) or {}

    # org_id is always injected by the workflow runner from current_user.organization_id
    # (see app/workflows/services/runner.py). It is never read from user-controlled input,
    # preventing cross-tenant document access.
    org_id = payload.get("org_id")

    question = (
        input_data.get("question")
        or input_data.get("query")
        or input_data.get("ping")
        or ""
    ).strip()

    explicit_doc_refs = _to_list(input_data.get("documents") or context.get("documents"))
    query_id = f"DK-{uuid4().hex[:10].upper()}"

    # Fase B3: only documents within this workflow's scope (app/services/document_access.py),
    # with or without an explicit selection.
    doc_contents = read_scoped_documents(org_id, "document_knowledge", stored_names=explicit_doc_refs or None)
    auto_selected = bool(doc_contents) and not explicit_doc_refs
    sources = sources_for(doc_contents)

    top_sources = [d["filename"] for d in doc_contents]

    # Guard: no question
    if not question:
        return {
            "status": "ok",
            "query_id": query_id,
            "sources": sources,
            "answer": {
                "summary": "No question provided.",
                "top_sources": top_sources,
                "confidence": "low",
                "auto_selected_documents": auto_selected,
            },

            "user_id": user_id,
        }

    # Guard: no documents with readable content
    if not doc_contents:
        return {
            "status": "ok",
            "query_id": query_id,
            "sources": sources,
            "answer": {
                "summary": "No documents with readable content were available to answer the question.",
                "top_sources": [],
                "confidence": "low",
                "auto_selected_documents": auto_selected,
            },

            "user_id": user_id,
        }

    # Guard: no API key
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("document_knowledge: OPENAI_API_KEY not set — returning degraded response")
        return {
            "status": "degraded",
            "query_id": query_id,
            "sources": sources,
            "answer": _fallback_answer("OPENAI_API_KEY not configured", top_sources, auto_selected),
            "degraded_reason": "OPENAI_API_KEY not configured",

            "user_id": user_id,
        }

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        user_message = _build_user_message(question, doc_contents)
        user_message, pii_mapping = pii_anonymizer.anonymize_text_with_mapping(
            user_message, workflow="document_knowledge"
        )

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
        parsed["answer"] = pii_anonymizer.restore_placeholders(parsed["answer"], pii_mapping)
        parsed["reasoning"] = pii_anonymizer.restore_placeholders(parsed["reasoning"], pii_mapping)

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
            "sources": sources,
            "answer": {
                "summary": parsed["answer"],
                "top_sources": cited_sources,
                "confidence": parsed["confidence"],
                "auto_selected_documents": auto_selected,
                "reasoning": parsed["reasoning"],
            },
            "model": _MODEL,
            "tokens_used": response.usage.total_tokens if response.usage else None,

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

    except pii_anonymizer.PIIAnonymizerUnavailable as exc:
        logger.error("document_knowledge: PII-anonimisering mislukt — LLM-call geblokkeerd: %s", exc)
        reason = str(exc)

    except Exception as exc:
        logger.error("document_knowledge: Unexpected error: %s", exc, exc_info=True)
        reason = f"Unexpected error: {type(exc).__name__}"

    return {
        "status": "degraded",
        "query_id": query_id,
        "sources": sources,
        "answer": _fallback_answer(reason, top_sources, auto_selected),
        "degraded_reason": reason,
        "user_id": user_id,
    }
