def test_hr_recruitment_router_exists():
    # smoke test: importing router should work
    from app.workflows.routers.hr_recruitment import router  # noqa: F401
