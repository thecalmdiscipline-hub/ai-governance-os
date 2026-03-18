def test_document_knowledge_router_exists():
    # smoke test: importing router should work
    from app.workflows.routers.document_knowledge import router  # noqa: F401
