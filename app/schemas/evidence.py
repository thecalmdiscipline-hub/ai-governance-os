from pydantic import BaseModel
from typing import Optional


class EvidenceCreate(BaseModel):
    title: str
    description: Optional[str] = None
    ai_system_id: Optional[int] = None
    ai_risk_id: Optional[int] = None