from pathlib import Path

from app.workflows.implementations.document_knowledge import run
from tests.conftest import ensure_document, mock_openai_response

# This test previously asserted `top_sources == ["policy_x.txt"]` and
# `"Question received:" in summary` without ever creating "policy_x.txt" on
# disk or in the DB, and that exact "Question received:" string does not
# appear anywhere in the current implementation
# (app/workflows/implementations/document_knowledge.py). Both assertions
# were stale — written against an earlier version of this workflow, before
# it was rewritten to call a real LLM (see the docstring: top_sources means
# "documents actually used to answer", not "documents requested"; a
# nonexistent document correctly yields an empty top_sources). Fixed by
# actually creating the document and asserting on real, current behaviour.


def test_document_knowledge_returns_query_id_and_answer(monkeypatch):
    org_dir = Path("uploaded_documents/org_1")
    org_dir.mkdir(parents=True, exist_ok=True)

    stored_name = "policy_x.txt"
    content = "Policy X requires all AI systems to undergo a risk assessment before production approval."
    (org_dir / stored_name).write_text(content, encoding="utf-8")

    ensure_document(
        organization_id=1,
        uploaded_by_user_id=1,
        filename=stored_name,
        stored_name=stored_name,
        path=str(org_dir / stored_name),
        content_type="text/plain",
        size=len(content),
    )

    mock_openai_response(monkeypatch, {
        "answer": "Policy X requires a risk assessment before production approval.",
        "confidence": "high",
        "sources_used": [stored_name],
        "reasoning": "The document directly states the risk assessment requirement.",
    })

    result = run(
        payload={
            "input": {
                "question": "Where is policy X?",
                "documents": [stored_name],
            },
            "context": {},
            "user": "tester",
            "org_id": 1,
        },
        user_id=1,
    )

    assert result["query_id"].startswith("DK-")
    assert "answer" in result
    assert result["answer"]["top_sources"] == [stored_name]
    assert result["answer"]["confidence"] in {"low", "medium", "high"}
    assert "risk assessment" in result["answer"]["summary"]
