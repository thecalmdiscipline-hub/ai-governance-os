def test_meeting_agenda_assistant_router_exists():
    # smoke test: importing router should work
    from app.workflows.routers.meeting_agenda_assistant import router  # noqa: F401
