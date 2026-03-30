from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class WorkflowRunRequest(BaseModel):
    input: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)


class WorkflowRunResponse(BaseModel):
    workflow: str
    run_id: str
    status: str
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    message: Optional[str] = None
