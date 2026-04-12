from pathlib import Path

from app.workflows.implementations.document_knowledge import run


def test_document_knowledge_reads_uploaded_text():
    org_dir = Path("uploaded_documents/org_1")
    org_dir.mkdir(parents=True, exist_ok=True)

    stored_name = "test_knowledge_doc.txt"
    (org_dir / stored_name).write_text("This document contains pricing information for the bronze plan.", encoding="utf-8")

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
