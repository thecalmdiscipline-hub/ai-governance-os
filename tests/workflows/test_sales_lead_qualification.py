def test_sales_lead_qualification_router_exists():
    # smoke test: importing router should work
    from app.workflows.routers.sales_lead_qualification import router  # noqa: F401
