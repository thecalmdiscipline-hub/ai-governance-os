"""Onboarding projects and tasks (Batch I, Fase 2.2): started from the 'standard-v1' template for
an OpsAccount, tracked phase by phase. Only reachable under /ops/* (require_ops_access)."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_ops_access
from app.core.ops_audit import log_ops_action
from app.models.onboarding_project import OnboardingProject
from app.models.onboarding_task import OnboardingTask
from app.models.onboarding_template import OnboardingTemplate
from app.models.onboarding_template_task import OnboardingTemplateTask
from app.models.ops_account import OpsAccount
from app.models.user import User
from app.services.onboarding import (
    OnboardingError,
    PROJECT_STATUSES,
    TASK_STATUSES,
    apply_task_status,
    create_project_from_template,
    get_project_metrics,
)

router = APIRouter(prefix="/ops", tags=["Ops"], dependencies=[Depends(require_ops_access)])


def _template_dict(t: OnboardingTemplate) -> dict:
    return {"id": t.id, "key": t.key, "name": t.name, "version": t.version, "is_active": t.is_active}


def _task_dict(t: OnboardingTask) -> dict:
    return {
        "id": t.id,
        "project_id": t.project_id,
        "phase": t.phase,
        "position": t.position,
        "title": t.title,
        "owner": t.owner,
        "customer_visible": t.customer_visible,
        "status": t.status,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "completed_by_user_id": t.completed_by_user_id,
        "note": t.note,
    }


def _project_dict(p: OnboardingProject, tasks: Optional[List[OnboardingTask]] = None) -> dict:
    out = {
        "id": p.id,
        "account_id": p.account_id,
        "template_key": p.template_key,
        "template_version": p.template_version,
        "status": p.status,
        "target_golive_date": p.target_golive_date.isoformat() if p.target_golive_date else None,
        "started_at": p.started_at.isoformat() if p.started_at else None,
        "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        "created_by_user_id": p.created_by_user_id,
    }
    if tasks is not None:
        out["tasks"] = [_task_dict(t) for t in sorted(tasks, key=lambda t: (t.phase, t.position))]
    return out


@router.get("/onboarding/templates")
def list_templates(db: Session = Depends(get_db)):
    rows = db.query(OnboardingTemplate).order_by(OnboardingTemplate.key).all()
    return {"templates": [_template_dict(t) for t in rows]}


@router.post("/accounts/{account_id}/onboarding", status_code=201)
def start_onboarding(
    account_id: int,
    current_user: User = Depends(require_ops_access),
    db: Session = Depends(get_db),
):
    account = db.query(OpsAccount).filter(OpsAccount.id == account_id).first()
    if account is None:
        return JSONResponse(status_code=404, content={"error": "account_not_found"})

    try:
        project = create_project_from_template(db, account_id=account.id, created_by_user_id=current_user.id)
    except OnboardingError as exc:
        return JSONResponse(status_code=exc.status, content={"error": exc.code})

    log_ops_action(
        db, current_user, "onboarding_project_started", target_org_id=account.organization_id,
        details=f"account_id={account.id}; project_id={project.id}; template={project.template_key}",
    )
    tasks = db.query(OnboardingTask).filter(OnboardingTask.project_id == project.id).all()
    return _project_dict(project, tasks)


@router.get("/onboarding/projects")
def list_projects(
    status: Optional[str] = Query(default=None),
    account_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    if status is not None and status not in PROJECT_STATUSES:
        return JSONResponse(status_code=422, content={"error": "invalid_status", "allowed": list(PROJECT_STATUSES)})
    query = db.query(OnboardingProject)
    if status is not None:
        query = query.filter(OnboardingProject.status == status)
    if account_id is not None:
        query = query.filter(OnboardingProject.account_id == account_id)
    rows = query.order_by(OnboardingProject.id.desc()).limit(200).all()
    return {"projects": [_project_dict(p) for p in rows]}


def _get_project_or_404(db: Session, project_id: int) -> Optional[OnboardingProject]:
    return db.query(OnboardingProject).filter(OnboardingProject.id == project_id).first()


@router.get("/onboarding/projects/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    if project is None:
        return JSONResponse(status_code=404, content={"error": "project_not_found"})
    tasks = db.query(OnboardingTask).filter(OnboardingTask.project_id == project.id).all()
    return _project_dict(project, tasks)


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_golive_date: Optional[date] = None
    status: Optional[str] = None


@router.patch("/onboarding/projects/{project_id}")
def update_project(
    project_id: int,
    body: ProjectUpdate,
    current_user: User = Depends(require_ops_access),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    project = _get_project_or_404(db, project_id)
    if project is None:
        return JSONResponse(status_code=404, content={"error": "project_not_found"})

    fields = body.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] not in PROJECT_STATUSES:
        return JSONResponse(status_code=422, content={"error": "invalid_status", "allowed": list(PROJECT_STATUSES)})

    account = db.query(OpsAccount).filter(OpsAccount.id == project.account_id).first()
    changed = False
    for key, value in fields.items():
        if getattr(project, key) != value:
            setattr(project, key, value)
            changed = True
    if "status" in fields:
        project.completed_at = datetime.utcnow() if fields["status"] == "completed" else None

    if changed:
        db.commit()
        log_ops_action(
            db, current_user, "onboarding_project_updated", target_org_id=account.organization_id if account else None,
            details=f"project_id={project.id}; fields={','.join(sorted(fields.keys()))}",
        )
    db.refresh(project)
    return _project_dict(project)


@router.get("/onboarding/projects/{project_id}/metrics")
def project_metrics(project_id: int, db: Session = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    if project is None:
        return JSONResponse(status_code=404, content={"error": "project_not_found"})
    tasks = db.query(OnboardingTask).filter(OnboardingTask.project_id == project.id).all()
    return get_project_metrics(project, tasks)


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Optional[str] = None
    note: Optional[str] = None


@router.patch("/onboarding/tasks/{task_id}")
def update_task(
    task_id: int,
    body: TaskUpdate,
    current_user: User = Depends(require_ops_access),
    db: Session = Depends(get_db),
):
    task = db.query(OnboardingTask).filter(OnboardingTask.id == task_id).first()
    if task is None:
        return JSONResponse(status_code=404, content={"error": "task_not_found"})

    fields = body.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] not in TASK_STATUSES:
        return JSONResponse(status_code=422, content={"error": "invalid_status", "allowed": list(TASK_STATUSES)})

    project = db.query(OnboardingProject).filter(OnboardingProject.id == task.project_id).first()
    account = db.query(OpsAccount).filter(OpsAccount.id == project.account_id).first() if project else None

    old_status = task.status
    changed = False
    if "status" in fields and fields["status"] != old_status:
        apply_task_status(task, fields["status"], current_user.id)
        changed = True
    if "note" in fields and fields["note"] != task.note:
        task.note = fields["note"]
        changed = True

    if changed:
        db.commit()
        details = f"task_id={task.id}"
        if "status" in fields and fields["status"] != old_status:
            details += f"; {old_status}->{fields['status']}"
        # Never include the note text itself in the audit details.
        log_ops_action(
            db, current_user, "onboarding_task_updated", target_org_id=account.organization_id if account else None,
            details=details,
        )
    db.refresh(task)
    return _task_dict(task)
