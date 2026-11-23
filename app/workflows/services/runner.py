import json
from typing import Any, Dict, Optional
from uuid import uuid4

from app.db.session import SessionLocal
from app.workflows.registry import WORKFLOWS, normalize_workflow_key
from app.models.workflow_run import WorkflowRun
from app.models.document_usage import DocumentUsage
from app.core.audit import create_audit_log
from app.services.document_access import finish_usage_capture, start_usage_capture


def _add_usage_rows(db, run_id: str, usage: Dict[str, Any]) -> None:
    # B6: same transaction as the WorkflowRun row (committed together by the caller).
    for doc in usage["docs"]:
        db.add(DocumentUsage(run_id=run_id, document_id=doc["id"], codes=",".join(doc["codes"])))


def _audit_documents(db, org_id: int, run_row_id: int, key: str, usage: Dict[str, Any], user_id) -> None:
    # V19: one audit line per run of a document-reading workflow, with document names and codes.
    if not usage["accessed"]:
        return
    if usage["docs"]:
        listed = "; ".join(f"{d['filename']} [{','.join(d['codes'])}]" for d in usage["docs"])
        details = f"Workflow {key} read {len(usage['docs'])} document(s): {listed}"
    else:
        details = f"Workflow {key} read no documents"
    create_audit_log(
        db=db,
        organization_id=org_id,
        entity_type="workflow_run",
        entity_id=run_row_id,
        action="workflow_run_documents",
        details=details,
        performed_by=str(user_id) if user_id is not None else "system",
    )


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
    usage: Dict[str, Any] = {"accessed": False, "docs": []}

    try:
        enriched_payload = {
            **(payload or {}),
            "org_id": org_id,
        }
        capture_token = start_usage_capture()
        try:
            result = fn(payload=enriched_payload, user_id=user_id)
        finally:
            usage = finish_usage_capture(capture_token)

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
        _add_usage_rows(db, run_id, usage)
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
            _audit_documents(db, org_id, db_row.id, key, usage, user_id)

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
        _add_usage_rows(db, run_id, usage)
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
            _audit_documents(db, org_id, db_row.id, key, usage, user_id)

        return response

    finally:
        db.close()
