def test_marketing_automation_router_exists():
    # smoke test: importing router should work
    from app.workflows.routers.marketing_automation import router  # noqa: F401
