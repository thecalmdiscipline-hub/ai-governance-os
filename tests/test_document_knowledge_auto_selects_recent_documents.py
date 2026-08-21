from app.workflows.services.runner import run_workflow
from tests.conftest import ensure_document


def test_document_knowledge_auto_selects_recent_documents():
    ensure_document(
        organization_id=1,
        uploaded_by_user_id=1,
        filename="auto_doc.txt",
        stored_name="auto_doc.txt",
        path="uploaded_documents/org_1/auto_doc.txt",
        content_type="text/plain",
        size=24,
    )

    result = run_workflow(
        "document_knowledge",
        {
            "input": {"question": "What documents are available?"},
            "context": {},
            "user": "dennis_admin",
        },
        user_id=1,
        org_id=1,
    )

    assert result["status"] == "ok"
    assert "answer" in result["output"]
    assert "auto_selected_documents" in result["output"]["answer"]
