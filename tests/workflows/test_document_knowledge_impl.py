from app.workflows.implementations.document_knowledge import run


def test_document_knowledge_returns_query_id_and_answer():
    result = run(
        payload={
            "input": {
                "question": "Where is policy X?",
                "documents": ["policy_x.txt"],
            },
            "context": {},
            "user": "tester",
            "org_id": 1,
        },
        user_id=1,
    )

    assert result["query_id"].startswith("DK-")
    assert "answer" in result
    assert result["answer"]["top_sources"] == ["policy_x.txt"]
    assert result["answer"]["confidence"] in {"low", "medium", "high"}
    assert "Question received:" in result["answer"]["summary"]
