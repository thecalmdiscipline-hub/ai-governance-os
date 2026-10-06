"""Customer-facing onboarding progress (Batch L, Deel A, 2026-10-06 night).

Deliberately separate from app/api/ops_onboarding.py (HQ-staff-only, under /ops/*). Everything here
is scoped to current_user.organization_id — never to an id taken from the request — and never
returns anything from the linked ops_accounts row itself (contact name/email, notes, source,
proposed_tier, status): only which project/tasks exist, and only the tasks marked
customer_visible=True. See app/services/onboarding.py for the shared task/phase model.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.audit import create_audit_log
from app.models.onboarding_project import OnboardingProject
from app.models.onboarding_task import OnboardingTask
from app.models.ops_account import OpsAccount
from app.models.user import User
from app.services.onboarding import apply_task_status

router = APIRouter(tags=["Onboarding"])

_OPEN_PROJECT_STATUSES = ("active", "paused")

OWNER_LABELS = {"valqeron": "Valqeron", "customer": "You", "both": "Both"}

# English translation of the Dutch phase names in app/services/onboarding.py's STANDARD_V1_TASKS
# comments (no stored/queryable phase-title field exists anywhere — the ops-side portal just shows
# "Phase N" with no name either). Not specified verbatim by the hand-off; a reasonable addition to
# satisfy "per fase (nummer, titel)".
PHASE_TITLES = {
    1: "Lead & qualification",
    2: "Proposal, contract & DPA",
    3: "Kickoff",
    4: "Technical provisioning",
    5: "Configuration & data",
    6: "Training & handover",
    7: "Go-live verification",
    8: "Aftercare",
}


def _find_active_project(db: Session, organization_id: int) -> Optional[OnboardingProject]:
    account = db.query(OpsAccount).filter(OpsAccount.organization_id == organization_id).first()
    if account is None:
        return None
    return (
        db.query(OnboardingProject)
        .filter(OnboardingProject.account_id == account.id, OnboardingProject.status.in_(_OPEN_PROJECT_STATUSES))
        .order_by(OnboardingProject.id.desc())
        .first()
    )


@router.get("/onboarding/progress")
def onboarding_progress(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = _find_active_project(db, current_user.organization_id)
    if project is None:
        return {"project": None}

    tasks = (
        db.query(OnboardingTask)
        .filter(OnboardingTask.project_id == project.id, OnboardingTask.customer_visible.is_(True))
        .order_by(OnboardingTask.phase, OnboardingTask.position)
        .all()
    )

    phase_counts: dict = {}
    for t in tasks:
        p = phase_counts.setdefault(t.phase, {"phase": t.phase, "title": PHASE_TITLES.get(t.phase, f"Phase {t.phase}"), "total": 0, "done": 0})
        p["total"] += 1
        if t.status in ("done", "skipped"):
            p["done"] += 1

    return {
        "project": {"id": project.id, "status": project.status},
        "phases": [phase_counts[k] for k in sorted(phase_counts)],
        "tasks": [
            {
                "id": t.id,
                "phase": t.phase,
                "title": t.title,
                "status": t.status,
                "owner": OWNER_LABELS.get(t.owner, t.owner),
                "editable": t.owner in ("customer", "both"),
            }
            for t in tasks
        ],
    }


class TaskStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["todo", "doing", "done"]


@router.patch("/onboarding/tasks/{task_id}")
def update_onboarding_task(
    task_id: int,
    body: TaskStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(OnboardingTask)
        .join(OnboardingProject, OnboardingTask.project_id == OnboardingProject.id)
        .join(OpsAccount, OnboardingProject.account_id == OpsAccount.id)
        .filter(
            OnboardingTask.id == task_id,
            OpsAccount.organization_id == current_user.organization_id,
            OnboardingTask.customer_visible.is_(True),
            OnboardingTask.owner.in_(("customer", "both")),
        )
        .first()
    )
    if task is None:
        return JSONResponse(status_code=404, content={"error": "task_not_found"})

    old_status = task.status
    apply_task_status(task, body.status, current_user.id)
    db.commit()

    create_audit_log(
        db,
        current_user.organization_id,
        "onboarding_task",
        task.id,
        "customer_task_status_changed",
        f"{old_status}->{body.status}",
        performed_by=current_user.username,
    )

    return {"id": task.id, "status": task.status}
