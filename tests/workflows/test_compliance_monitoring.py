def test_compliance_monitoring_router_exists():
    # smoke test: importing router should work
    from app.workflows.routers.compliance_monitoring import router  # noqa: F401
