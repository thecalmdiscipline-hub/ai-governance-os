import json
from typing import Any, Dict, Optional
from uuid import uuid4

from app.db.session import SessionLocal
from app.workflows.registry import WORKFLOWS, normalize_workflow_key
from app.models.workflow_run import WorkflowRun
from app.core.audit import create_audit_log


def run_workflow(
    workflow_key: str,
    payload: Dict[str, Any],
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> Dict[str, Any]:
    run_id = str(uuid4())
    key = normalize_workflow_key(workflow_key)

    fn = WORKFLOWS.get(key)
    if not fn:
        return {
            "workflow": key,
            "run_id": run_id,
            "status": "error",
            "output": {},
            "error": "unknown_workflow",
            "message": f"Workflow not registered: {key}",
        }

    db = SessionLocal()

    input_payload = (payload or {}).get("input", {}) or {}
    context_payload = (payload or {}).get("context", {}) or {}

    try:
        enriched_payload = {
            **(payload or {}),
            "org_id": org_id,
        }
        result = fn(payload=enriched_payload, user_id=user_id)

        response = {
            "workflow": key,
            "run_id": run_id,
            "status": "ok",
            "output": result if isinstance(result, dict) else {"result": result},
            "error": None,
            "message": None,
        }

        db_row = WorkflowRun(
            run_id=run_id,
            workflow=key,
            organization_id=org_id,
            user_id=user_id,
            status="ok",
            input_payload=json.dumps(input_payload, ensure_ascii=False),
            context_payload=json.dumps(context_payload, ensure_ascii=False),
            output_payload=json.dumps(response["output"], ensure_ascii=False),
            error=None,
            message=None,
        )
        db.add(db_row)
        db.commit()
        db.refresh(db_row)

        if org_id is not None:
            create_audit_log(
                db=db,
                organization_id=org_id,
                entity_type="workflow_run",
                entity_id=db_row.id,
                action="executed",
                details=f"Workflow {key} executed with status ok",
                performed_by=str(user_id) if user_id is not None else "system",
            )

        return response

    except Exception as e:
        response = {
            "workflow": key,
            "run_id": run_id,
            "status": "error",
            "output": {},
            "error": "exception",
            "message": str(e),
        }

        db_row = WorkflowRun(
            run_id=run_id,
            workflow=key,
            organization_id=org_id,
            user_id=user_id,
            status="error",
            input_payload=json.dumps(input_payload, ensure_ascii=False),
            context_payload=json.dumps(context_payload, ensure_ascii=False),
            output_payload=json.dumps({}, ensure_ascii=False),
            error="exception",
            message=str(e),
        )
        db.add(db_row)
        db.commit()
        db.refresh(db_row)

        if org_id is not None:
            create_audit_log(
                db=db,
                organization_id=org_id,
                entity_type="workflow_run",
                entity_id=db_row.id,
                action="executed",
                details=f"Workflow {key} executed with status error: {str(e)}",
                performed_by=str(user_id) if user_id is not None else "system",
            )

        return response

    finally:
        db.close()
