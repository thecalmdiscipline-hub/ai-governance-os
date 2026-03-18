def test_business_intelligence_router_exists():
    # smoke test: importing router should work
    from app.workflows.routers.business_intelligence import router  # noqa: F401
