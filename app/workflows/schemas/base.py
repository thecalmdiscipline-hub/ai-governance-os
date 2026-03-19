from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

class WorkflowRunRequest(BaseModel):
    input: Dict[str, Any] = Field(default_factory=dict)
    context: Optional[Dict[str, Any]] = None

class WorkflowRunResponse(BaseModel):
    workflow: str
    run_id: str
    status: str
    output: Dict[str, Any] = Field(default_factory=dict)
