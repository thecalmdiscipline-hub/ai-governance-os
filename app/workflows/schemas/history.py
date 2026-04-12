from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowRunHistoryItem(BaseModel):
    id: int
    run_id: str
    workflow: str
    status: str
    organization_id: Optional[int] = None
    user_id: Optional[int] = None
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    context_payload: Dict[str, Any] = Field(default_factory=dict)
    output_payload: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    message: Optional[str] = None
    created_at: str


class WorkflowRunHistoryResponse(BaseModel):
    total: int
    items: List[WorkflowRunHistoryItem] = Field(default_factory=list)
