from datetime import datetime

from pydantic import BaseModel
from typing import Optional


class EvidenceCreate(BaseModel):
    title: str
    description: Optional[str] = None
    ai_system_id: Optional[int] = None
    ai_risk_id: Optional[int] = None


class EvidenceResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    file_reference: Optional[str]
    created_at: datetime
    ai_system_id: Optional[int]
    ai_risk_id: Optional[int]

    model_config = {"from_attributes": True}