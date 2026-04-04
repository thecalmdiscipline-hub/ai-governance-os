from app.workflows.implementations.document_knowledge import run

def test_document_knowledge_returns_query_id_and_answer():
    out = run(
        payload={"input": {"question": "Where is policy X?", "documents": ["doc_a.pdf", "doc_b.pdf"]}, "context": {}, "user": "dennis_admin"},
        user_id=1,
    )
    assert out["query_id"].startswith("DK-")
    assert "answer" in out
    assert out["answer"]["summary"] in ("stub_search_ok", "no_question_provided")
    assert out["user_id"] == 1
