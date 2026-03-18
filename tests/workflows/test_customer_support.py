def test_customer_support_router_exists():
    # smoke test: importing router should work
    from app.workflows.routers.customer_support import router  # noqa: F401
