import json
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.workflow_run import WorkflowRun
from app.core.audit import create_audit_log

router = APIRouter(prefix="/workflows", tags=["Workflows"])


def _decode_payload(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _serialize_run(row: WorkflowRun):
    return {
        "id": row.id,
        "run_id": row.run_id,
        "workflow": row.workflow,
        "status": row.status,
        "organization_id": row.organization_id,
        "user_id": row.user_id,
        "input_payload": _decode_payload(row.input_payload),
        "context_payload": _decode_payload(row.context_payload),
        "output_payload": _decode_payload(row.output_payload),
        "error": row.error,
        "message": row.message,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def _get_org_query(db: Session, organization_id: int):
    return db.query(WorkflowRun).filter(
        WorkflowRun.organization_id == organization_id
    )


def _get_run_or_404(db: Session, organization_id: int, run_id: str):
    row = (
        _get_org_query(db, organization_id)
        .filter(WorkflowRun.run_id == run_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return row


@router.get("/history")
def get_workflow_history(
    limit: int = Query(default=50, ge=1, le=200),
    workflow: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    q = _get_org_query(db, int(current_user.organization_id))

    if workflow:
        q = q.filter(WorkflowRun.workflow == workflow)

    rows = q.order_by(WorkflowRun.id.desc()).limit(limit).all()

    return {
        "total": len(rows),
        "items": [_serialize_run(row) for row in rows],
    }


@router.get("/recent")
def get_workflow_recent(
    limit: int = Query(default=10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    rows = (
        _get_org_query(db, int(current_user.organization_id))
        .order_by(WorkflowRun.id.desc())
        .limit(limit)
        .all()
    )

    items = [
        {
            "id": row.id,
            "run_id": row.run_id,
            "workflow": row.workflow,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]

    return {
        "total": len(items),
        "items": items,
    }


@router.get("/summary")
def get_workflow_summary(
    limit: int = Query(default=5, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    all_rows = (
        _get_org_query(db, int(current_user.organization_id))
        .order_by(WorkflowRun.id.desc())
        .all()
    )

    total_runs = len(all_rows)
    ok_runs = sum(1 for row in all_rows if row.status == "ok")
    error_runs = sum(1 for row in all_rows if row.status != "ok")
    success_rate = round((ok_runs / total_runs) * 100, 1) if total_runs else 0.0

    counts = {}
    for row in all_rows:
        counts[row.workflow] = counts.get(row.workflow, 0) + 1

    workflow_cards = [
        {"workflow": workflow, "count": count}
        for workflow, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    ]

    latest_runs = [
        {
            "id": row.id,
            "run_id": row.run_id,
            "workflow": row.workflow,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in all_rows[:limit]
    ]

    return {
        "stats": {
            "total_runs": total_runs,
            "ok_runs": ok_runs,
            "error_runs": error_runs,
            "success_rate": success_rate,
        },
        "latest_runs": latest_runs,
        "workflow_cards": workflow_cards,
    }


@router.get("/dashboard")
def get_workflow_dashboard(
    limit: int = Query(default=10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    all_rows = (
        _get_org_query(db, int(current_user.organization_id))
        .order_by(WorkflowRun.id.desc())
        .all()
    )

    total_runs = len(all_rows)
    ok_runs = sum(1 for row in all_rows if row.status == "ok")
    error_runs = sum(1 for row in all_rows if row.status != "ok")
    success_rate = round((ok_runs / total_runs) * 100, 1) if total_runs else 0.0

    counts = {}
    for row in all_rows:
        counts[row.workflow] = counts.get(row.workflow, 0) + 1

    workflow_cards = [
        {"workflow": workflow, "count": count}
        for workflow, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    ]

    recent_runs = [
        {
            "id": row.id,
            "run_id": row.run_id,
            "workflow": row.workflow,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in all_rows[:limit]
    ]

    history = [_serialize_run(row) for row in all_rows[:limit]]

    return {
        "stats": {
            "total_runs": total_runs,
            "ok_runs": ok_runs,
            "error_runs": error_runs,
            "success_rate": success_rate,
        },
        "workflow_cards": workflow_cards,
        "recent_runs": recent_runs,
        "history": history,
    }


@router.get("/runs/{run_id}")
def get_workflow_run_detail(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    row = _get_run_or_404(db, int(current_user.organization_id), run_id)
    return _serialize_run(row)


@router.get("/runs/{run_id}/card")
def get_workflow_run_card(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    row = _get_run_or_404(db, int(current_user.organization_id), run_id)

    return {
        "run": {
            "id": row.id,
            "run_id": row.run_id,
            "workflow": row.workflow,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        },
        "input": _decode_payload(row.input_payload) or {},
        "output": _decode_payload(row.output_payload) or {},
        "error": row.error,
        "message": row.message,
    }


@router.delete("/runs/{run_id}")
def delete_workflow_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")

    row = _get_run_or_404(db, int(current_user.organization_id), run_id)

    deleted = {
        "id": row.id,
        "run_id": row.run_id,
        "workflow": row.workflow,
    }

    db.delete(row)
    db.commit()

    create_audit_log(
        db=db,
        organization_id=int(current_user.organization_id),
        entity_type="workflow_run",
        entity_id=int(deleted["id"]),
        action="deleted",
        details=f'Workflow run deleted: workflow={deleted["workflow"]}, run_id={deleted["run_id"]}',
        performed_by=current_user.username,
    )

    return {
        "status": "ok",
        "deleted": deleted,
    }
