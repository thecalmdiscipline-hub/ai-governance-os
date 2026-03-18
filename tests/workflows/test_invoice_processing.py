def test_invoice_processing_router_exists():
    # smoke test: importing router should work
    from app.workflows.routers.invoice_processing import router  # noqa: F401
