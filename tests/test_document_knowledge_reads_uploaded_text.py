from pathlib import Path

from app.workflows.implementations.document_knowledge import run
from tests.conftest import ensure_document, mock_openai_response


def test_document_knowledge_reads_uploaded_text(monkeypatch):
    org_dir = Path("uploaded_documents/org_1")
    org_dir.mkdir(parents=True, exist_ok=True)

    stored_name = "test_knowledge_doc.txt"
    (org_dir / stored_name).write_text("This document contains pricing information for the bronze plan.", encoding="utf-8")

    # _load_documents() in document_knowledge.py matches on the `documents`
    # DB table by stored_name — writing the file to disk alone is not
    # enough. Without this row the workflow can never find the document, so
    # it always hits the "no documents with readable content" guard and
    # returns confidence="low" deterministically, regardless of the file's
    # actual content. That (not LLM flakiness) was the original bug.
    ensure_document(
        organization_id=1,
        uploaded_by_user_id=1,
        filename=stored_name,
        stored_name=stored_name,
        path=str(org_dir / stored_name),
        content_type="text/plain",
        size=len("This document contains pricing information for the bronze plan."),
    )

    mock_openai_response(monkeypatch, {
        "answer": "The document contains pricing information for the bronze plan.",
        "confidence": "high",
        "sources_used": [stored_name],
        "reasoning": "The document explicitly states it contains bronze plan pricing information.",
    })

    result = run(
        payload={
            "input": {
                "question": "What does the document contain?",
                "documents": [stored_name],
            },
            "context": {},
            "user": "dennis_admin",
            "org_id": 1,
        },
        user_id=1,
    )

    assert result["answer"]["confidence"] in {"medium", "high"}
    assert result["answer"]["top_sources"] == [stored_name]
    assert len(result["answer"]["document_snippets"]) == 1
    assert "pricing information" in result["answer"]["document_snippets"][0]["snippet"]
