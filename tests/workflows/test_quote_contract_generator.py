def test_quote_contract_generator_router_exists():
    # smoke test: importing router should work
    from app.workflows.routers.quote_contract_generator import router  # noqa: F401
