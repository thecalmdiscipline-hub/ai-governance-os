from pydantic import BaseModel
from typing import Optional, Dict, Any

class WorkflowRunRequest(BaseModel):
    # later: input payload per workflow (now generic)
    input: Dict[str, Any]
    dry_run: bool = True
    correlation_id: Optional[str] = None

class WorkflowRunResponse(BaseModel):
    workflow: str
    status: str
    dry_run: bool
    output: Dict[str, Any]
