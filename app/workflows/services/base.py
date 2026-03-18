from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.user import User
from app.workflows.schemas.base import WorkflowRunRequest, WorkflowRunResponse


def run_workflow_stub(
    workflow_name: str,
    req: WorkflowRunRequest,
    current_user: User,
    db: Session,
) -> WorkflowRunResponse:
    now = datetime.utcnow().isoformat()
    return WorkflowRunResponse(
        workflow=workflow_name,
        status="ok",
        output={
            "message": "stub",
            "user": getattr(current_user, "username", None),
            "input": getattr(req, "input", None),
        },
        started_at=now,
        finished_at=now,
    )
