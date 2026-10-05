from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user, require_module_access
from app.models.user import User
from app.workflows.implementations.quote_contract_generator import (
    SUPPORTED_OUTPUT_LANGUAGES,
    resolve_output_language,
)
from app.workflows.schemas.base import WorkflowRunRequest, WorkflowRunResponse
from app.workflows.services.runner import run_workflow

router = APIRouter(
    prefix="/quote-contract-generator",
    tags=["Workflows"],
    dependencies=[Depends(require_module_access("quote_contract_generator"))],
)

@router.get("/schema")
def schema():
    return WorkflowRunRequest.model_json_schema()

@router.post("/run", response_model=WorkflowRunResponse)
def run(
    body: WorkflowRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validated here (not only inside the workflow implementation) so an
    # unsupported value gets a real HTTP 422 rather than being silently
    # absorbed into run_workflow()'s generic try/except, which would
    # otherwise turn it into an HTTP 200 with status="error".
    if resolve_output_language(body.input.get("output_language")) is None:
        return JSONResponse(
            status_code=422,
            content={
                "error": "invalid_output_language",
                "allowed": list(SUPPORTED_OUTPUT_LANGUAGES),
            },
        )

    result = run_workflow("quote_contract_generator", {"input": body.input, "context": body.context, "user": current_user.username}, user_id=current_user.id, org_id=current_user.organization_id)
    return result
